import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import gi
from icon_render_match import match_icon

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib  # noqa: E402 — GI version must be selected first

PROJECT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--endpoint")
parser.add_argument("--moderator-file", type=Path)
parser.add_argument("--node", default=shutil.which("node"))
parser.add_argument("--isolation-only", action="store_true")
parser.add_argument("--components", action="store_true")
parser.add_argument("--upstream-fixture", type=Path)
parser.add_argument("--upstream-catalog", type=Path)
parser.add_argument("--upstream-slug", default="godot")
parser.add_argument("--upstream-provider", default="dashboard")
parser.add_argument("--upstream-config", type=Path)
parser.add_argument("--case-name")
parser.add_argument("--verify-cancel", action="store_true")
args = parser.parse_args()
if args.case_name and not re.fullmatch(r"[a-z0-9-]+", args.case_name):
    parser.error("--case-name must contain only lowercase letters, numbers and hyphens")
if args.upstream_fixture and not args.upstream_catalog:
    parser.error("--upstream-fixture requires --upstream-catalog")
if not args.isolation_only and not args.components and not args.upstream_fixture:
    if not args.endpoint or not args.moderator_file or not args.node:
        parser.error(
            "The contribution flow requires --endpoint, --moderator-file and Node.js on PATH (or --node)"
        )
assert os.getuid() != 0, "Run as desktop user"
assert os.environ.get("APP_FACES_ISOLATED_DISPLAY") == "1", "Private display is required"
ARTIFACTS = PROJECT / "state/native-e2e"
if args.case_name:
    ARTIFACTS = ARTIFACTS / args.case_name
ARTIFACTS.mkdir(parents=True, exist_ok=True)
checks = {}


def verify_display_isolation():
    display = os.environ.get("DISPLAY", "")
    assert re.fullmatch(r":[0-9]+", display) and int(display[1:]) >= 99
    assert os.environ.get("XDG_SESSION_TYPE") == "x11"
    assert not os.environ.get("WAYLAND_DISPLAY")
    assert f"/run/user/{os.getuid()}/bus" not in os.environ.get("DBUS_SESSION_BUS_ADDRESS", "")
    server_pid = int(Path(f"/tmp/.X{display[1:]}-lock").read_text().strip())
    server_args = Path(f"/proc/{server_pid}/cmdline").read_bytes().split(b"\0")
    assert Path(os.fsdecode(server_args[0])).name == "Xvfb" and display.encode() in server_args
    Atspi.get_desktop(0)
    reply = subprocess.check_output(
        [
            "busctl",
            "--user",
            "call",
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetConnectionUnixProcessID",
            "s",
            "org.a11y.Bus",
        ],
        text=True,
    )
    pid = int(reply.split()[1])
    environment = dict(
        part.split(b"=", 1)
        for part in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
        if b"=" in part
    )
    assert environment.get(b"DISPLAY") == display.encode(), (
        "Accessibility service escaped the test display"
    )
    checks["accessibility_service_uses_isolated_display"] = True


def pump(duration=0.12):
    loop = GLib.MainLoop()
    GLib.timeout_add(int(duration * 1000), lambda: (loop.quit(), False)[1])
    loop.run()


def children(root):
    for index in range(root.get_child_count()):
        item = root.get_child_at_index(index)
        if item:
            yield item


def walk(root, depth=0):
    if depth > 45:
        return
    yield root
    for child in children(root):
        try:
            yield from walk(child, depth + 1)
        except GLib.Error:
            continue


def wait(condition, description, timeout=20):
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            value = condition()
            if value:
                return value
        except (GLib.Error, RuntimeError, AssertionError) as error:
            last = error
        pump()
    raise AssertionError(f"Timed out: {description}; last={last}")


def window(title):
    for app in children(Atspi.get_desktop(0)):
        for item in children(app):
            if item.get_name() == title:
                return item
    return None


def find(title, name, role=None):
    root = window(title)
    if root is None:
        return None
    found = [
        n
        for n in walk(root)
        if n.get_name() == name and (role is None or n.get_role_name() == role)
    ]
    if len(found) != 1:
        return None
    return found[0]


def node(title, name, role=None):
    return wait(lambda: find(title, name, role), f"{title}: {name} / {role}")


def action(title, name, role="button", action_name="click"):
    item = node(title, name, role)
    actions = item.get_action_iface()
    labels = [actions.get_action_name(i) for i in range(actions.get_n_actions())]
    assert action_name in labels, (name, labels)
    assert actions.do_action(labels.index(action_name))
    pump(0.4)


def click_bound(title, name, role):
    item = node(title, name, role)
    component = item.get_component_iface()
    try:
        component.scroll_to(Atspi.ScrollType.ANYWHERE)
    except GLib.Error:
        pass
    pump()
    bounds = component.get_extents(Atspi.CoordType.SCREEN)
    relative = []
    if bounds.y <= 0 or bounds.width <= 0 or bounds.height <= 0:
        bounds = component.get_extents(Atspi.CoordType.WINDOW)
        window_ids = subprocess.check_output(
            ["/usr/bin/xdotool", "search", "--onlyvisible", "--name", "^" + re.escape(title) + "$"],
            text=True,
        ).split()
        assert len(window_ids) == 1, window_ids
        relative = ["--window", window_ids[0]]
    assert bounds.x >= 0 and bounds.y > 0 and bounds.width > 0 and bounds.height > 0, (
        name,
        bounds.x,
        bounds.y,
        bounds.width,
        bounds.height,
    )
    print("Click bounds", name, bounds.x, bounds.y, bounds.width, bounds.height, flush=True)
    assert item.get_state_set().contains(Atspi.StateType.SHOWING)
    subprocess.run(
        [
            "/usr/bin/xdotool",
            "mousemove",
            "--sync",
            *relative,
            str(
                bounds.x
                + (min(20, bounds.width // 2) if role == "check box" else bounds.width // 2)
            ),
            str(bounds.y + bounds.height // 2),
            "click",
            "1",
        ],
        check=True,
    )
    pump(0.4)


def text(title, name, value):
    item = node(title, name, "entry" if name == "Search catalog" else "text")
    assert item.get_editable_text_iface().set_text_contents(value)
    pump()
    assert Atspi.Text.get_text(item, 0, -1) == value


def select_file(title, filename):
    item = node(title, filename + ". File")
    selection = item.get_parent().get_selection_iface()
    assert selection.clear_selection()
    assert selection.select_child(item.get_index_in_parent())
    assert selection.get_n_selected_children() == 1
    wait(lambda: item.get_state_set().contains(Atspi.StateType.SELECTED), "file selected")


def capture(name):

    script = "import gi,sys;gi.require_version('Gdk','3.0');from gi.repository import Gdk; w=Gdk.get_default_root_window();p=Gdk.pixbuf_get_from_window(w,0,0,w.get_width(),w.get_height());p.savev(sys.argv[1],'png',[],[])"
    subprocess.run(["/usr/bin/python3", "-c", script, str(ARTIFACTS / (name + ".png"))], check=True)


def bridge(action_name, app_name):
    subprocess.run(
        [
            args.node,
            str(PROJECT / "backend/e2e/native-bridge.mjs"),
            action_name,
            app_name,
            args.endpoint,
            str(args.moderator_file),
            str(ARTIFACTS / ("browser-" + action_name + ".png")),
        ],
        cwd=PROJECT / "backend",
        check=True,
        timeout=90,
    )


def launch_chooser(folder, filename):
    select_file(folder.name, filename)
    root = node(folder.name, folder.name, "frame")
    interface = root.get_action_iface()
    labels = [interface.get_action_name(i) for i in range(interface.get_n_actions())]
    scripts = [s for s in labels if s.startswith("view.script_") and "App%2520Faces" in s]
    assert len(scripts) == 1, scripts
    assert interface.do_action(labels.index(scripts[0]))
    wait(lambda: window("App Faces"), "chooser launched through Files")
    pump(0.5)


def rendered_artwork(folder, filename, screenshot, artwork):
    tile = node(folder.name, filename + ". File")
    bounds = tile.get_component_iface().get_extents(Atspi.CoordType.WINDOW)
    ids = subprocess.check_output(
        ["xdotool", "search", "--onlyvisible", "--name", "^" + re.escape(folder.name) + "$"],
        text=True,
    ).split()
    assert len(ids) == 1
    geometry = dict(
        line.split("=", 1)
        for line in subprocess.check_output(
            ["xdotool", "getwindowgeometry", "--shell", ids[0]], text=True
        ).splitlines()
    )

    frame_property = subprocess.check_output(
        ["xprop", "-id", ids[0], "_GTK_FRAME_EXTENTS"], text=True
    )
    shadow = [int(value) for value in re.findall(r"\d+", frame_property.split("=", 1)[-1])]
    shadow_left, shadow_top = (shadow[0], shadow[2]) if len(shadow) == 4 else (0, 0)
    left = bounds.x + int(geometry["X"]) + shadow_left
    top = bounds.y + int(geometry["Y"]) + shadow_top

    result = match_icon(
        screenshot,
        artwork,
        (left, top, bounds.width, bounds.height),
        coordinate_margin=32 if "no such atom" in frame_property else 0,
    )
    result["tileBounds"] = [left, top, bounds.width, bounds.height]
    result["geometry"] = geometry
    result["frameProperty"] = frame_property
    frame_bounds = (
        node(folder.name, folder.name, "frame")
        .get_component_iface()
        .get_extents(Atspi.CoordType.WINDOW)
    )
    result["frameBounds"] = [
        frame_bounds.x,
        frame_bounds.y,
        frame_bounds.width,
        frame_bounds.height,
    ]
    (ARTIFACTS / (screenshot.stem + "-match.json")).write_text(json.dumps(result, indent=2) + "\n")
    return result


def upstream_case(root, folder, executable, catalog):
    from app_faces.automatic import run_once
    from app_faces.community import png_bytes
    from app_faces.core import atomic_json, custom_icon, icon_path

    negative_dir = root / "misleading-name"
    negative_dir.mkdir()
    impostor = negative_dir / "Telegram"
    shutil.copyfile("/usr/bin/true", impostor)
    impostor.chmod(0o700)
    atomic_json(
        root / "config/app-faces/config.json",
        {"directories": [str(negative_dir)], "automatic_enabled": True},
    )
    automatic = run_once()
    assert not automatic["errors"] and not automatic["applied"], automatic
    assert not custom_icon(impostor), "A popular filename must not assign identity automatically"
    atomic_json(
        root / "config/app-faces/config.json", {"directories": [], "automatic_enabled": False}
    )

    entry = next(
        e
        for e in catalog["icons"]
        if e["slug"] == args.upstream_slug and e["provider"] == args.upstream_provider
    )
    assert not custom_icon(executable)
    assert not (root / "cache/app-faces/assets.json").exists()
    capture("upstream-files-before")
    launch_chooser(folder, executable.name)
    label = entry["name"] + "  ·  " + entry["provider"]
    node("App Faces", label, "button")
    action("App Faces", label)
    wait(
        lambda: find("App Faces", "Ready to apply", "label"),
        "real upstream artwork downloaded",
        timeout=35,
    )
    if args.verify_cancel:
        action("App Faces", "App Faces", "frame", "window.close")
        wait(lambda: not window("App Faces"), "preview dismissed without applying")
        assert not custom_icon(executable), "Choosing a preview must not change the file"
        capture("upstream-preview-cancelled")
        launch_chooser(folder, executable.name)
        action("App Faces", label)
        wait(lambda: find("App Faces", "Ready to apply", "label"), "preview reopened")
    assets = json.loads((root / "cache/app-faces/assets.json").read_text())
    asset = assets[entry["provider"] + ":" + entry["source_revision"] + ":" + entry["slug"]]
    assert asset["source_url"] == entry["source_url"]
    action("App Faces", "Apply icon")
    wait(lambda: custom_icon(executable), "real portable custom icon")
    applied = icon_path(custom_icon(executable))
    assert applied and applied.read_bytes() == png_bytes(asset["path"])
    applied_hash = hashlib.sha256(applied.read_bytes()).hexdigest()
    shutil.copyfile(applied, ARTIFACTS / "upstream-applied-icon.png")
    action("App Faces", "App Faces", "frame", "window.close")
    wait(lambda: not window("App Faces"), "chooser closed, Files visible")
    pump(1)
    capture("upstream-files-applied")
    artwork = ARTIFACTS / "upstream-applied-icon.png"
    before_match = rendered_artwork(
        folder, executable.name, ARTIFACTS / "upstream-files-before.png", artwork
    )
    assert not before_match["matched"], "Initial generic tile must not match the expected artwork"

    def visible_artwork():
        capture("upstream-files-applied")
        return rendered_artwork(
            folder, executable.name, ARTIFACTS / "upstream-files-applied.png", artwork
        )["matched"]

    wait(visible_artwork, "Files must visibly show the downloaded icon without reload", timeout=6)
    applied_match = rendered_artwork(
        folder, executable.name, ARTIFACTS / "upstream-files-applied.png", artwork
    )
    launch_chooser(folder, executable.name)
    action("App Faces", "Restore previous")
    wait(lambda: not custom_icon(executable), "real portable Undo")
    action("App Faces", "App Faces", "frame", "window.close")
    wait(lambda: not window("App Faces"), "restored Files visible")
    pump(0.5)
    capture("upstream-files-restored")
    restored_match = rendered_artwork(
        folder, executable.name, ARTIFACTS / "upstream-files-restored.png", artwork
    )
    assert not restored_match["matched"], "Undo must remove the rendered upstream artwork"
    result = {
        "passed": True,
        "fixture": str(args.upstream_fixture),
        "fixtureSha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "sourceUrl": asset["source_url"],
        "sourceRevision": entry["source_revision"],
        "appliedPngSha256": applied_hash,
        "initialSearchOfferedExpectedApp": True,
        "cancelledPreviewPreservedOriginalIcon": args.verify_cancel,
        "automaticPreservedMisleadingExecutable": True,
        "visualRenderVerifiedWithoutReload": True,
        "fileTileArtworkTemplate": {
            "before": before_match,
            "applied": applied_match,
            "restored": restored_match,
        },
        "artworkCacheInitiallyEmpty": True,
        "appliedBytesMatchDownloadedNormalizedArtwork": True,
        "undoRestoredMissingCustomIcon": True,
        "binaryExecuted": False,
        "uploaded": False,
        "visualEvidence": [
            "upstream-files-before.png",
            "upstream-files-applied.png",
            "upstream-files-restored.png",
        ],
    }
    (ARTIFACTS / "upstream-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def main():
    root = Path(os.environ["APP_FACES_E2E_ROOT"])
    verify_display_isolation()
    if args.isolation_only:
        print("Activated accessibility service is on the private display; no input generated.")
        return
    if args.components:
        subprocess.run(
            [str(PROJECT / ".venv/bin/python"), "-m", "pytest", "-q", "tests/test_native_ui.py"],
            env=dict(os.environ, APP_FACES_GTK_TEST="1"),
            check=True,
        )
        return
    os.environ.update(
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_DATA_HOME=str(root / "data"),
        XDG_CACHE_HOME=str(root / "cache"),
        GDK_BACKEND="x11",
        GTK_USE_PORTAL="0",
        GSK_RENDERER="cairo",
        PYTHONPATH=str(PROJECT),
        PULSE_SERVER="unix:/nonexistent/app-faces-audio",
        PIPEWIRE_REMOTE="/nonexistent/app-faces-audio",
    )
    from app_faces.automatic import run_once
    from app_faces.community import (
        fetch_approved,
        revise_submission,
        submission_status,
        submissions,
    )
    from app_faces.core import atomic_json, custom_icon
    from app_faces.installation import managed_files

    folder = root / "App Faces Flow"
    folder.mkdir()
    app_name = "Native Flow " + uuid.uuid4().hex[:8]
    app_id = "org.appfaces.NativeFlow." + uuid.uuid4().hex[:8]
    first = folder / "Native Source"
    second = folder / "Native Consumer"
    for p in [first, second]:
        p.write_text("#!/bin/sh\nexit 0\n")
        p.chmod(0o700)
    if args.upstream_fixture:
        first.unlink()
        second.unlink()
        first = folder / args.upstream_fixture.name
        shutil.copyfile(args.upstream_fixture, first)
        first.chmod(0o700)
    icon = folder / "icon.svg"
    icon.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" rx="30" fill="#{uuid.uuid4().hex[:6]}"/><circle cx="64" cy="64" r="28" fill="white"/></svg>'
    )
    script_path = root / "data/nautilus/scripts/App Faces"
    content = managed_files(PROJECT)[script_path]
    script_path.parent.mkdir(parents=True)
    script_path.write_text(content)
    script_path.chmod(0o700)
    atomic_json(
        root / "config/app-faces/config.json",
        {"community_url": args.endpoint, "directories": [], "automatic_enabled": False},
    )
    atomic_json(
        root / "cache/app-faces/catalog.json", {"version": 1, "icons": [], "fingerprints": {}}
    )
    if args.upstream_config:
        from app_faces.upstreams import sources

        shutil.copyfile(args.upstream_config, root / "config/app-faces/upstreams.toml")
        configured = sources()
        assert args.upstream_provider in configured and configured[args.upstream_provider].enabled
    if args.upstream_fixture:
        from app_faces.upstreams import configuration_revision

        catalog = json.loads(args.upstream_catalog.read_text())
        atomic_json(root / "cache/app-faces/catalog.json", catalog)

        upstream_revision = configuration_revision()
        atomic_json(
            root / "cache/app-faces/refresh-attempt",
            {
                "attempted_configuration": upstream_revision,
                "applied_configuration": upstream_revision,
                "attempted_at": time.time(),
                "failed": False,
            },
        )
        atomic_json(
            root / "config/app-faces/config.json", {"directories": [], "automatic_enabled": False}
        )
        icon.unlink()
    for key in ["index-recursive-directories", "index-single-directories"]:
        subprocess.run(
            ["/usr/bin/gsettings", "set", "org.freedesktop.Tracker3.Miner.Files", key, "[]"],
            check=True,
        )
    log = (ARTIFACTS / "applications.log").open("w")
    process = subprocess.Popen(
        ["/usr/bin/nautilus", "--new-window", str(folder)], stdout=log, stderr=log
    )
    try:
        wait(lambda: window(folder.name), "Files window")
        if args.upstream_fixture:
            upstream_case(root, folder, first, catalog)
            return
        launch_chooser(folder, first.name)
        checks["files_script_opens_native_chooser"] = True
        action("App Faces", "Choose image…")
        wait(lambda: window("Choose application icon"), "native file picker")

        picker = window("Choose application icon")
        pump(1)
        (ARTIFACTS / "picker-ui.json").write_text(
            json.dumps(
                [{"role": n.get_role_name(), "name": n.get_name()} for n in walk(picker)],
                ensure_ascii=False,
                indent=2,
            )
        )
        capture("file-picker")
        click_bound("Choose application icon", "icon.svg", "table cell")
        action("Choose application icon", "Open")
        wait(lambda: not window("Choose application icon"), "picker closes")
        action("App Faces", "Apply icon")
        wait(lambda: custom_icon(first), "actual GVFS icon applied")
        checks["native_file_pick_and_apply"] = True
        capture("applied-native-icon")
        action("App Faces", "Restore previous")
        wait(lambda: not custom_icon(first), "Undo restores baseline")
        checks["native_undo_restores_baseline"] = True
        text("App Faces", "Application name", app_name)
        checkbox = node("App Faces", "Share this icon when applying", "check box")
        assert not checkbox.get_state_set().contains(Atspi.StateType.CHECKED)
        frame = (
            node("App Faces", "App Faces", "frame")
            .get_component_iface()
            .get_extents(Atspi.CoordType.SCREEN)
        )
        subprocess.run(
            [
                "/usr/bin/xdotool",
                "mousemove",
                str(frame.x + 15),
                str(frame.y + 400),
                "click",
                "--repeat",
                "8",
                "--delay",
                "60",
                "5",
            ],
            check=True,
        )
        pump(0.4)
        click_bound("App Faces", "Share this icon when applying", "check box")
        wait(
            lambda: checkbox.get_state_set().contains(Atspi.StateType.CHECKED),
            "explicit share consent",
        )
        capture("sharing-consent")

        expander = next(
            (
                n
                for n in walk(window("App Faces"))
                if n.get_name() == "Contribution details" and n.get_role_name() != "label"
            ),
            None,
        )
        if expander:
            action("App Faces", "Contribution details", action_name="activate")
        text("App Faces", "Application ID", app_id)
        text("App Faces", "Image source", "https://example.org/generated-native-e2e-art")
        text("App Faces", "License / attribution", "CC0-1.0")
        action("App Faces", "Apply icon")
        receipt = wait(
            lambda: next(
                (r["id"] for r in submissions() if r["name"] == app_name and r["sent"]), None
            ),
            "native consent upload",
            timeout=40,
        )
        assert submission_status(receipt)["status"] == "pending"
        checks["native_explicit_consent_upload_pending"] = True
        bridge("approve", app_name)
        assert submission_status(receipt)["status"] == "approved"
        checks["firefox_approval_visible_to_native_client"] = True
        run_once()
        downloaded = fetch_approved(app_id)
        assert downloaded.is_file()
        checks["background_catalog_sync_and_verified_download"] = True
        action("App Faces", "Restore previous")
        action("App Faces", "App Faces", "frame", "window.close")
        wait(lambda: not window("App Faces"), "first chooser closes")
        launch_chooser(folder, second.name)
        text("App Faces", "Search catalog", app_name)
        choice = wait(
            lambda: next(
                (
                    n
                    for n in walk(window("App Faces"))
                    if n.get_role_name() == "button"
                    and n.get_name().startswith(app_name)
                    and "community" in n.get_name()
                ),
                None,
            ),
            "approved artwork search result",
        )
        action("App Faces", choice.get_name())
        wait(
            lambda: find("App Faces", "Ready to apply", "label"),
            "approved preview downloaded",
        )
        action("App Faces", "Apply icon")
        wait(lambda: custom_icon(second), "community artwork applied")
        checks["second_native_file_uses_approved_artwork"] = True
        capture("approved-artwork-in-native-client")
        action("App Faces", "Restore previous")
        wait(lambda: not custom_icon(second), "consumer Undo")
        checks["consumer_undo_restores_baseline"] = True
        bridge("revoke", app_name)
        assert submission_status(receipt)["status"] == "revoked"
        checks["browser_revocation_visible_to_client"] = True
        action("App Faces", "App Faces", "frame", "window.close")
        capture("files-after-restoration")
        result = {
            "passed": True,
            "checks": checks,
            "environment": "isolated Xvfb display + private D-Bus, real Nautilus/GTK/Firefox and production Worker",
            "fixtureOnly": True,
            "applicationsExecuted": False,
            "screenshots": "local only",
        }
        (ARTIFACTS / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    except Exception as error:
        if args.upstream_fixture:
            (ARTIFACTS / "upstream-result.json").write_text(
                json.dumps({"passed": False, "failure": str(error)}, indent=2) + "\n"
            )
        capture("failure")
        names = []
        for app in children(Atspi.get_desktop(0)):
            for w in children(app):
                names.extend(
                    {"window": w.get_name(), "role": n.get_role_name(), "name": n.get_name()}
                    for n in walk(w)
                    if n.get_name()
                )
        (ARTIFACTS / "failure-ui.json").write_text(json.dumps(names, ensure_ascii=False, indent=2))
        raise
    finally:
        for item in submissions():
            if item["name"] == app_name and item["sent"]:
                try:
                    status = submission_status(item["id"])["status"]
                    if status in {"pending", "correction"}:
                        revise_submission(item["id"])
                    elif status == "approved":
                        bridge("revoke", app_name)
                except Exception:
                    recovery = Path.home() / ".local/state/app-faces/e2e-recovery" / app_id
                    recovery.mkdir(parents=True, exist_ok=True, mode=0o700)
                    shutil.copytree(
                        root / "data/app-faces/outbox", recovery / "outbox", dirs_exist_ok=True
                    )
                    for saved in (recovery / "outbox").glob("*"):
                        saved.chmod(0o600)
                    print(f"Cleanup incomplete; private receipt retained at {recovery}", flush=True)
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()


if __name__ == "__main__":
    main()

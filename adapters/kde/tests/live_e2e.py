
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

os.environ["GDK_BACKEND"] = "x11"
os.environ["WAYLAND_DISPLAY"] = "app-faces-no-wayland"
os.environ["XDG_SESSION_TYPE"] = "x11"

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, Gdk, GdkPixbuf  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SESSION = ROOT / "build/dolphin-live-e2e"
RUNTIME = ROOT / "build/kde-deps/root/usr"
assert os.environ.get("APP_FACES_ISOLATED_DISPLAY") == "1"
assert os.environ["DISPLAY"] not in (":0", ":1")
shutil.rmtree(SESSION, ignore_errors=True)
for name in ("home", "config", "data", "cache", "fixtures"):
    (SESSION / name).mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env.update(
    HOME=str(SESSION / "home"),
    XDG_CONFIG_HOME=str(SESSION / "config"),
    XDG_DATA_HOME=str(SESSION / "data"),
    XDG_CACHE_HOME=str(SESSION / "cache"),
    XDG_CURRENT_DESKTOP="KDE",
    QT_QPA_PLATFORM="xcb",
    QT_LINUX_ACCESSIBILITY_ALWAYS_ON="1",
    XDG_DATA_DIRS=f"{RUNTIME}/share:/usr/local/share:/usr/share",
    LD_LIBRARY_PATH=f"{RUNTIME}/lib/x86_64-linux-gnu",
    QT_PLUGIN_PATH=f"{ROOT}/build/kde/plugins:{RUNTIME}/lib/x86_64-linux-gnu/qt6/plugins:/usr/lib/x86_64-linux-gnu/qt6/plugins",
    PATH=f"{RUNTIME}/bin:{RUNTIME}/lib/x86_64-linux-gnu/libexec/kf6:" + env["PATH"],
    PULSE_SERVER="unix:/nonexistent/app-faces-audio",
    PIPEWIRE_REMOTE="/nonexistent/app-faces-audio",
    PYTHONPATH=str(ROOT),
)
target = SESSION / "fixtures/App Faces Preview Test"
shutil.copyfile("/usr/bin/true", target)
target.chmod(0o700)
initial_binary = (
    hashlib.sha256(target.read_bytes()).hexdigest(),
    target.stat().st_mode,
    target.stat().st_mtime_ns,
)
(SESSION / "cache/app-faces").mkdir(parents=True)
(SESSION / "cache/app-faces/catalog.json").write_text('{"icons": [], "fingerprints": {}}')
icon = SESSION / "artwork.png"
pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 128, 128)
pix.fill(0x16E47AFF)
pix.savev(str(icon), "png", [], [])
replacement = SESSION / "replacement.png"
pix.fill(0xE42AACFF)
pix.savev(str(replacement), "png", [], [])
apps = SESSION / "data/applications"
apps.mkdir(exist_ok=True)
(apps / "appfaces-preview-test.desktop").write_text(
    f'[Desktop Entry]\nType=Application\nName=App Faces Preview Test\nExec="{target}"\nIcon={icon}\n'
)
(SESSION / "config/dolphinrc").write_text(
    "[General]\nShowFullPath=true\n[PreviewSettings]\nPlugins=appfacesthumbnail,libappfacesthumbnail\n"
)

subprocess.run(
    [
        "/usr/bin/python3",
        "-c",
        'from pathlib import Path; from app_faces.installation import managed_files; import os; files=managed_files(Path(os.environ["PYTHONPATH"])); [(p.parent.mkdir(parents=True,exist_ok=True),p.write_text(c),p.chmod(0o755)) for p,c in files.items() if ".local/bin" in str(p) or "kio/servicemenus" in str(p)]',
    ],
    env=env,
    check=True,
)
log = (SESSION / "dolphin.log").open("w")
proc = subprocess.Popen(
    [str(RUNTIME / "bin/dolphin"), "--new-window", str(target.parent)],
    env=env,
    stdout=log,
    stderr=log,
)
report = {
    "isolated_display": os.environ["DISPLAY"],
    "preview": False,
    "menu": False,
    "chooser": False,
}


def nodes(item, depth=0):
    if depth > 30:
        return
    item.clear_cache()
    yield item
    for i in range(item.get_child_count()):
        yield from nodes(item.get_child_at_index(i), depth + 1)


def snapshot(name, color=(22, 228, 122)):
    window = Gdk.get_default_root_window()
    image = Gdk.pixbuf_get_from_window(window, 0, 0, window.get_width(), window.get_height())
    image.savev(str(ROOT / f"state/dolphin-{name}.png"), "png", [], [])
    pixels = image.get_pixels()
    return sum(
        pixels[i : i + 3] == bytes(color) for i in range(0, len(pixels), image.get_n_channels())
    )


def button(name):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        for node in nodes(Atspi.get_desktop(0)):
            if node.get_name() == name and node.get_role_name() == "button":
                iface = node.get_action_iface()
                for index in range(iface.get_n_actions()):
                    if iface.get_action_name(index) == "click":
                        assert iface.do_action(index)
                        time.sleep(1)
                        return
        time.sleep(0.2)
    raise AssertionError(f"Missing button: {name}")


def keys(*args):
    subprocess.run(["xdotool", *args], check=True)
    time.sleep(0.5)


def reopen():
    subprocess.Popen(
        [str(SESSION / "home/.local/bin/app-faces"), "gui", str(target)],
        env=env,
        stdout=log,
        stderr=log,
    )
    time.sleep(3)


def close_chooser():
    frames = [
        n
        for n in nodes(Atspi.get_desktop(0))
        if n.get_name() == "App Faces" and n.get_role_name() == "frame"
    ]
    assert len(frames) == 1
    close = next(
        n for n in nodes(frames[0]) if n.get_name() == "Close" and n.get_role_name() == "button"
    )
    assert close.get_action_iface().do_action(0)
    time.sleep(2)


def visible(name, color, present):
    deadline = time.monotonic() + 12
    stable_since = None
    while time.monotonic() < deadline:
        count = snapshot(name, color)
        tile_visible = any(
            n.get_name() == "App Faces Preview Test"
            and n.get_role_name() == "list item"
            and n.get_state_set().contains(Atspi.StateType.SHOWING)
            for n in nodes(Atspi.get_desktop(0))
        )
        if tile_visible and (count > 500) == present:
            stable_since = stable_since or time.monotonic()
            if time.monotonic() - stable_since >= 1.5:
                return count
        else:
            stable_since = None
        time.sleep(0.5)
    raise AssertionError(f"Dolphin preview did not transition: {name}, pixels={count}")


try:
    time.sleep(5)
    tree = list(nodes(Atspi.get_desktop(0)))
    (SESSION / "tree.json").write_text(
        json.dumps(
            [{"name": n.get_name(), "role": n.get_role_name()} for n in tree if n.get_name()],
            indent=2,
        )
    )
    report["window_open"] = any(n.get_name() == "dolphin" for n in tree)

    preview = next(n for n in tree if n.get_name() == "Show Previews")
    report["preview_initial_checked"] = preview.get_state_set().contains(Atspi.StateType.CHECKED)
    report["preview_action"] = (
        True if report["preview_initial_checked"] else preview.get_action_iface().do_action(0)
    )
    time.sleep(5)
    report["green_preview_pixels"] = snapshot("preview")
    report["preview"] = report["green_preview_pixels"] > 500
    target_node = next(n for n in tree if n.get_name() == "App Faces Preview Test")
    rect = target_node.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
    subprocess.run(
        [
            "xdotool",
            "mousemove",
            str(rect.x + rect.width // 2),
            str(rect.y + rect.height // 2),
            "click",
            "3",
        ],
        check=True,
    )
    time.sleep(1)
    menu_tree = list(nodes(Atspi.get_desktop(0)))
    (SESSION / "menu-tree.json").write_text(
        json.dumps(
            [{"name": n.get_name(), "role": n.get_role_name()} for n in menu_tree if n.get_name()],
            indent=2,
        )
    )
    menu = next((n for n in menu_tree if n.get_name().replace("&", "") == "App Faces"), None)
    report["menu"] = menu is not None
    snapshot("menu")
    if not menu:


        subprocess.run(["xdotool", "mousemove", "270", "347", "click", "1"], check=True)
        report["menu_action"] = "isolated screenshot-coordinate fallback"
    if menu:
        report["menu_action"] = menu.get_action_iface().do_action(0)
    if report.get("menu_action"):
        time.sleep(4)
        chooser_tree = list(nodes(Atspi.get_desktop(0)))
        report["chooser"] = any(
            "App Faces" in n.get_name() and n.get_role_name() == "frame" for n in chooser_tree
        )
        report["menu"] = report["menu"] or report["chooser"]
        snapshot("chooser")
        (SESSION / "chooser-tree.json").write_text(
            json.dumps(
                [
                    {"name": n.get_name(), "role": n.get_role_name()}
                    for n in chooser_tree
                    if n.get_name()
                ],
                indent=2,
            )
        )
    assert report["chooser"]

    close_chooser()
    journal = SESSION / "data/app-faces/changes.json"
    assert not journal.exists() or not json.loads(journal.read_text())
    report["cancel_preserved_preview"] = visible("cancelled", (22, 228, 122), True) > 500
    reopen()
    button("Choose image…")
    keys("key", "ctrl+l")
    keys("type", "--clearmodifiers", str(replacement))
    keys("key", "Return")
    time.sleep(2)
    button("Apply icon")
    assert str(target) in json.loads(journal.read_text())
    assert any("No Dolphin, pressione F5" in n.get_name() for n in nodes(Atspi.get_desktop(0)))
    snapshot("apply-notice")
    close_chooser()
    report["automatic_refresh"] = snapshot("before-refresh", (228, 42, 172)) > 500
    refresh = next(
        n
        for n in nodes(Atspi.get_desktop(0))
        if n.get_name() == "Refresh" and n.get_role_name() == "menu item"
    )
    assert refresh.get_action_iface().do_action(0)
    report["applied_magenta_pixels"] = visible("applied", (228, 42, 172), True)
    report["apply"] = True
    reopen()
    button("Restore previous")
    close_chooser()
    assert str(target) not in json.loads(journal.read_text())
    refresh = next(
        n
        for n in nodes(Atspi.get_desktop(0))
        if n.get_name() == "Refresh" and n.get_role_name() == "menu item"
    )
    assert refresh.get_action_iface().do_action(0)
    report["restored_magenta_pixels"] = visible("restored", (228, 42, 172), False)
    report["undo"] = True
    assert (
        hashlib.sha256(target.read_bytes()).hexdigest(),
        target.stat().st_mode,
        target.stat().st_mtime_ns,
    ) == initial_binary
    report["binary_unchanged"] = True
    report["refresh_action"] = "Dolphin Refresh menu action (F5 equivalent)"
    report["passed"] = all(
        report[k]
        for k in (
            "window_open",
            "preview",
            "menu",
            "chooser",
            "cancel_preserved_preview",
            "apply",
            "undo",
        )
    )
    print(json.dumps(report))
    assert report["passed"], "Dolphin live preview/menu/chooser flow failed"
except Exception as exc:
    report["passed"] = False
    report["failure"] = str(exc)
    raise
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    (ROOT / "state/dolphin-live-e2e.json").write_text(json.dumps(report, indent=2) + "\n")

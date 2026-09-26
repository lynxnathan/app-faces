#!/usr/bin/python3

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GioUnix", "2.0")
from gi.repository import Gio, GioUnix  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app_faces.launchers import add_launcher, remove_launcher  # noqa: E402

STATE = ROOT / "state/dock-e2e"
EXE = ROOT / "build/portable-fixtures/Godot/Godot_v4.7.2-stable_linux.x86_64"
ICON = ROOT / "state/native-e2e/upstream-applied-icon.png"


class DesktopBusy(RuntimeError):
    """The user's foreground activity prevents visual acceptance, not a product failure."""


def snapshot(stage, pids, launcher="app-faces-dock-e2e.desktop", screenshot=False, **actions):
    stage = f"{stage}-{time.monotonic_ns()}"
    request = STATE / "request.json"
    temp = request.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            dict(stage=stage, pids=pids, launcher=launcher, screenshot=screenshot, **actions)
        )
    )
    temp.replace(request)
    output = STATE / f"{stage}.json"
    for _ in range(100):
        if output.exists():
            return json.loads(output.read_text())
        time.sleep(0.1)
    raise RuntimeError(f"Shell observer did not return {stage}")


def main():
    import shlex

    assert os.getuid() != 0
    assert EXE.is_file() and ICON.is_file()
    report = {"passed": False, "cases": [], "screenshots": "local only"}
    try:
        for driver in ("wayland", "x11"):
            owned = []
            launcher = None
            build = ROOT / "build/dock-e2e" / driver
            build.mkdir(parents=True, exist_ok=True)
            pidfile = build / "pid"
            wrapper = build / "godot-test"
            lines = ["#!/bin/sh", "set -eu", f"echo $$ > {shlex.quote(str(pidfile))}"]
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                path = build / key.lower()
                path.mkdir(exist_ok=True)
                lines.append(f"export {key}={shlex.quote(str(path))}")
            for key, value in {
                "PULSE_SERVER": "unix:/run/agent-audio-disabled/native",
                "PIPEWIRE_REMOTE": "/run/agent-audio-disabled/pipewire-0",
                "ALSA_CONFIG_PATH": "/usr/local/lib/agent-silence/alsa.conf",
            }.items():
                lines.append(f"export {key}={shlex.quote(value)}")
            lines.append(
                "exec "
                + shlex.join(
                    [
                        str(EXE),
                        "--project-manager",
                        "--display-driver",
                        driver,
                        "--rendering-method",
                        "gl_compatibility",
                        "--audio-driver",
                        "Dummy",
                    ]
                )
                + " > "
                + shlex.quote(str(build / "godot.log"))
                + " 2>&1"
            )
            wrapper.write_text("\n".join(lines) + "\n")
            wrapper.chmod(0o700)

            def wait_view(label, pids, predicate, identity="app-faces-dock-e2e.desktop"):
                for _ in range(50):
                    view = snapshot(f"{driver}-{label}", pids, identity)
                    if predicate(view):
                        return view
                    time.sleep(0.2)
                if (view["dock"] and not any(x["actor"]["mapped"] for x in view["dock"])) or (
                    label == "search-visible"
                    and (
                        not view.get("overviewVisible")
                        or view.get("searchDebug", {}).get("text") != "App Faces Dock E2E"
                    )
                ):
                    raise DesktopBusy("Personal desktop is in use; visual check was not completed")
                snapshot(f"{driver}-{label}-failure", pids, identity, screenshot=True)
                raise AssertionError(f"{driver} {label}: {view}")

            def close_owned():
                for pid in owned:
                    try:
                        if Path(f"/proc/{pid}/exe").resolve() == EXE:
                            os.kill(pid, 15)
                    except FileNotFoundError, ProcessLookupError:
                        pass
                for _ in range(30):
                    if not any(Path(f"/proc/{pid}/exe").exists() for pid in owned):
                        break
                    time.sleep(0.1)
                assert not any(Path(f"/proc/{pid}/exe").exists() for pid in owned), (
                    "Test process did not stop"
                )
                owned.clear()

            try:
                process = subprocess.Popen([str(wrapper)])
                owned.append(process.pid)
                baseline = wait_view("baseline", owned, lambda r: len(r["windows"]) == 1)
                identity = baseline["windows"][0]["wmClass"]
                assert identity
                assert baseline["windows"][0]["app"].startswith("window:"), baseline
                baseline = snapshot(f"{driver}-generic", owned, screenshot=True)
                close_owned()
                process.wait(timeout=5)
                launcher = add_launcher(
                    wrapper,
                    "App Faces Dock E2E " + driver,
                    str(ICON),
                    application_id=identity,
                    wm_class=identity,
                )
                assert not launcher.reused
                desktop_id = launcher.path.name
                registered = wait_view(
                    "registered",
                    [],
                    lambda r: (
                        r["launcherExists"] and any(desktop_id in group for group in r["search"])
                    ),
                    desktop_id,
                )
                info = GioUnix.DesktopAppInfo.new_from_filename(str(launcher.path))
                expected_icon = info.get_icon().to_string()
                snapshot(f"{driver}-search-open", [], desktop_id, showSearch=True)
                wait_view(
                    "search-visible", [], lambda r: len(r["visualSearchResults"]) == 1, desktop_id
                )
                visual_search = snapshot(f"{driver}-search", [], desktop_id, screenshot=True)
                for number in (1, 2):
                    pidfile.unlink(missing_ok=True)
                    if number == 1:
                        snapshot(f"{driver}-search-click", [], desktop_id, clickResult=True)
                    else:
                        assert info.launch([], Gio.AppLaunchContext())
                    for _ in range(50):
                        if pidfile.exists() and pidfile.read_text().strip():
                            break
                        time.sleep(0.1)
                    owned.append(int(pidfile.read_text()))
                    view = wait_view(
                        f"grouped-{number}",
                        owned,
                        lambda r: (
                            len(r["windows"]) == number
                            and all(w["app"] == desktop_id for w in r["windows"])
                            and len(r["dock"]) == 1
                            and r["dock"][0]["windows"] == number
                            and r["dock"][0]["actor"]["mapped"]
                        ),
                        desktop_id,
                    )
                    assert view["dock"][0]["icon"] == expected_icon, view
                    assert view["dock"][0]["renderedGicon"] == expected_icon, view
                applied = snapshot(f"{driver}-applied", owned, desktop_id, screenshot=True)
                close_owned()
                wait_view("closed", [], lambda r: not r["dock"], desktop_id)
                remove_launcher(launcher.path)
                launcher = None
                removed = wait_view(
                    "removed",
                    [],
                    lambda r: (
                        not r["launcherExists"]
                        and not any(desktop_id in group for group in r["search"])
                    ),
                    desktop_id,
                )
                snapshot(f"{driver}-removed-search-open", [], desktop_id, showSearch=True)
                time.sleep(1)
                removed_search = snapshot(
                    f"{driver}-removed-search", [], desktop_id, screenshot=True
                )
                assert not removed_search["visualSearchResults"], removed_search
                snapshot(f"{driver}-search-close", [], desktop_id, hideSearch=True)
                process = subprocess.Popen([str(wrapper)])
                owned.append(process.pid)
                restored = wait_view(
                    "restored",
                    owned,
                    lambda r: (
                        len(r["windows"]) == 1 and r["windows"][0]["app"].startswith("window:")
                    ),
                )
                assert restored["dock"][0]["renderedGicon"] == "application-x-executable", restored
                restored = snapshot(f"{driver}-restored", owned, desktop_id, screenshot=True)
                close_owned()
                process.wait(timeout=5)
                case = {
                    "driver": driver,
                    "baseline": baseline,
                    "registered": registered,
                    "applied": applied,
                    "removed": removed,
                    "restored": restored,
                    "twoWindowsOneDockEntry": True,
                    "actualDockGiconMatchesManagedIcon": True,
                    "visualSearch": visual_search,
                    "removedVisualSearch": removed_search,
                    "launchedByVisibleSearchResultClick": True,
                }
                report["cases"].append(case)
                print(
                    json.dumps({"driver": driver, "passed": True, "desktopId": desktop_id}),
                    flush=True,
                )
            finally:
                close_owned()
                if launcher is not None:
                    remove_launcher(launcher.path)
        report["passed"] = True
    except DesktopBusy as error:
        report.update(disposition="desktop-in-use", error=str(error), productFailure=False)
        raise
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        (STATE / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        (STATE / "request.json").write_text(json.dumps({"stage": "stop-complete", "stop": True}))


if __name__ == "__main__":
    try:
        main()
    except DesktopBusy as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(77) from None

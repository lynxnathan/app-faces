import fcntl
import hashlib
import json
import os
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gi.repository import GLib

from .core import GROUP, atomic_json, data_dir, desktop_dirs, desktop_entries


@dataclass(frozen=True)
class LauncherResult:
    path: Path
    reused: bool


def exec_argument(value: str) -> str:
    if any(ord(c) < 32 for c in value):
        raise ValueError("Control characters are not supported in executable paths")
    value = value.replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return '"' + value + '"'


@contextmanager
def launcher_journal() -> Iterator[tuple[Path, dict[str, Any]]]:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    file = root / "launchers.json"
    with (root / "launchers.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = json.loads(file.read_text()) if file.exists() else {}
        yield file, records


def add_launcher(
    path: Path,
    name: str,
    icon: str,
    application_id: str = "",
    wm_class: str = "",
    applications_dir: Path | None = None,
    search_dirs: Sequence[Path] | None = None,
) -> LauncherResult:
    path = path.absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Select an executable regular file")
    matches = [e for e in desktop_entries(search_dirs) if e["executable"] == path.resolve()]
    if len(matches) > 1:
        raise ValueError("Multiple existing launchers; choose the existing entry explicitly")
    if matches:
        return LauncherResult(Path(matches[0]["file"]), True)
    if not name.strip() or not icon.strip():
        raise ValueError("Name and icon are required")
    if application_id and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,199}", application_id):
        raise ValueError("Invalid application ID")
    if any(ord(c) < 32 for c in name + icon + wm_class):
        raise ValueError("Control characters are not supported in launcher fields")
    identity = application_id.removesuffix(".desktop") or (
        "app-faces-" + hashlib.sha256(os.fsencode(path)).hexdigest()[:20]
    )
    target = (applications_dir or desktop_dirs()[0]) / (identity + ".desktop")

    for directory in search_dirs if search_dirs is not None else desktop_dirs():
        if (directory / target.name).exists():
            raise ValueError("Application ID already belongs to another desktop entry")
    if icon.startswith(("/", "file://")):
        from .state import store_icon

        icon = str(store_icon(icon))
    keyfile = GLib.KeyFile()
    for key, value in {
        "Type": "Application",
        "Name": name,
        "Exec": exec_argument(str(path)),
        "Icon": icon,
        "X-AppFaces-Managed": "true",
    }.items():
        keyfile.set_string(GROUP, key, value)
    keyfile.set_boolean(GROUP, "Terminal", False)
    if wm_class:
        keyfile.set_string(GROUP, "StartupWMClass", wm_class)
    content = str(keyfile.to_data()[0]).encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with launcher_journal() as (file, records):
        if target.exists() or target.is_symlink():
            raise ValueError("Launcher already exists; refusing to overwrite it")

        with target.open("xb") as handle:
            records[str(target)] = {"sha256": hashlib.sha256(content).hexdigest()}
            atomic_json(file, records)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    return LauncherResult(target, False)


def remove_launcher(path: Path) -> None:
    path = path.absolute()
    with launcher_journal() as (file, records):
        record = records.get(str(path))
        if not record:
            raise ValueError("This launcher is not managed by App Faces")
        if path.is_symlink():
            raise ValueError("Launcher changed outside App Faces; preserved")
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("Launcher changed outside App Faces; preserved")
            path.unlink()
        del records[str(path)]
        atomic_json(file, records)


def rollback_launchers() -> dict[str, list[str]]:
    with launcher_journal() as (_, records):
        paths = list(records)
    report: dict[str, list[str]] = {"removed": [], "preserved": []}
    for path in paths:
        try:
            remove_launcher(Path(path))
            report["removed"].append(path)
        except OSError, ValueError:
            report["preserved"].append(path)
    return report

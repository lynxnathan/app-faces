import fcntl
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from gi.repository import GLib

from .core import atomic_json, data_dir
from .launchers import exec_argument

MAX_INSTALL_SOURCE_BYTES = 32_000_000
MARKER = "# App Faces managed launcher"


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def managed_files(root: Path) -> dict[Path, str]:
    root = root.absolute()
    if any(ord(c) < 32 for c in str(root)):
        raise ValueError("Control characters are not supported in installation paths")
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    command = f"PYTHONPATH={shlex.quote(str(root))} /usr/bin/python3 -m app_faces.cli"
    unit_root = str(root).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    menu = GLib.KeyFile()
    for key, value in {
        "Type": "Service",
        "MimeType": "application/octet-stream;application/x-executable;application/x-pie-executable;application/vnd.appimage;",
        "Actions": "AppFaces;",
        "X-KDE-Protocols": "file",
        "X-KDE-RequiredNumberOfUrls": "1",
    }.items():
        menu.set_string("Desktop Entry", key, value)
    for key, value in {
        "Name": "App Faces",
        "Icon": "preferences-desktop-icons",
        "Exec": exec_argument(str(home / ".local/bin/app-faces")) + " gui %f",
    }.items():
        menu.set_string("Desktop Action AppFaces", key, value)
    files = {
        home / ".local/bin/app-faces": f'#!/bin/sh\n{MARKER}\nexec env {command} "$@"\n',
        data / "nautilus/scripts/App Faces": f"""#!/bin/sh
{MARKER}
if [ "$#" -ne 1 ]; then
    exec env PYTHONPATH={shlex.quote(str(root))} /usr/bin/python3 -m app_faces.selection
fi
exec env {command} gui "$1"
""",
        config / "systemd/user/app-faces.service": f"""{MARKER}
[Unit]
Description=App Faces automatic application artwork
After=graphical-session.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -m app_faces.cli automatic
Environment="PYTHONPATH={unit_root}"
Environment=PULSE_SERVER=unix:/nonexistent/app-faces-audio
Environment=PIPEWIRE_REMOTE=/nonexistent/app-faces-audio
Nice=10
TimeoutStartSec=180
UMask=0077
""",
        config / "systemd/user/app-faces.timer": f"""{MARKER}
[Unit]
Description=Refresh application artwork quietly
[Timer]
OnStartupSec=20s
OnUnitInactiveSec=60s
AccuracySec=10s
[Install]
WantedBy=timers.target
""",
        data / "kio/servicemenus/app-faces.desktop": MARKER + "\n" + str(menu.to_data()[0]),
    }
    return files


def systemctl(*args: str, missing_ok: bool = False) -> None:
    result = subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
        check=False,
    )
    if result.returncode:
        absent = any(
            text in result.stderr
            for text in (
                "does not exist",
                "not loaded",
                "not found",
            )
        )
        if not (missing_ok and absent):
            raise subprocess.CalledProcessError(
                result.returncode, result.args, result.stdout, result.stderr
            )


@contextmanager
def installation_manifest() -> Iterator[tuple[Path, dict[str, Any]]]:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    file = root / "installation.json"
    with (root / "installation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = json.loads(file.read_text()) if file.exists() else {"files": {}}
        yield file, manifest


def _owned_content(path: Path, record: dict[str, Any]) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    return digest(path.read_bytes()) in {record["sha256"], record.get("previous_sha256")}


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(root: Path, activate: bool = True) -> dict[str, Any]:
    files = managed_files(root)
    with installation_manifest() as (manifest_file, manifest):
        for path, text in files.items():
            if path.is_symlink():
                raise ValueError(f"Refusing to replace a symlink: {path}")
            if path.exists():
                known = manifest["files"].get(str(path))
                if known and not _owned_content(path, known):
                    raise ValueError(f"Installed file was edited; preserving it: {path}")

                if not known and (not path.is_file() or path.read_bytes() != text.encode()):
                    raise ValueError(f"Refusing to overwrite an unrelated file: {path}")
        for path, text in files.items():
            record = {"sha256": digest(text.encode())}
            if path.is_file():
                record["previous_sha256"] = digest(path.read_bytes())
            manifest["files"][str(path)] = record

            atomic_json(manifest_file, dict(manifest, root=str(root.absolute()), version=1))
            _atomic_write(
                path, text.encode(), 0o755 if path.suffix not in {".service", ".timer"} else 0o644
            )
            record.pop("previous_sha256", None)
            atomic_json(manifest_file, dict(manifest, root=str(root.absolute()), version=1))
        if activate:
            systemctl("daemon-reload")
            systemctl("enable", "--now", "app-faces.timer")
    return {"installed": list(map(str, files)), "service_activated": activate}


def uninstall(activate: bool = True, restore: bool = True) -> dict[str, Any]:
    from .launchers import rollback_launchers
    from .state import rollback_all

    with installation_manifest() as (manifest_file, manifest):
        if activate:
            systemctl("disable", "--now", "app-faces.timer", missing_ok=True)
            systemctl("stop", "app-faces.service", missing_ok=True)
        icons = rollback_all() if restore else {"retained": "explicit keep-icons option"}
        launchers = rollback_launchers()
        result: dict[str, Any] = dict(icons=icons, launchers=launchers, removed=[], preserved=[])
        for key, record in list(manifest["files"].items()):
            path = Path(key)
            if path.exists() or path.is_symlink():
                if not _owned_content(path, record):
                    result["preserved"].append(key)
                    continue
                path.unlink()
                result["removed"].append(key)
            manifest["files"].pop(key)
            atomic_json(manifest_file, manifest)
        atomic_json(manifest_file, manifest)
        if activate:
            systemctl("daemon-reload")

    result["retained_data"] = str(data_dir())
    return result


def install_kde_plugin(source: Path, plugin_dir: Path) -> dict[str, str]:
    source = source.resolve(strict=True)
    if not source.is_file() or source.name != "libappfacesthumbnail.so":
        raise ValueError("Select the compiled libappfacesthumbnail.so plugin")
    if source.stat().st_size > MAX_INSTALL_SOURCE_BYTES:
        raise ValueError("Plugin exceeds the 32 MB size limit")
    content = source.read_bytes()
    if len(content) < 64 or content[:4] != b"\x7fELF" or content[4] not in {1, 2}:
        raise ValueError("Plugin is not a valid ELF shared-object header")
    if content[5] not in {1, 2}:
        raise ValueError("Plugin has an invalid ELF byte order")
    byte_order: Literal["little", "big"] = "little" if content[5] == 1 else "big"
    if int.from_bytes(content[16:18], byte_order) != 3:
        raise ValueError("Plugin must be an ELF shared object")
    if not plugin_dir.is_absolute():
        raise ValueError("Choose an absolute local Qt6 plugin directory")
    plugin_dir = plugin_dir.resolve()
    if not plugin_dir.is_relative_to(Path.home().resolve()):
        raise ValueError("Choose a user-local Qt6 plugin directory under your home")
    target = plugin_dir / "kf6/thumbcreator/libappfacesthumbnail.so"

    if not target.parent.resolve().is_relative_to(Path.home().resolve()):
        raise ValueError("Plugin directory resolves outside your home")
    with installation_manifest() as (manifest_file, manifest):
        if target.is_symlink():
            raise ValueError("Refusing to replace a symlink plugin")
        known = manifest["files"].get(str(target))
        if target.exists():
            if known and not _owned_content(target, known):
                raise ValueError("Installed plugin was edited; preserving it")
            if not known and (not target.is_file() or target.read_bytes() != content):
                raise ValueError("Refusing to overwrite an unrelated plugin")
        record = {"sha256": digest(content)}
        if target.is_file():
            record["previous_sha256"] = digest(target.read_bytes())
        manifest["files"][str(target)] = record
        atomic_json(manifest_file, manifest)
        _atomic_write(target, content, 0o644)
        record.pop("previous_sha256", None)
        atomic_json(manifest_file, manifest)
    return {
        "installed": str(target),
        "plugin_root": str(plugin_dir),
        "discovery": "Qt6 must already search this root, or add it to QT_PLUGIN_PATH",
    }

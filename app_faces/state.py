import base64
import errno
import fcntl
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from .core import ATTR, atomic_json, custom_icon, data_dir, icon_path
from .i18n import t

REFRESH_ATTRIBUTE = "user.app-faces.icon"
KDE_REFRESH_NOTICE = t("In Dolphin, press F5 to refresh the icon preview.")
REFRESH_NOTICE = t("Refresh the folder if the file icon has not changed.")


@contextmanager
def marker_file(path: Path, record: dict[str, Any]) -> Iterator[int]:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
    try:
        stat = os.fstat(descriptor)
        if stat.st_ino != record["inode"] or stat.st_dev != record["device"]:
            raise OSError(errno.ESTALE, "File was replaced; refresh marker preserved")
        yield descriptor
    finally:
        os.close(descriptor)


def read_marker(descriptor: int) -> str | None:
    try:
        return base64.b64encode(os.getxattr(descriptor, REFRESH_ATTRIBUTE)).decode("ascii")
    except OSError as exc:
        if exc.errno == errno.ENODATA:
            return None
        raise


def plan_marker(path: Path, record: dict[str, Any], old: dict[str, Any] | None) -> dict[str, Any]:
    try:
        with marker_file(path, record) as descriptor:
            current = read_marker(descriptor)
        prior = old.get("refresh_marker", {}) if old else {}
        owned = "applied" in prior and current == prior["applied"]
        if prior.get("status") in {"applied", "planned", "restore_failed"} and not owned:
            return {"status": "external", "reason": "Later marker edits were preserved"}
        return dict(
            status="planned",
            previous=prior["previous"] if owned else current,
            expected=current,
            owned_before=owned,
            applied=base64.b64encode(record["applied"].encode()).decode("ascii"),
        )
    except OSError as exc:
        return dict(status="unavailable", reason=str(exc))


def apply_marker(path: Path, record: dict[str, Any]) -> None:
    marker = record["refresh_marker"]
    if marker.get("status") != "planned":
        return
    try:
        with marker_file(path, record) as descriptor:
            if read_marker(descriptor) != marker["expected"]:
                marker.update(status="external", reason="Later marker edits were preserved")
                return
            os.setxattr(descriptor, REFRESH_ATTRIBUTE, base64.b64decode(marker["applied"]))
        marker["status"] = "applied"
    except OSError as exc:
        marker.update(status="unavailable", reason=str(exc))


def restore_marker(path: Path, record: dict[str, Any]) -> tuple[bool, bool]:
    marker = record.get("refresh_marker", {})
    if "applied" not in marker:
        return True, False
    try:
        with marker_file(path, record) as descriptor:
            current = read_marker(descriptor)
            owned = current == marker["applied"] or (
                marker.get("owned_before") and current == marker["expected"]
            )
            if not owned:
                marker["status"] = "restored" if current == marker["previous"] else "external"
                return True, False
            previous = marker["previous"]
            if previous is None:
                os.removexattr(descriptor, REFRESH_ATTRIBUTE)
            else:
                os.setxattr(descriptor, REFRESH_ATTRIBUTE, base64.b64decode(previous))
        marker["status"] = "restored"
        return True, True
    except OSError as exc:
        marker.update(status="restore_failed", reason=str(exc))
        return False, False


def refresh_warning(path: Path) -> str:
    with journal() as (_, changes):
        record = changes.get(str(path.absolute()), {})
    if record.get("backend", "gvfs") == "kde":
        return KDE_REFRESH_NOTICE
    return "" if record.get("refresh_marker", {}).get("status") == "applied" else REFRESH_NOTICE


def backend_name() -> str:
    return "kde" if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() else "gvfs"


def set_metadata(path: Path, value: str) -> None:
    file = Gio.File.new_for_path(str(path))
    if value:
        file.set_attribute_string(ATTR, value, Gio.FileQueryInfoFlags.NONE, None)
    else:
        info = Gio.FileInfo()
        info.set_attribute(ATTR, Gio.FileAttributeType.INVALID, 0)
        file.set_attributes_from_info(info, Gio.FileQueryInfoFlags.NONE, None)


@contextmanager
def journal() -> Iterator[tuple[Path, dict[str, Any]]]:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    file = root / "changes.json"
    with (root / "changes.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        changes = json.loads(file.read_text()) if file.exists() else {}
        yield file, changes


def signature(path: Path) -> dict[str, int]:
    stat = path.stat()
    return dict(inode=stat.st_ino, device=stat.st_dev, size=stat.st_size, mtime_ns=stat.st_mtime_ns)


def current_icon(path: Path, record: dict[str, Any] | None = None) -> str:
    if record and record.get("backend") == "kde":
        return str(record.get("applied", ""))
    return custom_icon(path)


def store_icon(icon: str) -> Path:
    asset = icon_path(icon)
    if asset is None:
        raise ValueError("Icon is unavailable; the existing desktop entry was preserved")
    from .community import png_bytes

    content = png_bytes(str(asset))
    stored = data_dir() / "artwork/local" / (hashlib.sha256(content).hexdigest() + ".png")
    stored.parent.mkdir(parents=True, exist_ok=True)
    if not stored.exists():
        stored.write_bytes(content)
    return stored


def apply(
    path: Path,
    icon: str,
    replace: bool = False,
    automatic: bool = False,
    backend: str | None = None,
) -> str:
    path = path.absolute()
    if not path.is_file():
        raise ValueError("Select a regular file")
    uri = store_icon(icon).absolute().as_uri()
    with journal() as (file, changes):
        key = str(path)
        old = changes.get(key)
        previous = current_icon(path, old)
        if (
            automatic
            and replace
            and (not old or old.get("mode") != "automatic" or previous != old["applied"])
        ):
            raise ValueError("Automatic ownership changed; preserving the current icon")
        if previous and not replace:
            raise ValueError("File already has a custom icon; explicit replacement is required")
        sig = signature(path)
        if (
            old
            and automatic
            and previous == uri
            and old.get("mode") == "automatic"
            and all(old.get(k) == v for k, v in sig.items())
        ):
            return uri
        same = (
            old
            and old["applied"] == previous
            and old["inode"] == sig["inode"]
            and old.get("device") == sig["device"]
        )
        original = old["previous"] if same and old is not None else previous
        entry = dict(
            previous=original,
            applied=uri,
            **sig,
            mode="automatic" if automatic else "manual",
            source_icon=icon,
            backend=backend or backend_name(),
        )
        if entry["backend"] == "gvfs":
            marker_owner = (
                old
                if old and old.get("inode") == sig["inode"] and old.get("device") == sig["device"]
                else None
            )
            entry["refresh_marker"] = plan_marker(path, entry, marker_owner)
        changes[key] = entry
        atomic_json(file, changes)
        try:
            if entry["backend"] == "gvfs":
                set_metadata(path, uri)
        except Exception:
            if old is None:
                changes.pop(key, None)
            else:
                changes[key] = old
            atomic_json(file, changes)
            raise
        if entry["backend"] == "gvfs":
            apply_marker(path, entry)
            atomic_json(file, changes)
        if not automatic:
            disabled_file = data_dir() / "disabled.json"
            disabled = json.loads(disabled_file.read_text()) if disabled_file.exists() else {}
            disabled.pop(key, None)
            atomic_json(disabled_file, disabled)
    return uri


def undo(path: Path, suppress: bool = True) -> str:
    path = path.absolute()
    with journal() as (file, changes):
        record = changes.get(str(path))
        if not record:
            raise ValueError("No App Faces change recorded for this path")
        if path.stat().st_ino != record["inode"] or path.stat().st_dev != record.get(
            "device", path.stat().st_dev
        ):
            raise ValueError("File was replaced; refusing to change its icon")
        current = current_icon(path, record)
        if current != record["applied"] and not (
            record.get("restoring") and current == record["previous"]
        ):
            raise ValueError("Icon changed outside App Faces; leaving it untouched")
        record["restoring"] = True
        atomic_json(file, changes)
        complete, notified = True, True
        if record.get("backend", "gvfs") == "gvfs":
            if current != record["previous"]:
                set_metadata(path, record["previous"])
            complete, notified = restore_marker(path, record)
        if suppress:
            disabled_file = data_dir() / "disabled.json"
            disabled = json.loads(disabled_file.read_text()) if disabled_file.exists() else {}
            disabled[str(path)] = path.stat().st_ino
            atomic_json(disabled_file, disabled)
        if complete:
            del changes[str(path)]
        atomic_json(file, changes)
        if record.get("backend") == "kde":
            return KDE_REFRESH_NOTICE
        return "" if notified else REFRESH_NOTICE


def rollback_all() -> dict[str, list[str]]:
    result: dict[str, list[str]] = dict(restored=[], preserved=[], missing=[])
    with journal() as (_, changes):
        records = dict(changes)
    for key in records:
        path = Path(key)
        if not path.exists():
            result["missing"].append(key)
            continue
        try:
            undo(path)
            with journal() as (_, remaining):
                recovery_pending = key in remaining
            if recovery_pending:
                result["preserved"].append(f"{key}: icon restored; refresh marker recovery pending")
            else:
                result["restored"].append(key)
        except (ValueError, OSError, GLib.Error) as exc:
            result["preserved"].append(f"{key}: {exc}")
    return result


def prepare_automatic(path: Path) -> tuple[bool, bool]:
    path = path.absolute()
    key = str(path)
    sig = signature(path)
    with journal() as (file, changes):
        record = changes.get(key)
        if not record:
            for previous, candidate in list(changes.items()):
                if (
                    not Path(previous).exists()
                    and candidate.get("inode") == sig["inode"]
                    and candidate.get("device") == sig["device"]
                ):
                    record = changes[key] = changes.pop(previous)
                    atomic_json(file, changes)
                    break
        current = current_icon(path, record)
        if not record:
            return not bool(current), False
        if record.get("mode", "manual") != "automatic":
            return False, False
        if current != record["applied"]:
            return False, False
        return True, True


def clear_automatic(path: Path) -> None:
    path = path.absolute()
    with journal() as (file, changes):
        record = changes.get(str(path))
        if not record or record.get("mode") != "automatic":
            return
        current = current_icon(path, record)
        if current != record["applied"] and not (
            record.get("restoring") and current == record["previous"]
        ):
            return
        stat = path.stat()
        same = stat.st_ino == record["inode"] and stat.st_dev == record.get("device", stat.st_dev)
        record["restoring"] = True
        atomic_json(file, changes)
        complete = True
        if record.get("backend", "gvfs") == "gvfs":
            set_metadata(path, record["previous"] if same else "")
            if same:
                complete, _ = restore_marker(path, record)
        if complete:
            changes.pop(str(path))
        atomic_json(file, changes)

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from .core import Resolver, Result, atomic_json, cache_dir, data_dir, fetch_icon, sync_catalog
from .state import apply, clear_automatic, prepare_automatic, signature

THRESHOLD = 0.90
EXACT_MATCH_SCORE = 1.0
APPIMAGE_NAME_SCORE = 0.92
NAME_ONLY_SCORE = 0.60
MAX_SCAN_DEPTH = 2
MAX_SCAN_ENTRIES = 10_000
MAX_SCAN_CANDIDATES = 2_000
CATALOG_REFRESH_SECONDS = 86_400
CATALOG_RETRY_SECONDS = 900
COMMUNITY_REFRESH_SECONDS = 300
FILE_SETTLE_SECONDS = 15
MAX_DOWNLOADS_PER_SCAN = 3
MAX_CACHED_RESOLUTIONS = 5_000
APPIMAGE_HEADER_BYTES = 12


def set_enabled(enabled: bool) -> None:
    from .community import settings

    file = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "app-faces/config.json"
    )
    atomic_json(file, dict(settings(), automatic_enabled=enabled))


def confidence(path: Path, result: Any) -> float:
    if result.status == "resolved" and result.method in {"desktop", "sha256", "bundle"}:
        return EXACT_MATCH_SCORE
    if result.status != "suggested" or result.method != "filename":
        return 0.0
    hits = result.candidates or []

    if len({item["slug"] for item in hits}) != 1:
        return 0.0
    try:
        with path.open("rb") as f:
            header = f.read(APPIMAGE_HEADER_BYTES)
    except OSError:
        return 0.0

    if (
        path.suffix.casefold() == ".appimage"
        and header[:4] == b"\x7fELF"
        and header[8:11] in {b"AI\x01", b"AI\x02"}
    ):
        return APPIMAGE_NAME_SCORE
    return NAME_ONLY_SCORE


def roots() -> list[Path]:
    config = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "app-faces/config.json"
    )
    if config.exists() and "directories" in json.loads(config.read_text()):
        return [Path(p).expanduser() for p in json.loads(config.read_text())["directories"]]
    result = [Path.home() / x for x in ("Downloads", "Desktop", "Applications", ".local/bin")]

    dirs_file = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "user-dirs.dirs"
    if dirs_file.exists():
        for line in dirs_file.read_text().splitlines():
            if line.startswith(("XDG_DOWNLOAD_DIR=", "XDG_DESKTOP_DIR=")):
                value = line.split("=", 1)[1].strip().strip('"').replace("$HOME", str(Path.home()))
                result.append(Path(value))

    return list(dict.fromkeys(p for p in result if p.is_absolute() and p != Path.home()))


def candidates(resolver: Resolver) -> list[Path]:
    found: set[Path] = set()

    for entry in resolver.entries:
        path = entry["executable"]
        if path and path.is_relative_to(Path.home()) and path.is_file():
            found.add(path)
    examined = 0
    for root in roots():
        if not root.is_dir() or root.is_symlink():
            continue
        for directory, dirs, files in os.walk(root, followlinks=False):
            depth = len(Path(directory).relative_to(root).parts)
            dirs[:] = [] if depth >= MAX_SCAN_DEPTH else [d for d in dirs if not d.startswith(".")]
            for name in files:
                examined += 1
                if examined > MAX_SCAN_ENTRIES:
                    return sorted(found)
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    continue
                if path.suffix.casefold() == ".appimage" or os.access(path, os.X_OK):
                    found.add(path)
                if len(found) >= MAX_SCAN_CANDIDATES:
                    return sorted(found)
    return sorted(found)


def run_once() -> dict[str, Any]:
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "automatic.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(applied=[], errors=[], examined=0, busy=True)
        return _run_once()


def _run_once() -> dict[str, Any]:
    summary: dict[str, Any] = {"applied": [], "errors": [], "examined": 0}
    catalog = cache_dir() / "catalog.json"
    attempt = cache_dir() / "refresh-attempt"
    from .upstreams import configuration_revision

    try:
        upstream_revision = configuration_revision()
    except (OSError, ValueError) as exc:
        summary["errors"].append(f"upstreams: {exc}")
        atomic_json(data_dir() / "last-run.json", dict(summary, finished_at=time.time()))
        return summary
    try:
        refresh = json.loads(attempt.read_text())
        if not isinstance(refresh, dict):
            refresh = {}
    except OSError, ValueError:
        refresh = {}
    now = time.time()
    due = (
        not catalog.exists()
        or now - catalog.stat().st_mtime > CATALOG_REFRESH_SECONDS
        or refresh.get("applied_configuration") != upstream_revision
        or bool(refresh.get("failed"))
    )
    retry = (
        refresh.get("attempted_configuration") != upstream_revision
        or now - refresh.get("attempted_at", 0) > CATALOG_RETRY_SECONDS
    )
    if due and retry:
        refresh.update(attempted_configuration=upstream_revision, attempted_at=now, failed=True)
        atomic_json(attempt, refresh)
        try:
            synced = sync_catalog()
            errors = synced.get("errors", [])
            summary["errors"].extend(f"catalog: {error}" for error in errors)
            if not errors:
                refresh.update(applied_configuration=upstream_revision, failed=False)
        except Exception as exc:
            summary["errors"].append(f"catalog: {exc}")
        atomic_json(attempt, refresh)
    from .community import drain_outbox, settings, sync_approved

    if settings().get("community_url"):
        try:
            summary["submissions"] = drain_outbox()
            community_file = data_dir() / "community-catalog.json"
            if (
                not community_file.exists()
                or time.time() - community_file.stat().st_mtime > COMMUNITY_REFRESH_SECONDS
            ):
                sync_approved()
        except Exception as exc:
            summary["errors"].append(f"community: {exc}")
    if settings().get("automatic_enabled", True) is False:
        return dict(summary, paused=True)
    resolver = Resolver()
    import hashlib

    from gi.repository import Gio

    theme = Gio.Settings.new("org.gnome.desktop.interface").get_string("icon-theme")
    desktop_revision = hashlib.sha256(
        json.dumps(resolver.entries, default=str, sort_keys=True).encode()
    ).hexdigest()
    community_file = data_dir() / "community-catalog.json"
    from .identity import catalog_paths

    appstream_revision = str(
        [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in catalog_paths() if p.exists()]
    )
    community_revision = (
        hashlib.sha256(community_file.read_bytes()).hexdigest() if community_file.exists() else ""
    )
    revision = (
        str(resolver.catalog.get("revision", ""))
        + desktop_revision
        + theme
        + community_revision
        + appstream_revision
        + upstream_revision
    )
    resolution_file = cache_dir() / "resolutions.json"
    try:
        resolutions = json.loads(resolution_file.read_text())
    except OSError, ValueError:
        resolutions = {}

    disabled_file = data_dir() / "disabled.json"
    disabled = json.loads(disabled_file.read_text()) if disabled_file.exists() else {}
    remaining_downloads = MAX_DOWNLOADS_PER_SCAN
    for path in candidates(resolver):
        summary["examined"] += 1
        try:
            stat = path.stat()
            if time.time() - stat.st_mtime < FILE_SETTLE_SECONDS:
                continue
            key = str(path.absolute())
            if disabled.get(key) == stat.st_ino:
                continue
            eligible, replace = prepare_automatic(path)
            if not eligible:
                continue
            stamp = dict(signature(path), revision=revision)
            cached = resolutions.get(key, {})
            if cached.get("signature") == stamp:
                result = Result(**cached["result"])
            else:
                result = resolver.resolve(
                    path, read_custom=False, fingerprint=bool(resolver.catalog.get("fingerprints"))
                )
                resolutions[key] = dict(signature=stamp, result=result.to_dict())
            score = confidence(path, result)
            if score < THRESHOLD:
                if replace:
                    clear_automatic(path)
                continue
            icon = result.icon
            if result.method == "filename":
                if remaining_downloads <= 0:
                    continue
                item = (result.candidates or [])[0]
                remaining_downloads -= 1
                icon = str(fetch_icon(item["provider"], item["slug"], item.get("source_revision")))
            after = path.stat()
            if (stat.st_ino, stat.st_size, stat.st_mtime_ns) != (
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                continue

            from .core import custom_icon, icon_path

            asset = icon_path(icon)
            if asset is None:
                summary.setdefault("skipped", []).append(
                    dict(path=str(path), reason="Existing desktop icon is unavailable")
                )
                continue
            current = custom_icon(path)
            if asset and current == asset.absolute().as_uri() and cached.get("signature") == stamp:
                continue
            if settings().get("automatic_enabled", True) is False:
                break
            apply(path, icon, replace=replace, automatic=True)
            summary["applied"].append({"path": str(path), "method": result.method, "score": score})
        except Exception as exc:
            summary["errors"].append(f"{path.name}: {exc}")
    atomic_json(resolution_file, dict(list(resolutions.items())[-MAX_CACHED_RESOLUTIONS:]))
    atomic_json(data_dir() / "last-run.json", dict(summary, finished_at=time.time()))
    return summary

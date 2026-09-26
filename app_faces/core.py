import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from .i18n import t
from .upstreams import ADAPTERS, asset_url, records, sources

HTTP_TIMEOUT_SECONDS = 20
MAX_REVISION_RESPONSE_BYTES = 1_000_000
MAX_PROVIDER_CATALOG_BYTES = 8_000_000
MAX_PROVIDER_ICON_BYTES = 4_000_000
MAX_SEARCH_RESULTS = 100
UNCONFIGURED_SOURCE_PRIORITY = 10_000
LEGACY_CACHE_TTL_SECONDS = 7 * 86_400
MAX_IMAGE_DIMENSION = 4_096
NORMALIZED_ICON_SIZE = 512


GROUP = "Desktop Entry"
ATTR = "metadata::custom-icon"
SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,150}\Z")
SOURCE_REVISION = re.compile(r"[a-f0-9]{40}\Z")


def provider_revision(provider: str) -> str:
    source = sources()[provider]
    if SOURCE_REVISION.fullmatch(source.ref):
        return source.ref
    value = json.loads(
        download(
            f"https://api.github.com/repos/{source.repository}/commits/{urllib.parse.quote(source.ref, safe='')}",
            MAX_REVISION_RESPONSE_BYTES,
        )
    )
    revision = value.get("sha") if isinstance(value, dict) else None
    if not isinstance(revision, str) or not SOURCE_REVISION.fullmatch(revision):
        raise ValueError("Provider returned an invalid source revision")
    return revision


def provider_asset_url(provider: str, slug: str, revision: str) -> str:
    configured = sources()
    if provider not in configured:
        raise ValueError("Unknown provider")
    return asset_url(configured[provider].repository, slug, revision)


def atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "app-faces"


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "app-faces"


def desktop_dirs() -> list[Path]:
    home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    others = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    return [home / "applications"] + [Path(x) / "applications" for x in others if x]


def get_string(keyfile: Any, key: str, default: str = "") -> str:
    try:
        return str(keyfile.get_string(GROUP, key))
    except GLib.Error:
        return default


def executable_from_exec(command: str) -> Path | None:
    try:
        args = list(GLib.shell_parse_argv(command)[1])
    except GLib.Error:
        return None
    if not args:
        return None
    if Path(args[0]).name == "env":
        args = args[1:]
        while args and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", args[0]):
            args.pop(0)
        if args and args[0] == "--":
            args.pop(0)
    if not args or args[0].startswith("-"):
        return None
    name = Path(args[0]).name
    if name in {
        "sh",
        "bash",
        "zsh",
        "fish",
        "flatpak",
        "snap",
        "wine",
        "wine64",
        "bwrap",
        "sudo",
        "pkexec",
        "gio",
        "xdg-open",
    }:
        return None
    if re.fullmatch(r"(python[\d.]*|perl|ruby|node)", name):
        if len(args) < 2 or args[1].startswith("-"):
            return None
        token = args[1]
    else:
        token = args[0]
    token = token.replace("%%", "\x00")
    if "%" in token:
        return None
    token = token.replace("\x00", "%")
    if os.path.isabs(token):
        return Path(token).resolve()

    if "/" in token:
        return None
    found = shutil.which(token)
    return Path(found).resolve() if found else None


def desktop_entries(directories: Sequence[Path] | None = None) -> Iterator[dict[str, Any]]:
    seen = set()
    for directory in directories if directories is not None else desktop_dirs():
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for file in sorted(directory.rglob("*.desktop")):
            identity = str(file.relative_to(directory)).replace("/", "-")
            if identity in seen:
                continue
            seen.add(identity)
            keyfile = GLib.KeyFile()
            try:
                keyfile.load_from_file(str(file), GLib.KeyFileFlags.NONE)
                if get_string(keyfile, "Hidden").lower() == "true":
                    continue
                if get_string(keyfile, "Type") != "Application":
                    continue
                name = keyfile.get_locale_string(GROUP, "Name", None)
            except GLib.Error:
                continue
            yield dict(
                id=identity,
                name=name,
                icon=get_string(keyfile, "Icon"),
                executable=executable_from_exec(get_string(keyfile, "Exec")),
                file=str(file),
                nodisplay=get_string(keyfile, "NoDisplay") == "true",
                wm_class=get_string(keyfile, "StartupWMClass"),
                command=get_string(keyfile, "Exec"),
                try_exec=get_string(keyfile, "TryExec"),
            )


def custom_icon(path: Path) -> str:
    if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper():
        try:
            record = json.loads((data_dir() / "changes.json").read_text()).get(
                str(path.absolute()), {}
            )
            if record.get("inode") == path.stat().st_ino and record.get("backend") == "kde":
                return str(record.get("applied", ""))
        except OSError, ValueError:
            pass
    try:
        info = Gio.File.new_for_path(str(path)).query_info(ATTR, Gio.FileQueryInfoFlags.NONE, None)
        return str(info.get_attribute_string(ATTR) or "")
    except GLib.Error:
        return ""


@dataclass
class Result:
    status: str
    method: str
    name: str = ""
    icon: str = ""
    application_id: str = ""
    evidence: str = ""
    candidates: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Resolver:
    def __init__(
        self, directories: Sequence[Path] | None = None, catalog: dict[str, Any] | None = None
    ) -> None:
        self.entries = list(desktop_entries(directories))
        self._appstream: Any = None
        if catalog is None:
            file = cache_dir() / "catalog.json"
            try:
                catalog = json.loads(file.read_text())
            except OSError, ValueError:
                catalog = {"version": 1, "icons": [], "fingerprints": {}}
        self.catalog: dict[str, Any] = catalog if catalog is not None else {}

    def resolve(self, path: Path, read_custom: bool = True, fingerprint: bool = False) -> Result:
        path = Path(path).absolute()
        if not path.is_file():
            return Result("unknown", "none", evidence="Not a regular file")
        if read_custom:
            icon = custom_icon(path)
            if icon:
                return Result(
                    "resolved",
                    "user-icon",
                    path.name,
                    icon,
                    evidence="Existing file icon is authoritative",
                )
        matches = [e for e in self.entries if e["executable"] == path.resolve()]
        if len(matches) > 1:
            return Result(
                "ambiguous",
                "desktop",
                candidates=[dict(e, executable=str(e["executable"])) for e in matches],
                evidence="Multiple desktop entries launch this file",
            )
        if matches:
            e = matches[0]
            return Result(
                "resolved" if e["icon"] else "missing-icon",
                "desktop",
                e["name"],
                e["icon"],
                e["id"],
                e["file"],
            )
        if path.suffix.casefold() == ".appimage":
            from .bundles import extract_appimage

            try:
                bundle = extract_appimage(path, cache_dir() / "bundles")
            except OSError, ValueError:
                bundle = None
            if bundle:
                return Result(
                    "resolved",
                    "bundle",
                    bundle.name,
                    str(bundle.icon),
                    bundle.application_id,
                    bundle.evidence,
                )
        if fingerprint:
            from .identity import fingerprint as file_fingerprint

            try:
                digest = file_fingerprint(path, cache_dir() / "fingerprints.json")
            except ValueError:
                return Result("unknown", "sha256", evidence="File changed during hashing")
            match = self.catalog.get("fingerprints", {}).get(digest)
            if match:
                return Result(
                    "resolved", "sha256", match["name"], match["icon"], match["id"], digest
                )
        from .identity import AppStreamIndex

        if self._appstream is None:
            self._appstream = AppStreamIndex()
        identities = self._appstream.match(binary_names=[path.name])
        if identities:
            return Result(
                "suggested",
                "appstream",
                candidates=[
                    dict(
                        name=e.name,
                        icon=e.icon,
                        application_id=e.application_id,
                        evidence=e.evidence,
                    )
                    for e in identities
                ],
                evidence="AppStream binary-name evidence; select to confirm",
            )

        hits = self.search(application_search_name(path), exact=True)
        return Result(
            "suggested" if hits else "unknown",
            "filename" if hits else "none",
            evidence="Filename match requires selection" if hits else "No reliable association",
            candidates=hits,
        )

    def search(self, query: str, exact: bool = False) -> list[dict[str, Any]]:
        query = query.casefold().strip()
        if not query:
            return []
        result = []
        from .community import approved_icons

        configured = sources()
        entries = self.catalog.get("icons", []) + approved_icons()
        entries = sorted(
            entries,
            key=lambda e: (
                configured[e["provider"]].priority
                if e.get("provider") in configured
                else UNCONFIGURED_SOURCE_PRIORITY,
                e.get("provider", ""),
                e.get("slug", ""),
            ),
        )
        for e in entries:
            if e.get("provider") != "community" and (
                e.get("provider") not in configured or not configured[e["provider"]].enabled
            ):
                continue
            values = [e["slug"].casefold(), e["name"].casefold()]
            if (query in values) if exact else any(query in v for v in values):
                result.append(e)
        return result[:MAX_SEARCH_RESULTS]


def application_search_name(path: Path) -> str:
    stem = re.sub(r"(?i)\.(appimage|exe|bin|run)$", "", path.name).casefold()
    stem = re.sub(r"[-_](?:v?\d.*|x86_64|amd64|aarch64)$", "", stem)
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-")


def download(url: str, limit: int) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "AppFaces/0.1"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
        value = response.read(limit + 1)
    if len(value) > limit:
        raise ValueError("Provider response exceeds size limit")
    return bytes(value)


def sync_catalog() -> dict[str, Any]:
    icons: list[dict[str, Any]] = []
    errors: list[str] = []
    revisions: dict[str, str] = {}
    existing = Resolver().catalog
    configured = sources()
    successful = 0
    for provider, source in sorted(
        configured.items(), key=lambda pair: (pair[1].priority, pair[0])
    ):
        if not source.enabled:
            continue
        try:
            revision = provider_revision(provider)
            source_root = f"https://raw.githubusercontent.com/{source.repository}/{revision}"
            document = json.loads(
                download(source_root + "/" + ADAPTERS[source.format][0], MAX_PROVIDER_CATALOG_BYTES)
            )
            entries = records(source, document)
            revisions[provider] = revision
            successful += 1
            for slug, name in entries:
                icons.append(
                    dict(
                        name=name,
                        slug=slug,
                        provider=provider,
                        attribution=source.repository
                        + t(" · collection; artwork license unverified"),
                        asset_license="unknown",
                        source_repository=source.repository,
                        collection_source=f"https://github.com/{source.repository}/tree/{revision}",
                        source=f"https://github.com/{source.repository}/blob/{revision}/png/{slug}.png",
                        source_revision=revision,
                        source_url=asset_url(source.repository, slug, revision),
                    )
                )
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            previous = [
                item
                for item in existing.get("icons", [])
                if isinstance(item, dict) and item.get("provider") == provider
            ]
            icons.extend(previous)
            if provider in existing.get("sources", {}):
                revisions[provider] = existing["sources"][provider]
    if errors and not successful:
        raise RuntimeError("; ".join(errors))
    from .catalog import publish

    revision = publish(
        {
            "version": 1,
            "icons": icons,
            "sources": revisions,
            "fingerprints": existing.get("fingerprints", {}),
        }
    )
    return {
        "icons": len(icons),
        "providers": [key for key, source in configured.items() if source.enabled],
        "errors": errors,
        "revision": revision,
        "sources": revisions,
    }


def fetch_icon(provider: str, slug: str, source_revision: str | None = None) -> Path:
    if provider == "community":
        from .community import fetch_approved

        return fetch_approved(slug)
    if not SLUG.fullmatch(provider) or not SLUG.fullmatch(slug):
        raise ValueError("Unknown provider or invalid icon identifier")
    import time

    index_file = cache_dir() / "assets.json"
    try:
        assets = json.loads(index_file.read_text())
    except OSError, ValueError:
        assets = {}
    matches = [
        item
        for item in Resolver().catalog.get("icons", [])
        if isinstance(item, dict) and item.get("provider") == provider and item.get("slug") == slug
    ]
    if source_revision is None:
        source_revision = matches[0].get("source_revision") if matches else None
    if source_revision is not None and (
        not isinstance(source_revision, str) or not SOURCE_REVISION.fullmatch(source_revision)
    ):
        raise ValueError("Invalid source revision")
    legacy = assets.get(provider + ":" + slug, {})
    legacy_path = Path(legacy.get("path", "/nonexistent"))
    if source_revision is None:
        if (
            legacy_path.is_file()
            and time.time() - legacy.get("fetched_at", 0) < LEGACY_CACHE_TTL_SECONDS
        ):
            return legacy_path
        configured = sources()
        if provider not in configured or not configured[provider].enabled:
            if legacy_path.is_file():
                return legacy_path
            raise ValueError("Source is removed or disabled; specify a cached source revision")
        try:
            source_revision = provider_revision(provider)
        except OSError, ValueError:
            if legacy_path.is_file():
                return legacy_path
            raise
    key = provider + ":" + source_revision + ":" + slug
    prior = assets.get(key, {})
    prior_path = Path(prior.get("path", "/nonexistent"))
    matching = next(
        (item for item in matches if item.get("source_revision") == source_revision), {}
    )
    configured = sources()
    repository = matching.get("source_repository") or prior.get("source_repository")
    source_url = (
        asset_url(repository, slug, source_revision)
        if repository
        else provider_asset_url(provider, slug, source_revision)
    )

    if prior_path.is_file() and prior.get("source_url") == source_url:
        return prior_path
    if provider not in configured or not configured[provider].enabled:
        raise ValueError("Source is removed or disabled; only cached artwork is available")
    content = download(source_url, MAX_PROVIDER_ICON_BYTES)
    path = data_dir() / "artwork" / provider / (hashlib.sha256(content).hexdigest() + ".png")

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    loader = GdkPixbuf.PixbufLoader.new_with_type("png")

    def prepared(loader: Any, width: int, height: int) -> None:
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            loader.set_size(NORMALIZED_ICON_SIZE, NORMALIZED_ICON_SIZE)

    loader.connect("size-prepared", prepared)
    loader.write(content)
    loader.close()
    pixbuf = loader.get_pixbuf()
    if pixbuf is None:
        raise ValueError("Provider did not return an image")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".png")
    os.close(fd)
    try:
        pixbuf.savev(tmp, "png", [], [])
        os.replace(tmp, path)
        assets[key] = dict(
            path=str(path),
            fetched_at=time.time(),
            source=source_url,
            source_url=source_url,
            source_revision=source_revision,
            source_repository=repository or configured[provider].repository,
        )
        atomic_json(index_file, assets)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def icon_path(icon: str) -> Path | None:
    if icon.startswith("file:"):
        file = Gio.File.new_for_uri(icon).get_path()
        return Path(file) if file and Path(file).is_file() else None
    if os.path.isabs(icon):
        return Path(icon) if Path(icon).is_file() else None
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gtk

    display = Gdk.Display.get_default()
    theme = Gtk.IconTheme.get_for_display(display) if display else Gtk.IconTheme.new()
    if not display:
        try:
            name = Gio.Settings.new("org.gnome.desktop.interface").get_string("icon-theme")
        except GLib.Error:
            name = "Adwaita"
        theme.set_theme_name(name)
    if not theme.has_icon(icon):
        return None
    paintable = theme.lookup_icon(icon, [], 128, 1, Gtk.TextDirection.NONE, 0)
    file = paintable.get_file()
    return Path(file.get_path()) if file and file.get_path() else None

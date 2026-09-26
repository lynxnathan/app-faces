import gzip
import hashlib
import json
import os
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_METADATA_BYTES = 32_000_000


@dataclass(frozen=True)
class Identity:
    application_id: str
    name: str
    icon: str
    evidence: str
    desktop_ids: tuple[str, ...] = ()
    binaries: tuple[str, ...] = ()


def catalog_paths() -> list[Path]:
    roots = [
        Path("/usr/share/metainfo"),
        Path("/usr/share/appdata"),
        Path("/var/cache/swcatalog/xml"),
        Path("/var/lib/swcatalog/xml"),
        Path("/var/cache/app-info/xmls"),
        Path("/var/lib/app-info/xmls"),
    ]
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    roots.extend([data_home / "metainfo", data_home / "appdata"])
    paths = {p for root in roots for pattern in ("*.xml", "*.xml.gz") for p in root.glob(pattern)}
    for root in (Path("/var/lib/flatpak/appstream"), data_home / "flatpak/appstream"):
        paths.update(root.glob("*/*/active/appstream.xml.gz"))
    return sorted(paths)


def _icon(component: ET.Element, source: Path, origin: str) -> str:
    for element in component.findall("icon"):
        value = (element.text or "").strip()
        kind = element.get("type", "stock")
        if kind == "stock" and value and "/" not in value:
            return value
        if kind == "local" and Path(value).is_absolute() and Path(value).is_file():
            return value
        if kind == "cached" and value and Path(value).name == value:
            if origin and (Path(origin).name != origin or origin in (".", "..")):
                continue
            size = element.get("width", "64") + "x" + element.get("height", "64")
            if not all(part.isdecimal() for part in size.split("x")):
                continue
            base = source.parent.parent / "icons"
            for path in (
                base / origin / size / value,
                base / origin / value,
                base / size / value,
                base / value,
                source.parent / "icons" / size / value,
            ):
                if path.is_file():
                    return str(path)
    return ""


class AppStreamIndex:
    def __init__(self, paths: Sequence[Path] | None = None) -> None:
        self.entries: list[Identity] = []
        self.errors: list[str] = []
        for path in paths if paths is not None else catalog_paths():
            try:
                opener = gzip.open if path.suffix == ".gz" else open
                with opener(path, "rb") as stream:
                    content = stream.read(MAX_METADATA_BYTES + 1)
                if len(content) > MAX_METADATA_BYTES or b"<!DOCTYPE" in content.upper():
                    raise ValueError("Unsupported or oversized catalog")
                root = ET.fromstring(content)
                components = [root] if root.tag == "component" else root.findall("component")
                for component in components:
                    app_id = (component.findtext("id") or "").strip()
                    if not app_id:
                        continue
                    desktops = tuple(
                        (x.text or "").strip()
                        for x in component.findall("launchable[@type='desktop-id']")
                        if x.text
                    )
                    binaries = tuple(
                        (x.text or "").strip()
                        for x in component.findall("provides/binary")
                        if x.text
                    )
                    self.entries.append(
                        Identity(
                            app_id,
                            component.findtext("name") or app_id,
                            _icon(component, path, root.get("origin", "")),
                            str(path),
                            desktops,
                            binaries,
                        )
                    )
            except (OSError, EOFError, ValueError, ET.ParseError) as exc:
                self.errors.append(f"{path}: {exc}")

    def match(
        self, application_ids: Sequence[str] = (), binary_names: Sequence[str] = ()
    ) -> list[Identity]:
        ids, names = set(application_ids), set(binary_names)
        matches: dict[str, Identity] = {}
        for entry in self.entries:
            if (
                entry.application_id in ids
                or ids.intersection(entry.desktop_ids)
                or names.intersection(entry.binaries)
            ):
                prior = matches.get(entry.application_id)
                if prior is None or (not prior.icon and entry.icon):
                    matches[entry.application_id] = entry
        return list(matches.values())


def fingerprint(path: Path, cache_file: Path | None = None) -> str:

    def signature() -> list[int]:
        st = path.stat()
        return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]

    before = signature()
    key = str(path.resolve())
    cache: dict[str, dict[str, object]] = {}
    if cache_file:
        try:
            loaded = json.loads(cache_file.read_text())
            if isinstance(loaded, dict):
                cache = loaded
            item = cache.get(key, {})
            digest = item.get("sha256")
            if item.get("stat") == before and isinstance(digest, str) and len(digest) == 64:
                return digest
        except OSError, ValueError, AttributeError:
            cache = {}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if before != signature():
        raise ValueError("File changed during fingerprinting")
    value = digest.hexdigest()
    if cache_file:
        cache[key] = {"stat": before, "sha256": value}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=cache_file.parent)
        try:
            with os.fdopen(fd, "w") as output:
                json.dump(cache, output)
            os.replace(tmp, cache_file)
        finally:
            Path(tmp).unlink(missing_ok=True)
    return value

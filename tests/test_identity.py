import gzip
import hashlib
from pathlib import Path

import pytest

from app_faces.identity import AppStreamIndex, fingerprint


def test_appstream_identity_gzip_and_cached_icon(tmp_path: Path) -> None:
    source = tmp_path / "xml" / "catalog.xml.gz"
    source.parent.mkdir()
    icon = tmp_path / "icons" / "test" / "64x64" / "demo.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"image")
    with gzip.open(source, "wb") as stream:
        stream.write(b"""<components origin="test"><component><id>org.demo.App</id>
        <name>Demo</name><launchable type="desktop-id">demo.desktop</launchable>
        <provides><binary>demo</binary></provides>
        <icon type="cached" width="64" height="64">demo.png</icon>
        </component></components>""")
    index = AppStreamIndex([source])
    assert index.match(application_ids=["demo.desktop"])[0].icon == str(icon)
    assert index.match(binary_names=["demo"])[0].name == "Demo"
    assert not index.match(binary_names=["demo-other"])


def test_appstream_missing_asset_and_ambiguity(tmp_path: Path) -> None:
    source = tmp_path / "catalog.xml"
    source.write_text("""<components><component><id>a</id><provides><binary>demo</binary>
    </provides><icon type="cached">missing.png</icon></component><component><id>b</id>
    <provides><binary>demo</binary></provides><icon type="stock">demo</icon>
    </component></components>""")
    result = AppStreamIndex([source]).match(binary_names=["demo"])
    assert len(result) == 2
    assert result[0].icon == ""
    assert result[1].icon == "demo"


def test_appstream_rejects_entities(tmp_path: Path) -> None:
    source = tmp_path / "catalog.xml"
    source.write_text('<!DOCTYPE foo [<!ENTITY x "bad">]><component><id>&x;</id></component>')
    index = AppStreamIndex([source])
    assert index.errors
    assert not index.entries


@pytest.mark.parametrize("field", ["origin", "filename"])
def test_appstream_rejects_traversal_to_existing_artwork(tmp_path: Path, field: str) -> None:
    source = tmp_path / "xml/catalog.xml"
    source.parent.mkdir()
    icons = tmp_path / "icons"
    (icons / "64x64").mkdir(parents=True)
    if field == "origin":
        target = tmp_path / "outside/64x64/secret.png"
        origin, filename = "../outside", "secret.png"
    else:
        target = icons / "secret.png"
        origin, filename = "", "../secret.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"private artwork")
    source.write_text(
        f'<components origin="{origin}"><component><id>demo</id>'
        f'<icon type="cached">{filename}</icon></component></components>'
    )
    assert AppStreamIndex([source]).match(application_ids=["demo"])[0].icon == ""
    assert target.read_bytes() == b"private artwork"


def test_fingerprint_reuses_and_invalidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "binary"
    cache = tmp_path / "cache.json"
    source.write_bytes(b"first")
    original_open = Path.open
    reads = []

    def track_open(path, mode="r", *args, **kwargs):
        if path == source and mode == "rb":
            reads.append(path)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", track_open)
    first = fingerprint(source, cache)
    assert first == hashlib.sha256(b"first").hexdigest()
    assert len(reads) == 1
    assert fingerprint(source, cache) == first
    assert len(reads) == 1
    source.write_bytes(b"other")
    assert fingerprint(source, cache) == hashlib.sha256(b"other").hexdigest()
    assert len(reads) == 2
    cache.write_text("invalid")
    assert fingerprint(source, cache) == fingerprint(source)

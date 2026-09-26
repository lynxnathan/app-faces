import json
from pathlib import Path

import pytest

from app_faces import catalog


def sample(name: str = "Demo") -> dict:
    return {
        "version": 1,
        "icons": [{"name": name, "slug": "demo", "provider": "selfhst"}],
        "fingerprints": {},
    }


def test_publish_rollback_integrity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "cache_dir", lambda: tmp_path)
    first = catalog.publish(sample())
    second = catalog.publish(sample("Other"))
    assert first != second
    assert catalog.rollback(first) == {"revision": first}
    assert json.loads((tmp_path / "catalog.json").read_text())["icons"][0]["name"] == "Demo"
    history = tmp_path / "catalog-history" / f"{first}.json"
    value = json.loads(history.read_text())
    value["icons"][0]["name"] = "Tampered"
    history.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="integrity"):
        catalog.rollback(first)
    assert json.loads((tmp_path / "catalog.json").read_text())["icons"][0]["name"] == "Demo"


@pytest.mark.parametrize(
    "value",
    [
        [],
        {"version": 2},
        {"version": 1, "icons": [{}]},
        {"version": 1, "icons": [], "fingerprints": {3: {}}},
        {"version": 1, "icons": [{"name": "Demo", "provider": "selfhst", "slug": "../bad"}]},
    ],
)
def test_validation_rejects_bad_catalog(value: object) -> None:
    with pytest.raises(ValueError):
        catalog.validate(value)


def test_invalid_import_preserves_working_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog, "cache_dir", lambda: tmp_path)
    revision = catalog.publish(sample())
    bad = tmp_path / "bad.json"
    bad.write_text('{"version":1,"icons":[{}]}')
    with pytest.raises(ValueError):
        catalog.import_catalog(bad)
    assert json.loads((tmp_path / "catalog.json").read_text())["revision"] == revision


def test_sync_pins_metadata_and_preserves_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app_faces import core

    monkeypatch.setattr(core, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "cache_dir", lambda: tmp_path)
    seed = {"f" * 64: {"id": "example", "name": "Example", "icon": "/local/example.png"}}
    core.atomic_json(tmp_path / "catalog.json", {"version": 1, "icons": [], "fingerprints": seed})
    calls = []

    def download(url: str, limit: int) -> bytes:
        calls.append(url)
        provider_revision = "a" * 40 if "selfhst" in url else "b" * 40
        if url.startswith("https://api.github.com/"):
            return json.dumps({"sha": provider_revision}).encode()
        assert "/" + provider_revision + "/" in url
        assert "/main/" not in url
        return (
            b'[{"Name":"Demo","Reference":"demo","PNG":"Yes"}]'
            if "selfhst" in url
            else b'{"png":["demo.png"]}'
        )

    monkeypatch.setattr(core, "download", download)
    core.sync_catalog()
    value = json.loads((tmp_path / "catalog.json").read_text())
    assert value["fingerprints"] == seed
    assert len(calls) == 4
    for item in value["icons"]:
        assert item["source_revision"] == value["sources"][item["provider"]]
        assert "/" + item["source_revision"] + "/png/demo.png" in item["source_url"]
        assert item["asset_license"] == "unknown"
        assert "artwork license unverified" in item["attribution"]


@pytest.mark.parametrize("bad_revision", ["main", "../evil", "f" * 39, 123, None])
def test_invalid_upstream_revision_keeps_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_revision: object
) -> None:
    from app_faces import core

    monkeypatch.setattr(core, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "cache_dir", lambda: tmp_path)
    revision = catalog.publish(sample())
    monkeypatch.setattr(core, "download", lambda *_: json.dumps({"sha": bad_revision}).encode())
    with pytest.raises(RuntimeError, match="invalid source revision"):
        core.sync_catalog()
    assert json.loads((tmp_path / "catalog.json").read_text())["revision"] == revision


def test_failed_pinned_metadata_keeps_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app_faces import core

    monkeypatch.setattr(core, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(catalog, "cache_dir", lambda: tmp_path)
    revision = catalog.publish(sample())

    def download(url: str, limit: int) -> bytes:
        if "api.github.com" in url:
            return json.dumps({"sha": "a" * 40}).encode()
        raise OSError("offline")

    monkeypatch.setattr(core, "download", download)
    with pytest.raises(RuntimeError, match="offline"):
        core.sync_catalog()
    assert json.loads((tmp_path / "catalog.json").read_text())["revision"] == revision


def test_catalog_rejects_wrong_pinned_artwork_url() -> None:
    value = sample()
    value["icons"][0].update(
        source_revision="a" * 40, source_url="https://untrusted.example/icon.png"
    )
    with pytest.raises(ValueError, match="does not match"):
        catalog.validate(value)


def test_asset_cache_preserves_each_revision_and_legacy_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import struct
    import zlib

    from app_faces import core

    monkeypatch.setattr(core, "cache_dir", lambda: tmp_path / "cache")
    monkeypatch.setattr(core, "data_dir", lambda: tmp_path / "data")

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
        + chunk(b"IEND", b"")
    )
    calls = []

    def download(url: str, limit: int) -> bytes:
        calls.append(url)
        return png

    monkeypatch.setattr(core, "download", download)
    first = core.fetch_icon("selfhst", "demo", "a" * 40)
    second = core.fetch_icon("selfhst", "demo", "b" * 40)
    assert first.exists() and second.exists()
    assert len(calls) == 2
    assert "/" + "a" * 40 + "/" in calls[0]
    assert "/" + "b" * 40 + "/" in calls[1]
    assert core.fetch_icon("selfhst", "demo", "a" * 40) == first
    assert len(calls) == 2
    index = json.loads((tmp_path / "cache/assets.json").read_text())
    assert len(index) == 2
    index["selfhst:legacy"] = {"path": str(first), "fetched_at": 0}
    core.atomic_json(tmp_path / "cache/assets.json", index)

    def offline(*args: object) -> bytes:
        raise OSError("offline")

    monkeypatch.setattr(core, "download", offline)
    assert core.fetch_icon("selfhst", "legacy") == first

    with pytest.raises(OSError):
        core.fetch_icon("selfhst", "legacy", "c" * 40)

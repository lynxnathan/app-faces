import json

import pytest

from app_faces import catalog, core, upstreams


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    config = tmp_path / "config/app-faces/upstreams.toml"
    config.parent.mkdir(parents=True)
    return config


def fork(config, extra=""):
    config.write_text(
        """[[sources]]
id = "mirror"
repository = "example/icons"
format = "selfhst"
priority = 1
"""
        + extra
    )


def response(url, limit):
    if "api.github.com" in url:
        return json.dumps({"sha": "a" * 40}).encode()
    if "tree.json" in url:
        return b'{"png":["demo.png"]}'
    return b'[{"Name":"Demo","Reference":"demo","PNG":"Yes"}]'


def test_fork_conflicts_priority_never_become_identity(environment, monkeypatch, tmp_path):
    fork(environment)
    monkeypatch.setattr(core, "download", response)
    report = core.sync_catalog()
    assert report["errors"] == []
    hits = core.Resolver(directories=[]).search("demo")
    assert [hit["provider"] for hit in hits] == ["mirror", "selfhst", "dashboard"]
    assert (
        hits[0]["source_url"]
        == f"https://raw.githubusercontent.com/example/icons/{'a' * 40}/png/demo.png"
    )
    binary = tmp_path / "demo"
    binary.write_bytes(b"not demo")
    result = core.Resolver(directories=[]).resolve(binary, read_custom=False)
    assert result.status == "suggested" and result.method == "filename"
    assert result.icon == ""


def test_partial_failure_keeps_prior_source_and_updates_healthy(environment, monkeypatch):
    fork(environment)
    monkeypatch.setattr(core, "download", response)
    first = core.sync_catalog()["revision"]

    def changed(url, limit):
        if "example/icons" in url:
            raise OSError("temporarily offline")
        if "api.github.com" in url:
            return json.dumps({"sha": "b" * 40}).encode()
        return response(url, limit)

    monkeypatch.setattr(core, "download", changed)
    report = core.sync_catalog()
    assert report["sources"]["mirror"] == "a" * 40
    assert report["sources"]["selfhst"] == "b" * 40
    assert report["errors"] == ["mirror: temporarily offline"]
    assert report["revision"] != first
    catalog.rollback(first)
    assert core.Resolver().catalog["sources"]["selfhst"] == "a" * 40


def test_disable_remove_preserve_artwork_and_history(environment, monkeypatch):
    import struct
    import zlib

    fork(environment)
    monkeypatch.setattr(core, "download", response)
    revision = core.sync_catalog()["revision"]

    def chunk(kind, payload):
        return (
            struct.pack("!I", len(payload))
            + kind
            + payload
            + struct.pack("!I", zlib.crc32(kind + payload))
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff"))
        + chunk(b"IEND", b"")
    )
    monkeypatch.setattr(core, "download", lambda *_: png)
    artwork = core.fetch_icon("mirror", "demo")
    original = artwork.read_bytes()
    fork(environment, "enabled = false\n")
    assert all(hit["provider"] != "mirror" for hit in core.Resolver().search("demo"))
    assert core.fetch_icon("mirror", "demo", "a" * 40) == artwork
    with pytest.raises(ValueError, match="disabled"):
        core.fetch_icon("mirror", "missing", "a" * 40)
    environment.unlink()
    monkeypatch.setattr(core, "download", response)
    core.sync_catalog()
    assert artwork.read_bytes() == original
    assert core.fetch_icon("mirror", "demo", "a" * 40) == artwork

    catalog.rollback(revision)
    assert any(item["provider"] == "mirror" for item in core.Resolver().catalog["icons"])
    assert all(hit["provider"] != "mirror" for hit in core.Resolver().search("demo"))


def test_new_adapter_uses_common_pinning_validation(environment, monkeypatch):
    monkeypatch.setitem(
        upstreams.ADAPTERS,
        "example",
        ("catalog.json", lambda doc: [(x["key"], x["label"]) for x in doc["items"]]),
    )
    environment.write_text("""[[sources]]
id="example"
repository="example/new-format"
format="example"
ref="cccccccccccccccccccccccccccccccccccccccc"
""")
    calls = []

    def document(url, limit):
        calls.append(url)
        if "new-format" in url:
            assert f"/{'c' * 40}/catalog.json" in url
            return b'{"items":[{"key":"demo","label":"New schema"}]}'
        return response(url, limit)

    monkeypatch.setattr(core, "download", document)
    core.sync_catalog()
    assert not any("api.github.com/repos/example" in url for url in calls)
    hit = next(x for x in core.Resolver().search("demo") if x["provider"] == "example")
    assert hit["name"] == "New schema" and hit["asset_license"] == "unknown"


@pytest.mark.parametrize(
    "body",
    [
        '[[sources]]\nid="../bad"\nrepository="a/b"\nformat="selfhst"',
        '[[sources]]\nid="community"\nrepository="a/b"\nformat="selfhst"',
        '[[sources]]\nid="selfhst"\nrepository="https://evil/"',
        '[[sources]]\nid="selfhst"\nformat="unknown"',
        '[[sources]]\nid="selfhst"\npriority=true',
        '[[sources]]\nid="selfhst"\nref="../main"',
        '[[sources]]\nid="selfhst"\n[[sources]]\nid="selfhst"',
        '[[sources]]\nid="new"',
    ],
)
def test_invalid_configuration_preserves_working_snapshot(environment, monkeypatch, body):
    monkeypatch.setattr(core, "download", response)
    core.sync_catalog()
    original = (core.cache_dir() / "catalog.json").read_bytes()
    environment.write_text(body)
    with pytest.raises(ValueError):
        core.sync_catalog()
    assert (core.cache_dir() / "catalog.json").read_bytes() == original


def test_bad_metadata_and_missing_asset_do_not_corrupt_cache(environment, monkeypatch):
    fork(environment)
    monkeypatch.setattr(core, "download", response)
    core.sync_catalog()
    original = core.Resolver().catalog["icons"]

    def broken(url, limit):
        if "example/icons" in url and "api.github.com" not in url:
            return b'[{"Name":"A","Reference":"demo","PNG":"Yes"},{"Name":"B","Reference":"demo","PNG":"Yes"}]'
        return response(url, limit)

    monkeypatch.setattr(core, "download", broken)
    report = core.sync_catalog()
    assert report["errors"] == ["mirror: Conflicting duplicate upstream slug"]
    assert core.Resolver().catalog["icons"] == original
    monkeypatch.setattr(core, "download", lambda *_: (_ for _ in ()).throw(OSError("404")))
    with pytest.raises(OSError, match="404"):
        core.fetch_icon("mirror", "demo")
    assert not (core.cache_dir() / "assets.json").exists()


def test_background_config_edit_refreshes_fresh_catalog_and_resolution_cache(
    environment, monkeypatch, tmp_path
):
    import os

    from app_faces import automatic

    target = tmp_path / "demo"
    target.write_bytes(b"not a recognized application")
    os.utime(target, (1, 1))
    monkeypatch.setattr(automatic, "candidates", lambda _: [target])
    monkeypatch.setattr(automatic, "prepare_automatic", lambda _: (True, False))
    calls = []

    def downloaded(url, limit):
        calls.append(url)
        return response(url, limit)

    monkeypatch.setattr(core, "download", downloaded)
    assert automatic.run_once()["errors"] == []
    calls.clear()
    assert automatic.run_once()["errors"] == []
    assert calls == []
    fork(environment)
    assert automatic.run_once()["errors"] == []
    assert any("example/icons" in url for url in calls)
    resolutions = json.loads((core.cache_dir() / "resolutions.json").read_text())
    result = resolutions[str(target)]["result"]
    assert result["status"] == "suggested"
    assert result["candidates"][0]["provider"] == "mirror"
    calls.clear()

    environment.write_text(environment.read_text() + "\n# Same settings\n")
    automatic.run_once()
    assert calls == []
    fork(environment, "enabled = false\n")
    automatic.run_once()
    resolutions = json.loads((core.cache_dir() / "resolutions.json").read_text())
    assert all(
        item["provider"] != "mirror" for item in resolutions[str(target)]["result"]["candidates"]
    )
    assert (core.data_dir() / "changes.json").exists() is False


def test_background_failure_backoff_is_config_specific_and_invalid_config_safe(
    environment, monkeypatch
):
    import time

    from app_faces import automatic

    monkeypatch.setattr(automatic, "candidates", lambda _: [])
    now = time.time()
    monkeypatch.setattr(automatic.time, "time", lambda: now)
    calls = []

    def offline(url, limit):
        calls.append(url)
        raise OSError("offline")

    monkeypatch.setattr(core, "download", offline)
    assert automatic.run_once()["errors"]
    initial = len(calls)
    automatic.run_once()
    assert len(calls) == initial
    fork(environment)
    assert automatic.run_once()["errors"]
    changed = len(calls)
    assert changed > initial
    automatic.run_once()
    assert len(calls) == changed
    now += 901
    automatic.run_once()
    assert len(calls) > changed
    before = len(calls)
    environment.write_text('[[sources]]\nid="mirror"\nformat="unknown"\nrepository="a/b"\n')
    invalid = automatic.run_once()
    assert invalid["errors"] == ["upstreams: Unknown upstream format"]
    assert invalid["examined"] == 0 and invalid["applied"] == []
    assert len(calls) == before
    fork(environment, 'ref="release"\n')
    automatic.run_once()
    assert len(calls) > before

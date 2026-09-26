from app_faces.automatic import confidence, run_once
from app_faces.core import Result


def test_name_alone_does_not_auto_apply(tmp_path):
    p = tmp_path / "Blender.AppImage"
    p.write_bytes(b"not an appimage")
    r = Result("suggested", "filename", candidates=[{"slug": "blender"}])
    assert confidence(p, r) < 0.9


def test_exact_appimage_name_and_magic_qualify(tmp_path):
    p = tmp_path / "Blender.AppImage"
    p.write_bytes(b"\x7fELF\x02\x01\x01\x00AI\x02\x00")
    r = Result("suggested", "filename", candidates=[{"slug": "blender"}, {"slug": "blender"}])
    assert confidence(p, r) >= 0.9


def test_conflicting_identities_never_auto_apply(tmp_path):
    p = tmp_path / "app.AppImage"
    r = Result("suggested", "filename", candidates=[{"slug": "one"}, {"slug": "two"}])
    assert confidence(p, r) == 0


def test_ambiguous_desktop_never_auto_applies(tmp_path):
    assert confidence(tmp_path / "app", Result("ambiguous", "desktop")) == 0


def test_desktop_qualifies(tmp_path):
    assert confidence(tmp_path / "app", Result("resolved", "desktop")) == 1


def test_background_preserves_custom_icon(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr("app_faces.automatic.sync_catalog", lambda: {})
    p = tmp_path / "app"
    p.touch()
    import os

    os.utime(p, (1, 1))
    monkeypatch.setattr("app_faces.automatic.candidates", lambda _: [p])
    monkeypatch.setattr("app_faces.state.custom_icon", lambda _: "file:///user.png")

    def forbidden(*args, **kwargs):
        raise AssertionError("Must not overwrite an existing icon")

    monkeypatch.setattr("app_faces.automatic.apply", forbidden)
    assert run_once()["applied"] == []


def test_pause_preserves_other_configuration(monkeypatch, tmp_path):
    import json

    from app_faces.automatic import set_enabled

    config = tmp_path / "app-faces/config.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"directories": ["/keep"], "community_url": "https://example.org"})
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    set_enabled(False)
    value = json.loads(config.read_text())
    assert value["directories"] == ["/keep"]
    assert value["automatic_enabled"] is False
    set_enabled(True)
    assert json.loads(config.read_text())["automatic_enabled"] is True


def test_paused_scan_never_changes_icons(monkeypatch, tmp_path):
    import json

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    config = tmp_path / "config/app-faces/config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({"automatic_enabled": False}))
    monkeypatch.setattr("app_faces.automatic.sync_catalog", lambda: {})

    def forbidden(*_):
        raise AssertionError("Paused must not scan files")

    monkeypatch.setattr("app_faces.automatic.candidates", forbidden)
    assert run_once()["paused"]


def test_parallel_scan_yields(monkeypatch, tmp_path):
    import fcntl

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    root = tmp_path / "app-faces"
    root.mkdir()
    with (root / "automatic.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert run_once()["busy"]

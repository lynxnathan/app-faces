import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from app_faces import installation, launchers, state
from app_faces.core import data_dir


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / "cache"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(home / "system-data") + ":/usr/share")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    control = Mock()
    monkeypatch.setattr(installation, "systemctl", control)
    return tmp_path / "source", control


def manifest():
    return json.loads((data_dir() / "installation.json").read_text())


def test_install_repeat_uninstall_repeat_and_service_order(isolated):
    root, control = isolated
    first = installation.install(root)
    snapshot = {path: path.read_bytes() for path in installation.managed_files(root)}
    assert installation.install(root) == first
    assert snapshot == {path: path.read_bytes() for path in snapshot}
    assert len(manifest()["files"]) == len(snapshot)
    assert (Path.home() / ".local/bin/app-faces").stat().st_mode & 0o111
    control.reset_mock()
    result = installation.uninstall()
    assert sorted(result["removed"]) == sorted(map(str, snapshot))
    assert result["launchers"] == {"removed": [], "preserved": []}
    assert result["icons"] == {"restored": [], "preserved": [], "missing": []}
    assert control.call_args_list[0].args == ("disable", "--now", "app-faces.timer")
    assert control.call_args_list[1].args == ("stop", "app-faces.service")
    assert control.call_args_list[-1].args == ("daemon-reload",)
    assert manifest()["files"] == {}
    assert installation.uninstall()["removed"] == []
    assert all(not path.exists() for path in snapshot)


def test_uninstall_restores_icons_and_removes_generated_launchers(isolated, tmp_path):
    root, _ = isolated
    installation.install(root, activate=False)
    app = tmp_path / "app"
    app.write_text("Never execute this fixture")
    app.chmod(0o700)
    icon = tmp_path / "artwork.png"
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
    image.fill(0xFF0000FF)
    image.savev(str(icon), "png", [], [])
    state.apply(app, str(icon), backend="kde")
    launcher = launchers.add_launcher(app, "Example", str(icon))
    report = installation.uninstall(activate=False)
    assert report["icons"]["restored"] == [str(app)]
    assert report["launchers"]["removed"] == [str(launcher.path)]
    assert not launcher.path.exists()
    assert json.loads((data_dir() / "changes.json").read_text()) == {}
    assert json.loads((data_dir() / "disabled.json").read_text())[str(app)] == app.stat().st_ino
    assert icon.exists()


def test_user_edits_preserved_by_upgrade_and_uninstall(isolated):
    root, _ = isolated
    installation.install(root, activate=False)
    files = installation.managed_files(root)
    edited = next(iter(files))
    edited.write_text(edited.read_text() + "# My customization\n")
    snapshot = {path: path.read_bytes() for path in files}
    with pytest.raises(ValueError, match="edited"):
        installation.install(root, activate=False)
    assert snapshot == {path: path.read_bytes() for path in files}
    result = installation.uninstall(activate=False)
    assert result["preserved"] == [str(edited)]
    assert edited.read_bytes() == snapshot[edited]
    assert str(edited) in manifest()["files"]
    assert installation.uninstall(activate=False)["preserved"] == [str(edited)]


def test_unknown_marker_is_not_ownership_and_preflight_is_atomic(isolated):
    root, _ = isolated
    files = installation.managed_files(root)
    last = list(files)[-1]
    last.parent.mkdir(parents=True)
    last.write_text(installation.MARKER + "\n# User-owned replacement\n")
    with pytest.raises(ValueError, match="unrelated"):
        installation.install(root, activate=False)
    assert all(not p.exists() for p in list(files)[:-1])
    assert "replacement" in last.read_text()


def test_identical_unmanifested_files_can_be_adopted(isolated):
    root, _ = isolated
    for path, text in installation.managed_files(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    installation.install(root, activate=False)
    assert len(manifest()["files"]) == 5
    assert len(installation.uninstall(activate=False)["removed"]) == 5


def test_dangling_symlink_preserved_and_tracked(isolated):
    root, _ = isolated
    installation.install(root, activate=False)
    target = next(iter(installation.managed_files(root)))
    target.unlink()
    target.symlink_to(target.parent / "nonexistent")
    result = installation.uninstall(activate=False)
    assert result["preserved"] == [str(target)]
    assert target.is_symlink()
    assert str(target) in manifest()["files"]


def test_partial_install_and_interrupted_upgrade_can_be_uninstalled(isolated, monkeypatch):
    root, _ = isolated
    installation.install(root, activate=False)

    def fail_write(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(installation, "_atomic_write", fail_write)
    with pytest.raises(OSError, match="disk failure"):
        installation.install(root / "new location", activate=False)
    assert any("previous_sha256" in entry for entry in manifest()["files"].values())
    report = installation.uninstall(activate=False)
    assert len(report["removed"]) == 5
    assert report["preserved"] == []


def test_keep_icons_option_retains_icon_journal(isolated, monkeypatch):
    root, _ = isolated
    installation.install(root, activate=False)
    rollback = Mock()
    monkeypatch.setattr(state, "rollback_all", rollback)
    report = installation.uninstall(activate=False, restore=False)
    rollback.assert_not_called()
    assert "retained" in report["icons"]


def test_corrupt_manifest_never_discards_ownership_history(isolated):
    root, _ = isolated
    installation.install(root, activate=False)
    journal = data_dir() / "installation.json"
    journal.write_text("{corrupt")
    with pytest.raises(json.JSONDecodeError):
        installation.uninstall(activate=False)
    assert all(p.exists() for p in installation.managed_files(root))
    assert journal.read_text() == "{corrupt"


def test_service_failure_stops_removal_before_rollback(isolated, monkeypatch):
    root, control = isolated
    installation.install(root, activate=False)
    control.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="No bus")
    rollback = Mock()
    monkeypatch.setattr(state, "rollback_all", rollback)
    with pytest.raises(subprocess.CalledProcessError):
        installation.uninstall()
    rollback.assert_not_called()
    assert all(p.exists() for p in installation.managed_files(root))


def test_systemctl_missing_units_are_idempotent_but_bus_failure_is_not(monkeypatch):
    call = Mock(
        return_value=subprocess.CompletedProcess(
            ["systemctl"], 1, "", "Failed to stop app-faces.service: Unit not loaded."
        )
    )
    monkeypatch.setattr(installation.subprocess, "run", call)
    installation.systemctl("stop", "app-faces.service", missing_ok=True)
    assert call.call_args.kwargs["env"]["LC_ALL"] == "C"
    with pytest.raises(subprocess.CalledProcessError):
        installation.systemctl("stop", "app-faces.service")
    call.return_value = subprocess.CompletedProcess(
        ["systemctl"], 1, "", "Failed to connect to bus"
    )
    with pytest.raises(subprocess.CalledProcessError):
        installation.systemctl("stop", "app-faces.service", missing_ok=True)


def elf_fixture(directory):
    source = directory / "libappfacesthumbnail.so"
    content = bytearray(64)
    content[:6] = b"\x7fELF\x02\x01"
    content[16:18] = (3).to_bytes(2, "little")
    source.write_bytes(content)
    return source


def test_optional_kde_plugin_install_repeat_and_uninstall(isolated, tmp_path):
    root, _ = isolated
    installation.install(root, activate=False)
    source = elf_fixture(tmp_path)
    plugin_dir = Path.home() / "qt6-plugins"
    first = installation.install_kde_plugin(source, plugin_dir)
    assert installation.install_kde_plugin(source, plugin_dir) == first
    target = Path(first["installed"])
    assert target.read_bytes() == source.read_bytes()
    assert str(target) in manifest()["files"]
    result = installation.uninstall(activate=False)
    assert str(target) in result["removed"]
    assert not target.exists()
    assert source.exists()


def test_optional_kde_plugin_preserves_user_edits(isolated, tmp_path):
    source = elf_fixture(tmp_path)
    plugin_dir = Path.home() / "qt6-plugins"
    result = installation.install_kde_plugin(source, plugin_dir)
    target = Path(result["installed"])
    target.write_bytes(b"User replacement")
    with pytest.raises(ValueError, match="edited"):
        installation.install_kde_plugin(source, plugin_dir)
    assert str(target) in installation.uninstall(activate=False)["preserved"]
    assert target.read_bytes() == b"User replacement"


def test_optional_kde_plugin_rejects_nonlocal_destination_and_non_elf(isolated, tmp_path):
    source = elf_fixture(tmp_path)
    with pytest.raises(ValueError, match="user-local"):
        installation.install_kde_plugin(source, tmp_path / "outside-home")
    with pytest.raises(ValueError, match="absolute"):
        installation.install_kde_plugin(source, Path("relative"))
    source.write_text("not a plugin")
    with pytest.raises(ValueError, match="ELF"):
        installation.install_kde_plugin(source, Path.home() / "plugins")


def test_optional_kde_plugin_rejects_symlink_escape(isolated, tmp_path):
    source = elf_fixture(tmp_path)
    plugin_dir = Path.home() / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "kf6").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="outside"):
        installation.install_kde_plugin(source, plugin_dir)

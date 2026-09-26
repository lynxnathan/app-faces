import os

import pytest
from gi.repository import GLib

from app_faces.core import GROUP, executable_from_exec
from app_faces.launchers import add_launcher, remove_launcher, rollback_launchers


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    app = tmp_path / 'an app $x`b`"percent%\\.bin'
    app.write_text("not executed")
    app.chmod(0o700)
    directory = tmp_path / "applications"
    return app, directory


def add(app, directory, **kwargs):
    return add_launcher(
        app, "My App", "app-icon", applications_dir=directory, search_dirs=[directory], **kwargs
    )


def test_exec_round_trip_and_explicit_identity(setup):
    app, directory = setup
    result = add(app, directory, application_id="org.example.App", wm_class="ObservedClass")
    kf = GLib.KeyFile()
    kf.load_from_file(str(result.path), GLib.KeyFileFlags.NONE)
    assert executable_from_exec(kf.get_string(GROUP, "Exec")) == app.resolve()
    assert kf.get_string(GROUP, "StartupWMClass") == "ObservedClass"
    assert result.path.name == "org.example.App.desktop"
    assert not result.reused


def test_reuses_existing_exact_entry_without_edits(setup):
    app, directory = setup
    first = add(app, directory)
    before = first.path.read_bytes()
    second = add(app, directory)
    assert second.reused
    assert second.path == first.path
    assert first.path.read_bytes() == before


def test_remove_preserves_user_edits(setup):
    app, directory = setup
    result = add(app, directory)
    result.path.write_text(result.path.read_text() + "Comment=Mine\n")
    with pytest.raises(ValueError, match="changed outside"):
        remove_launcher(result.path)
    assert result.path.exists()
    assert rollback_launchers()["preserved"] == [str(result.path)]


def test_rollback_managed_only(setup):
    app, directory = setup
    managed = add(app, directory)
    unrelated = directory / "unrelated.desktop"
    unrelated.write_text("other")
    assert rollback_launchers()["removed"] == [str(managed.path)]
    assert not managed.path.exists()
    assert unrelated.read_text() == "other"


def test_no_window_identity_guess(setup):
    app, directory = setup
    launcher = add(app, directory)
    assert "StartupWMClass" not in launcher.path.read_text()
    assert launcher.path.name.startswith("app-faces-")


def test_cannot_shadow_existing_id(setup):
    app, directory = setup
    directory.mkdir()
    existing = directory / "org.example.Other.desktop"
    existing.write_text("[Desktop Entry]\nType=Application\nName=Other\nExec=/bin/true\n")
    with pytest.raises(ValueError, match="another desktop entry"):
        add(app, directory, application_id="org.example.Other")
    assert "Other" in existing.read_text()


def test_symlink_replacement_preserved(setup):
    app, directory = setup
    result = add(app, directory)
    target = directory / "target"
    result.path.rename(target)
    result.path.symlink_to(target)
    with pytest.raises(ValueError, match="changed outside"):
        remove_launcher(result.path)
    assert target.exists()


def test_nonexecutable_is_rejected(setup):
    app, directory = setup
    app.chmod(0o600)

    assert not os.access(app, os.X_OK)
    with pytest.raises(ValueError, match="executable"):
        add(app, directory)


def test_identity_path_traversal_rejected(setup):
    app, directory = setup
    with pytest.raises(ValueError, match="ID"):
        add(app, directory, application_id="../outside")


def test_launcher_image_survives_source_deletion(setup):
    from pathlib import Path

    app, directory = setup
    icon = app.parent / "art.svg"
    icon.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="blue"/></svg>'
    )
    result = add_launcher(
        app, "Demo", str(icon), applications_dir=directory, search_dirs=[directory]
    )
    keyfile = GLib.KeyFile()
    keyfile.load_from_file(str(result.path), GLib.KeyFileFlags.NONE)
    stored = Path(keyfile.get_string(GROUP, "Icon"))
    icon.unlink()
    assert stored.is_file()
    assert stored != icon

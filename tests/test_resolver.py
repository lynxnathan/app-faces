import hashlib

import pytest

from app_faces.core import Resolver, desktop_entries, executable_from_exec


def entry(directory, identity, executable, icon="test-icon", extra=""):
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / identity
    f.write_text(
        f'[Desktop Entry]\nType=Application\nName=Test\nExec="{executable}" %U\nIcon={icon}\n{extra}'
    )
    return f


@pytest.fixture
def target(tmp_path):
    file = tmp_path / "an app"
    file.write_bytes(b"not executed")
    return file


def test_user_entry_wins(tmp_path, target):
    user, system = tmp_path / "user", tmp_path / "system"
    entry(system, "a.desktop", target, "system-icon")
    entry(user, "a.desktop", target, "user-icon")
    r = Resolver([user, system], {}).resolve(target, read_custom=False)
    assert (r.method, r.icon) == ("desktop", "user-icon")


def test_hidden_masks_system(tmp_path, target):
    user, system = tmp_path / "user", tmp_path / "system"
    entry(system, "a.desktop", target)
    entry(user, "a.desktop", target, extra="Hidden=true\n")
    assert list(desktop_entries([user, system])) == []


def test_nodisplay_still_has_identity(tmp_path, target):
    entry(tmp_path / "apps", "a.desktop", target, extra="NoDisplay=true\n")
    r = Resolver([tmp_path / "apps"], {}).resolve(target, read_custom=False)
    assert r.status == "resolved"


def test_two_launchers_are_ambiguous(tmp_path, target):
    for name in ["a.desktop", "b.desktop"]:
        entry(tmp_path / "apps", name, target)
    r = Resolver([tmp_path / "apps"], {}).resolve(target, read_custom=False)
    assert r.status == "ambiguous"
    assert len(r.candidates) == 2


def test_missing_icon_does_not_fall_through(tmp_path, target):
    entry(tmp_path / "apps", "a.desktop", target, "")
    assert Resolver([tmp_path / "apps"], {}).resolve(target, False).status == "missing-icon"


def test_symlink_resolves_to_same_app(tmp_path, target):
    link = tmp_path / "link"
    link.symlink_to(target)
    entry(tmp_path / "apps", "a.desktop", target)
    assert Resolver([tmp_path / "apps"], {}).resolve(link, False).status == "resolved"


@pytest.mark.parametrize(
    "command",
    [
        'sh -c "touch /tmp/not-executed"',
        "bash /tmp/test.sh",
        'env -S "app --thing"',
        'python3 -c "print(1)"',
        "flatpak run org.app.Test",
        "relative/path",
        '"unterminated',
        "app%F",
    ],
)
def test_wrappers_and_malformed_exec_not_guessed(command):
    assert executable_from_exec(command) is None


def test_env_and_spaces(target):
    assert executable_from_exec(f'env LANG=C "{target}" %F') == target


def test_interpreter_script_is_target(target):
    assert executable_from_exec(f'python3 "{target}"') == target


def test_custom_icon_precedes_desktop(monkeypatch, tmp_path, target):
    entry(tmp_path / "apps", "a.desktop", target)
    monkeypatch.setattr("app_faces.core.custom_icon", lambda p: "file:///chosen.png")
    assert Resolver([tmp_path / "apps"], {}).resolve(target).method == "user-icon"


def test_filename_only_suggests(tmp_path):
    target = tmp_path / "Blender-4.5-x86_64.AppImage"
    target.write_text("unrelated file can have this name")
    r = Resolver([], {"icons": [{"name": "Blender", "slug": "blender", "provider": "selfhst"}]})
    assert r.resolve(target, False).status == "suggested"


def test_exact_hash_opt_in(target):
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    r = Resolver([], {"fingerprints": {digest: {"id": "test", "name": "Test", "icon": "test"}}})
    assert r.resolve(target, False).status == "unknown"
    assert r.resolve(target, False, True).method == "sha256"

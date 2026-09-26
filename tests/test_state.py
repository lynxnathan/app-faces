import json

import pytest

from app_faces import state
from app_faces.core import fetch_icon, sync_catalog


@pytest.fixture
def metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    values = {}
    monkeypatch.setattr(state, "custom_icon", lambda p: values.get(str(p), ""))
    monkeypatch.setattr(state, "set_metadata", lambda p, v: values.__setitem__(str(p), v))
    target = tmp_path / "app"
    target.touch()
    icon = tmp_path / "icon.svg"
    icon.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="red"/></svg>'
    )
    return values, target, icon


def test_apply_and_undo(metadata):
    values, target, icon = metadata
    applied = state.apply(target, str(icon))
    assert values[str(target)] == applied
    assert applied != icon.as_uri()
    state.undo(target)
    assert values[str(target)] == ""


def test_preserve_existing_icon(metadata):
    values, target, icon = metadata
    values[str(target)] = "file:///original.png"
    with pytest.raises(ValueError, match="already has"):
        state.apply(target, str(icon))
    state.apply(target, str(icon), replace=True)
    state.undo(target)
    assert values[str(target)] == "file:///original.png"


def test_repeated_changes_restore_original(metadata):
    values, target, icon = metadata
    state.apply(target, str(icon))
    icon2 = icon.with_name("other.png")
    icon2.write_bytes(icon.read_bytes())
    state.apply(target, str(icon2), replace=True)
    state.undo(target)
    assert values[str(target)] == ""


def test_external_edit_not_overwritten_on_undo(metadata):
    values, target, icon = metadata
    state.apply(target, str(icon))
    values[str(target)] = "file:///someone-elses-choice.png"
    with pytest.raises(ValueError, match="outside"):
        state.undo(target)
    assert values[str(target)] == "file:///someone-elses-choice.png"


def test_corrupt_journal_preserved(metadata):
    _, target, icon = metadata
    root = state.data_dir()
    root.mkdir(parents=True)
    (root / "changes.json").write_text("broken")
    with pytest.raises(json.JSONDecodeError):
        state.apply(target, str(icon))


@pytest.mark.parametrize("slug", ["../evil", "a/b", "A bad slug", "x?query=true"])
def test_provider_path_injection_rejected(slug):
    with pytest.raises(ValueError):
        fetch_icon("selfhst", slug)


def test_failed_sync_keeps_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    root = tmp_path / "app-faces"
    root.mkdir()
    file = root / "catalog.json"
    file.write_text('{"icons": ["existing"]}')
    monkeypatch.setattr("app_faces.core.download", lambda *_: b"not json")
    with pytest.raises(RuntimeError):
        sync_catalog()
    assert "existing" in file.read_text()


def test_sync_both_providers_and_preserve_fingerprints(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    root = tmp_path / "app-faces"
    root.mkdir()
    (root / "catalog.json").write_text(
        json.dumps({"fingerprints": {"a" * 64: {"id": "test", "name": "Test", "icon": "test"}}})
    )

    def response(url, limit):
        if url.startswith("https://api.github.com/"):
            return json.dumps({"sha": "a" * 40}).encode()
        if "selfhst" in url:
            return json.dumps([{"Name": "Test", "Reference": "test", "PNG": "Yes"}]).encode()
        return json.dumps({"png": ["test.png", "../bad.png"]}).encode()

    monkeypatch.setattr("app_faces.core.download", response)
    assert sync_catalog()["icons"] == 2
    catalog = json.loads((root / "catalog.json").read_text())
    assert {x["provider"] for x in catalog["icons"]} == {"selfhst", "dashboard"}
    assert catalog["fingerprints"]["a" * 64]["id"] == "test"


def test_rollback_preserves_external_edits(metadata):
    values, target, icon = metadata
    state.apply(target, str(icon))
    values[str(target)] = "file:///later-choice.png"
    report = state.rollback_all()
    assert len(report["preserved"]) == 1
    assert not report["restored"]
    assert values[str(target)] == "file:///later-choice.png"


def test_automatic_race_preserves_new_user_choice(metadata):
    values, target, icon = metadata
    state.apply(target, str(icon), automatic=True)
    assert state.prepare_automatic(target) == (True, True)
    values[str(target)] = "file:///user-choice.png"
    with pytest.raises(ValueError, match="ownership changed"):
        state.apply(target, str(icon), automatic=True, replace=True)
    assert values[str(target)] == "file:///user-choice.png"


def test_rollback_restores_and_suppresses(metadata):
    values, target, icon = metadata
    state.apply(target, str(icon), automatic=True)
    report = state.rollback_all()
    assert report["restored"] == [str(target)]
    assert values[str(target)] == ""
    assert (
        json.loads((state.data_dir() / "disabled.json").read_text())[str(target)]
        == target.stat().st_ino
    )


def test_choice_survives_source_image_deletion(metadata):
    from pathlib import Path
    from urllib.parse import unquote, urlsplit

    _, target, icon = metadata
    uri = state.apply(target, str(icon))
    icon.unlink()
    assert Path(unquote(urlsplit(uri).path)).is_file()
    state.undo(target)


def test_marker_notifies_file_monitor_without_changing_binary(metadata):
    import os
    import time

    from gi.repository import Gio, GLib

    _, target, icon = metadata
    target.write_bytes(b"\x7fELF portable fixture")
    os.chmod(target, 0o751)
    before = target.stat()
    content = target.read_bytes()
    monitor = Gio.File.new_for_path(str(target)).monitor_file(Gio.FileMonitorFlags.NONE, None)
    events = []
    monitor.connect("changed", lambda _m, _f, _other, event: events.append(event))
    try:
        uri = state.apply(target, str(icon))
        assert os.getxattr(target, state.REFRESH_ATTRIBUTE) == uri.encode()
        deadline = time.monotonic() + 2
        while Gio.FileMonitorEvent.ATTRIBUTE_CHANGED not in events and time.monotonic() < deadline:
            while GLib.MainContext.default().pending():
                GLib.MainContext.default().iteration(False)
            time.sleep(0.01)
        assert Gio.FileMonitorEvent.ATTRIBUTE_CHANGED in events
        assert state.refresh_warning(target) == ""
        assert state.undo(target) == ""
        with pytest.raises(OSError):
            os.getxattr(target, state.REFRESH_ATTRIBUTE)
        after = target.stat()
        assert target.read_bytes() == content
        assert (before.st_ino, before.st_dev, before.st_mtime_ns, before.st_mode) == (
            after.st_ino,
            after.st_dev,
            after.st_mtime_ns,
            after.st_mode,
        )
    finally:
        monitor.cancel()


def test_marker_restores_arbitrary_prior_bytes_across_repeated_changes(metadata):
    import os

    _, target, icon = metadata
    original = b"\xff\x00\x80prior-marker"
    os.setxattr(target, state.REFRESH_ATTRIBUTE, original)
    state.apply(target, str(icon))
    state.apply(target, str(icon), replace=True)
    state.undo(target)
    assert os.getxattr(target, state.REFRESH_ATTRIBUTE) == original


def test_marker_external_edit_wins_during_rollback(metadata):
    import os

    values, target, icon = metadata
    state.apply(target, str(icon))
    os.setxattr(target, state.REFRESH_ATTRIBUTE, b"later-external-choice")
    result = state.rollback_all()
    assert result["restored"] == [str(target)]
    assert values[str(target)] == ""
    assert os.getxattr(target, state.REFRESH_ATTRIBUTE) == b"later-external-choice"


def test_marker_inode_replacement_is_not_touched(metadata):
    import os

    _, target, icon = metadata
    state.apply(target, str(icon), automatic=True)
    target.rename(target.with_name("original-inode"))
    target.write_bytes(b"replacement")
    os.setxattr(target, state.REFRESH_ATTRIBUTE, b"replacement-marker")
    with pytest.raises(ValueError, match="replaced"):
        state.undo(target)
    state.clear_automatic(target)
    assert os.getxattr(target, state.REFRESH_ATTRIBUTE) == b"replacement-marker"


def test_marker_device_mismatch_is_not_touched(metadata):
    import os

    _, target, icon = metadata
    state.apply(target, str(icon), automatic=True)
    record_file = state.data_dir() / "changes.json"
    records = json.loads(record_file.read_text())
    records[str(target)]["device"] += 1
    record_file.write_text(json.dumps(records))
    marker = os.getxattr(target, state.REFRESH_ATTRIBUTE)
    with pytest.raises(ValueError, match="replaced"):
        state.undo(target)
    state.clear_automatic(target)
    assert os.getxattr(target, state.REFRESH_ATTRIBUTE) == marker


@pytest.mark.parametrize("operation", ["getxattr", "setxattr"])
def test_marker_unavailable_does_not_fail_icon_application(metadata, monkeypatch, operation):
    import errno

    values, target, icon = metadata

    def denied(*_args, **_kwargs):
        raise OSError(errno.EOPNOTSUPP, "unsupported extended attributes")

    monkeypatch.setattr(state.os, operation, denied)
    uri = state.apply(target, str(icon))
    assert values[str(target)] == uri
    assert state.refresh_warning(target) == state.REFRESH_NOTICE
    state.undo(target)
    assert values[str(target)] == ""


def test_failed_gvfs_write_leaves_marker_and_prior_journal_unchanged(metadata, monkeypatch):
    import os

    _, target, icon = metadata
    os.setxattr(target, state.REFRESH_ATTRIBUTE, b"\xffexisting")

    def failed(*_args):
        raise OSError("metadata write failed")

    monkeypatch.setattr(state, "set_metadata", failed)
    with pytest.raises(OSError, match="metadata write failed"):
        state.apply(target, str(icon))
    assert os.getxattr(target, state.REFRESH_ATTRIBUTE) == b"\xffexisting"
    assert json.loads((state.data_dir() / "changes.json").read_text()) == {}


def test_marker_restore_failure_keeps_recovery_and_retry_finishes(metadata, monkeypatch):
    import errno
    import os

    values, target, icon = metadata
    state.apply(target, str(icon))
    remove = os.removexattr

    def failed(*_args, **_kwargs):
        raise OSError(errno.EACCES, "temporarily denied")

    monkeypatch.setattr(state.os, "removexattr", failed)
    assert state.undo(target) == state.REFRESH_NOTICE
    assert values[str(target)] == ""
    record = json.loads((state.data_dir() / "changes.json").read_text())[str(target)]
    assert record["restoring"] and record["refresh_marker"]["status"] == "restore_failed"
    monkeypatch.setattr(state.os, "removexattr", remove)
    assert state.undo(target) == ""
    assert json.loads((state.data_dir() / "changes.json").read_text()) == {}
    with pytest.raises(OSError):
        os.getxattr(target, state.REFRESH_ATTRIBUTE)


def test_marker_recovery_is_persisted_before_attribute_mutation(metadata, monkeypatch):
    import base64
    import os

    _, target, icon = metadata
    original = b"\xffprior"
    os.setxattr(target, state.REFRESH_ATTRIBUTE, original)
    write = os.setxattr

    def checked(*args, **kwargs):
        record = json.loads((state.data_dir() / "changes.json").read_text())[str(target)]
        assert record["refresh_marker"]["status"] == "planned"
        assert base64.b64decode(record["refresh_marker"]["previous"]) == original
        return write(*args, **kwargs)

    monkeypatch.setattr(state.os, "setxattr", checked)
    state.apply(target, str(icon))


def test_new_apply_keeps_original_marker_recovery_after_partial_undo(metadata, monkeypatch):
    import errno
    import os

    _, target, icon = metadata
    state.apply(target, str(icon))
    remove = os.removexattr
    monkeypatch.setattr(
        state.os, "removexattr", lambda *_: (_ for _ in ()).throw(OSError(errno.EACCES, "denied"))
    )
    state.undo(target)
    monkeypatch.setattr(state.os, "removexattr", remove)
    state.apply(target, str(icon), replace=True)
    state.undo(target)
    with pytest.raises(OSError):
        os.getxattr(target, state.REFRESH_ATTRIBUTE)


def test_clear_automatic_restores_prior_marker_and_retries_partial_cleanup(metadata, monkeypatch):
    import errno
    import os

    values, target, icon = metadata
    state.apply(target, str(icon), automatic=True)
    remove = os.removexattr
    monkeypatch.setattr(
        state.os, "removexattr", lambda *_: (_ for _ in ()).throw(OSError(errno.EACCES, "denied"))
    )
    state.clear_automatic(target)
    assert values[str(target)] == ""
    assert str(target) in json.loads((state.data_dir() / "changes.json").read_text())
    monkeypatch.setattr(state.os, "removexattr", remove)
    state.clear_automatic(target)
    assert json.loads((state.data_dir() / "changes.json").read_text()) == {}
    with pytest.raises(OSError):
        os.getxattr(target, state.REFRESH_ATTRIBUTE)


def test_rollback_reports_marker_recovery_still_pending(metadata, monkeypatch):
    import errno

    _, target, icon = metadata
    state.apply(target, str(icon))
    monkeypatch.setattr(
        state.os, "removexattr", lambda *_: (_ for _ in ()).throw(OSError(errno.EACCES, "denied"))
    )
    result = state.rollback_all()
    assert result["restored"] == []
    assert "refresh marker recovery pending" in result["preserved"][0]


def test_kde_apply_undo_refresh_hint_preserves_binary(metadata):
    import hashlib

    _, target, icon = metadata
    before = (
        hashlib.sha256(target.read_bytes()).hexdigest(),
        target.stat().st_mode,
        target.stat().st_mtime_ns,
    )
    state.apply(target, str(icon), backend="kde")
    assert state.refresh_warning(target) == state.KDE_REFRESH_NOTICE
    assert state.undo(target) == state.KDE_REFRESH_NOTICE
    assert (
        hashlib.sha256(target.read_bytes()).hexdigest(),
        target.stat().st_mode,
        target.stat().st_mtime_ns,
    ) == before
    with state.journal() as (_, changes):
        assert str(target) not in changes

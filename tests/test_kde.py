import json
from pathlib import Path

import pytest

from app_faces import kde
from app_faces.core import Resolver


def test_journal_artwork_and_replacement_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app = tmp_path / "application"
    app.write_text("test")
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"icon")
    root = tmp_path / "app-faces"
    root.mkdir()
    records = {str(app): {"inode": app.stat().st_ino, "applied": icon.as_uri()}}
    journal = root / "changes.json"
    journal.write_text(json.dumps(records))
    resolver = Resolver(directories=[], catalog={})
    assert kde.thumbnail_icon(app, resolver) == icon
    records[str(app)]["inode"] = -1
    journal.write_text(json.dumps(records))
    assert kde.thumbnail_icon(app, resolver) is None


def test_filename_suggestions_do_not_become_previews(tmp_path):
    app = tmp_path / "blender.AppImage"
    app.touch()
    resolver = Resolver(
        directories=[],
        catalog={"icons": [{"slug": "blender", "name": "Blender", "provider": "selfhst"}]},
    )
    assert kde.thumbnail_icon(app, resolver) is None


def test_thumbnail_writes_decoded_png(tmp_path, monkeypatch):
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    icon = tmp_path / "original.png"
    image = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 8)
    image.fill(0xFF0000FF)
    image.savev(str(icon), "png", [], [])
    monkeypatch.setattr(kde, "thumbnail_icon", lambda _: icon)
    output = tmp_path / "thumb.png"
    assert kde.write_thumbnail(tmp_path / "unused", output, 64)
    thumb = GdkPixbuf.Pixbuf.new_from_file(str(output))
    assert thumb.get_width() == 64
    assert thumb.get_height() == 32


def test_unknown_and_invalid_size_do_not_write(tmp_path, monkeypatch):
    monkeypatch.setattr(kde, "thumbnail_icon", lambda _: None)
    output = tmp_path / "thumb.png"
    assert not kde.write_thumbnail(tmp_path / "missing", output, 64)
    with pytest.raises(ValueError):
        kde.write_thumbnail(tmp_path / "missing", output, 9000)
    assert not output.exists()


def test_kf6_metadata_disables_stale_thumbnail_cache_and_handles_executables():
    root = Path(__file__).parents[1] / "adapters/kde"
    metadata = json.loads((root / "appfacesthumbnail.json").read_text())
    assert metadata["CacheThumbnail"] is False
    assert "application/x-executable" in metadata["KPlugin"]["MimeTypes"]

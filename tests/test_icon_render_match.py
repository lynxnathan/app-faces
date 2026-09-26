import importlib.util
from pathlib import Path

import pytest


def test_resized_pattern_matches_but_mirrored_same_palette_and_generic_do_not(tmp_path):
    pytest.importorskip("gi")
    path = Path(__file__).resolve().parents[1] / "tests/integration/icon_render_match.py"
    spec = importlib.util.spec_from_file_location("icon_render_match", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from gi.repository import GLib

    pixbuf = module.GdkPixbuf

    data = bytearray()
    for y in range(96):
        for x in range(128):
            glyph = (24 < x < 42 and 14 < y < 80) or (24 < x < 94 and 65 < y < 80)
            data.extend((255, 255, 255) if glyph else (20, 100 + y, 210))
    artwork = pixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(data)), pixbuf.Colorspace.RGB, False, 8, 128, 96, 128 * 3
    )
    template = tmp_path / "artwork.png"
    artwork.savev(str(template), "png", [], [])
    screen = pixbuf.Pixbuf.new(pixbuf.Colorspace.RGB, False, 8, 140, 120)
    screen.fill(0xE4E4E4FF)
    shot = tmp_path / "screen.png"
    screen.savev(str(shot), "png", [], [])
    assert not module.match_icon(shot, template, (20, 10, 96, 85))["matched"]
    artwork.scale_simple(48, 36, pixbuf.InterpType.BILINEAR).copy_area(0, 0, 48, 36, screen, 44, 16)
    screen.savev(str(shot), "png", [], [])
    assert module.match_icon(shot, template, (20, 10, 96, 85))["matched"]
    artwork.flip(True).savev(str(template), "png", [], [])
    assert not module.match_icon(shot, template, (20, 10, 96, 85))["matched"]

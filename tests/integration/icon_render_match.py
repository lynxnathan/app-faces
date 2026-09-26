import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402


def match_icon(screenshot, artwork, bounds, coordinate_margin=0):
    screen = GdkPixbuf.Pixbuf.new_from_file(str(screenshot))
    source = GdkPixbuf.Pixbuf.new_from_file(str(artwork))
    pixels, stride, channels = screen.get_pixels(), screen.get_rowstride(), screen.get_n_channels()
    left, top, width, height = bounds
    assert left >= 0 and top >= 0 and width > 0 and height > 0
    best = {"meanChannelError": 255.0, "matchingFraction": 0.0, "matched": False}
    for size in range(40, min(66, width, height - 16), 2):
        scaled_height = round(size * source.get_height() / source.get_width())
        scaled = source.scale_simple(size, scaled_height, GdkPixbuf.InterpType.BILINEAR)
        data, row, nc = scaled.get_pixels(), scaled.get_rowstride(), scaled.get_n_channels()
        samples = []
        for y in range(2, scaled_height - 2, 3):
            for x in range(2, size - 2, 3):
                offset = y * row + x * nc
                if nc == 3 or data[offset + 3] >= 250:
                    samples.append((x, y, data[offset : offset + 3]))
        assert len(samples) >= 30, "Artwork has too little opaque detail for this visual oracle"

        for ox in range(
            left + (width - size) // 2 - 4 - coordinate_margin,
            left + (width - size) // 2 + 5 + coordinate_margin,
        ):
            for oy in range(
                max(0, top - coordinate_margin), top + height - size - 16 + coordinate_margin
            ):
                if ox < 0 or oy + size > screen.get_height() or ox + size > screen.get_width():
                    continue
                total, close = 0, 0
                for x, y, rgb in samples:
                    index = (oy + y) * stride + (ox + x) * channels
                    error = sum(abs(pixels[index + c] - rgb[c]) for c in range(3)) / 3
                    total += error
                    close += error <= 25
                    if total > best["meanChannelError"] * len(samples):
                        break
                else:
                    mean = total / len(samples)
                    fraction = close / len(samples)
                    if mean < best["meanChannelError"]:
                        best = {
                            "meanChannelError": mean,
                            "matchingFraction": fraction,
                            "matched": mean <= 12 and fraction >= 0.9,
                            "x": ox,
                            "y": oy,
                            "size": size,
                            "sampleCount": len(samples),
                        }
    return best

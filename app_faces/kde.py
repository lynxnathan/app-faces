import argparse
import json
import sys
from pathlib import Path

import gi

from .core import Resolver, data_dir, icon_path


def thumbnail_icon(path: Path, resolver: Resolver | None = None) -> Path | None:
    path = path.absolute()
    if not path.is_file():
        return None
    journal = data_dir() / "changes.json"
    records = json.loads(journal.read_text()) if journal.exists() else {}
    record = records.get(str(path))
    stat = path.stat()
    if record and record["inode"] == stat.st_ino:
        same_device = record.get("device", stat.st_dev) == stat.st_dev
        fresh = record.get("mode") != "automatic" or (
            record.get("size", stat.st_size) == stat.st_size
            and record.get("mtime_ns", stat.st_mtime_ns) == stat.st_mtime_ns
        )
        if same_device and fresh:
            return icon_path(str(record["applied"]))
    disabled_file = data_dir() / "disabled.json"
    disabled = json.loads(disabled_file.read_text()) if disabled_file.exists() else {}
    if disabled.get(str(path)) == path.stat().st_ino:
        return None
    match = (resolver or Resolver()).resolve(path, read_custom=False)
    if match.status != "resolved":
        return None
    return icon_path(match.icon)


def write_thumbnail(path: Path, output: Path, size: int) -> bool:
    if not 1 <= size <= 1024:
        raise ValueError("Thumbnail size must be between 1 and 1024")
    icon = thumbnail_icon(path)
    if icon is None:
        return False
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), size, size, True)
    pixbuf.savev(str(output), "png", [], [])
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["thumbnail"])
    parser.add_argument("path", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("size", type=int)
    args = parser.parse_args()
    try:
        return 0 if write_thumbnail(args.path, args.output, args.size) else 1
    except Exception as exc:
        print(f"app-faces KDE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

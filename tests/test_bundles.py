import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from app_faces.bundles import _listing, _regular, _run, _safe_svg, extract_appimage, squashfs_offset


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    if not shutil.which("mksquashfs"):
        pytest.skip("squashfs-tools unavailable")
    root = tmp_path / "AppDir"
    root.mkdir()
    (root / "demo.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Demo\nIcon=demo\nExec=DO-NOT-EXECUTE\n"
    )
    (root / "demo.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    (root / ".DirIcon").symlink_to("demo.png")
    return root


def pack(root: Path) -> Path:
    fs = root.parent / "filesystem"
    subprocess.run(
        ["mksquashfs", str(root), str(fs), "-noappend", "-processors", "1", "-quiet"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    header = bytearray(128)
    header[:6] = b"\x7fELF\x02\x01"
    header[8:11] = b"AI\x02"
    struct.pack_into("<Q", header, 40, 64)
    struct.pack_into("<HH", header, 58, 64, 1)
    image = root.parent / "demo.AppImage"
    image.write_bytes(header + fs.read_bytes())
    return image


def test_extract_uses_archive_tools_without_executing_candidate(
    bundle: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = pack(bundle)
    original_popen = subprocess.Popen
    commands = []

    def guarded_popen(args, *positional, **kwargs):
        commands.append(args)
        assert Path(args[0]).name == "unsquashfs"
        assert not kwargs.get("shell", False)
        return original_popen(args, *positional, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", guarded_popen)
    assert squashfs_offset(image) == 128
    result = extract_appimage(image, image.parent / "cache")
    assert result is not None
    assert result.name == "Demo"
    assert result.application_id == "demo.desktop"
    assert result.icon.read_bytes().endswith(b"fixture")
    assert commands
    assert not (image.parent / "squashfs-root").exists()


@pytest.mark.parametrize("missing", ["demo.png", "demo.desktop"])
def test_missing_required_asset(bundle: Path, missing: str) -> None:
    (bundle / missing).unlink()
    image = pack(bundle)
    assert extract_appimage(image, image.parent / "cache") is None


def test_two_valid_desktop_entries_are_ambiguous(bundle: Path) -> None:
    (bundle / "second.desktop").write_bytes((bundle / "demo.desktop").read_bytes())
    image = pack(bundle)
    assert extract_appimage(image, image.parent / "cache") is None
    (bundle / "second.desktop").unlink()
    image = pack(bundle)
    assert extract_appimage(image, image.parent / "cache") is not None


def test_internal_desktop_symlink_preserves_public_application_id(bundle: Path) -> None:
    nested = bundle / "usr/share/applications"
    nested.mkdir(parents=True)
    (bundle / "demo.desktop").rename(nested / "internal.desktop")
    (bundle / "demo.desktop").symlink_to("usr/share/applications/internal.desktop")
    image = pack(bundle)
    result = extract_appimage(image, image.parent / "cache")
    assert result is not None
    assert result.name == "Demo"
    assert result.application_id == "demo.desktop"


@pytest.mark.parametrize("target", ["../outside.desktop", "/etc/example.desktop", "demo.desktop"])
def test_unsafe_desktop_symlink_rejected(bundle: Path, target: str) -> None:
    (bundle / "demo.desktop").unlink()
    (bundle / "demo.desktop").symlink_to(target)
    image = pack(bundle)
    assert extract_appimage(image, image.parent / "cache") is None


def test_second_desktop_symlink_remains_ambiguous(bundle: Path) -> None:
    (bundle / "alias.desktop").symlink_to("demo.desktop")
    image = pack(bundle)
    assert extract_appimage(image, image.parent / "cache") is None


def test_external_symlink_does_not_read_host(bundle: Path) -> None:
    (bundle / ".DirIcon").unlink()
    (bundle / "demo.png").unlink()
    secret = bundle.parent / "secret.png"
    secret.write_bytes(b"\x89PNG\r\n\x1a\nsecret")
    (bundle / ".DirIcon").symlink_to(secret)
    image = pack(bundle)
    assert extract_appimage(image, image.parent / "cache") is None


def test_listing_and_symlink_traversal() -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        _listing(b"-rw-r--r-- 0/0 3 2026-01-01 00:00 squashfs-root/../secret")
    assert _regular(".DirIcon", {".DirIcon": ("l", "../../secret")}) is None
    assert _regular(".DirIcon", {".DirIcon": ("l", ".DirIcon")}) is None


def test_bounded_subprocess() -> None:
    with pytest.raises(ValueError, match="output limit"):
        _run(["/usr/bin/printf", "123456789"], 4)
    with pytest.raises(ValueError, match="timed out"):
        _run(["/usr/bin/sleep", "1"], 8, timeout=0.01)


def test_plain_elf_is_not_appimage(tmp_path: Path) -> None:
    path = tmp_path / "app"
    path.write_bytes(b"\x7fELF" + bytes(124))
    assert squashfs_offset(path) is None


def test_svg_rejects_external_resources() -> None:
    assert _safe_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
    assert not _safe_svg(b'<svg><image href="file:///etc/passwd"/></svg>')
    assert not _safe_svg(b'<svg><style>@import "https://example.com";</style></svg>')
    assert not _safe_svg(b'<svg><path fill="url(https://example.com/image)"/></svg>')
    assert not _safe_svg(b"<svg><script>alert(1)</script></svg>")

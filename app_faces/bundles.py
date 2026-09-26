import configparser
import hashlib
import os
import posixpath
import re
import selectors
import shutil
import struct
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MAX_HEADER_SCAN_BYTES = 32 * 1024 * 1024
ARCHIVE_TIMEOUT_SECONDS = 15
ARCHIVE_READ_CHUNK_BYTES = 65_536
MIN_PROCESS_WAIT_SECONDS = 0.01
MAX_SYMLINK_DEPTH = 16
MAX_ARCHIVE_LISTING_BYTES = 4_000_000
MAX_DESKTOP_ENTRY_BYTES = 128_000
MAX_BUNDLED_ICON_BYTES = 4_000_000
SQUASHFS_HEADER_BYTES = 96
SQUASHFS_MIN_BLOCK_BYTES = 4_096
SQUASHFS_MAX_BLOCK_BYTES = 1_048_576
ELF64_HEADER_BYTES = 64
ELF32_HEADER_BYTES = 52
ELF64_SECTION_OFFSET_FIELD = 40
ELF32_SECTION_OFFSET_FIELD = 32
ELF64_SECTION_SIZE_FIELD = 58
ELF32_SECTION_SIZE_FIELD = 46
SQUASHFS_VERSION_FIELD = 28
SQUASHFS_BLOCK_SIZE_FIELD = 12
SQUASHFS_USED_BYTES_FIELD = 40


class DesktopParser(configparser.ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


@dataclass(frozen=True)
class BundleIcon:
    name: str
    icon: Path
    application_id: str
    evidence: str


def squashfs_offset(path: Path) -> int | None:
    with path.open("rb") as stream:
        data = stream.read(MAX_HEADER_SCAN_BYTES)
    if len(data) < ELF64_HEADER_BYTES or data[:4] != b"\x7fELF" or data[8:11] != b"AI\x02":
        return None
    if data[4] not in (1, 2) or data[5] not in (1, 2):
        return None
    endian = "<" if data[5] == 1 else ">"
    is64 = data[4] == 2

    shoff = struct.unpack_from(
        endian + ("Q" if is64 else "I"),
        data,
        ELF64_SECTION_OFFSET_FIELD if is64 else ELF32_SECTION_OFFSET_FIELD,
    )[0]
    shsize, shnum = struct.unpack_from(
        endian + "HH", data, ELF64_SECTION_SIZE_FIELD if is64 else ELF32_SECTION_SIZE_FIELD
    )
    end = max(ELF64_HEADER_BYTES if is64 else ELF32_HEADER_BYTES, shoff + shsize * shnum)
    if end > len(data):
        return None
    offset = data.find(b"hsqs", end)
    file_size = path.stat().st_size
    while offset >= 0:
        if offset + SQUASHFS_HEADER_BYTES <= len(data):
            major, minor = struct.unpack_from("<HH", data, offset + SQUASHFS_VERSION_FIELD)
            block_size = struct.unpack_from("<I", data, offset + SQUASHFS_BLOCK_SIZE_FIELD)[0]
            used = struct.unpack_from("<Q", data, offset + SQUASHFS_USED_BYTES_FIELD)[0]
            if (
                major == 4
                and minor == 0
                and SQUASHFS_MIN_BLOCK_BYTES <= block_size <= SQUASHFS_MAX_BLOCK_BYTES
                and block_size & (block_size - 1) == 0
                and SQUASHFS_HEADER_BYTES <= used <= file_size - offset
            ):
                return offset
        offset = data.find(b"hsqs", offset + 4)
    return None


def _run(arguments: list[str], limit: int, timeout: float = ARCHIVE_TIMEOUT_SECONDS) -> bytes:
    process = subprocess.Popen(
        arguments,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("AppImage inspection timed out")
                if not selector.select(remaining):
                    raise ValueError("AppImage inspection timed out")
                chunk = os.read(
                    process.stdout.fileno(), min(ARCHIVE_READ_CHUNK_BYTES, limit + 1 - len(output))
                )
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > limit:
                    raise ValueError("AppImage inspection exceeds output limit")
        if process.wait(timeout=max(MIN_PROCESS_WAIT_SECONDS, deadline - time.monotonic())) != 0:
            raise ValueError("Invalid or unsupported AppImage filesystem")
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        if process.stdout:
            process.stdout.close()


def _safe_name(name: str) -> bool:
    return (
        bool(name)
        and not name.startswith(("/", "-"))
        and not any(part in ("..", ".") for part in name.split("/"))
        and not any(ord(char) < 32 for char in name)
        and "\\" not in name
    )


def _listing(content: bytes) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for line in content.decode("utf-8", errors="strict").splitlines():
        match = re.match(
            r"^([dl-])[rwxstST-]{9}\s+\S+\s+\d+\s+\S+\s+\S+\s+squashfs-root/(.+)$", line
        )
        if not match:
            continue
        kind, name = match.groups()
        target = ""
        if kind == "l":
            name, separator, target = name.partition(" -> ")
            if not separator:
                continue
        if not _safe_name(name):
            raise ValueError("Unsafe archive path")
        if name in entries:
            raise ValueError("Ambiguous archive listing")
        entries[name] = kind, target
    return entries


def _regular(name: str, entries: dict[str, tuple[str, str]]) -> str | None:
    visited: set[str] = set()
    for _ in range(MAX_SYMLINK_DEPTH):
        if not _safe_name(name) or name in visited or name not in entries:
            return None
        visited.add(name)
        kind, target = entries[name]
        if kind == "-":
            if any(
                entries.get(str(parent), ("d", ""))[0] != "d"
                for parent in PurePosixPath(name).parents
                if str(parent) != "."
            ):
                return None
            return name
        if kind != "l" or target.startswith("/"):
            return None
        name = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    return None


def _safe_svg(data: bytes) -> bool:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        return False
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return False
    if root.tag.rsplit("}", 1)[-1] != "svg":
        return False
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() in ("script", "foreignobject"):
            return False
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1].lower() == "href" and not value.startswith("#"):
                return False
        for value in [*node.attrib.values(), node.text or ""]:
            if "@import" in value.lower():
                return False
            for target in re.findall(r"url\s*\((.*?)\)", value, re.IGNORECASE):
                if not target.strip(" \"'").startswith("#"):
                    return False
    return True


def extract_appimage(path: Path, cache_directory: Path) -> BundleIcon | None:
    tool = shutil.which("unsquashfs")
    if not tool:
        return None
    path = path.resolve()
    try:
        before = path.stat()
        offset = squashfs_offset(path)
        if offset is None:
            return None
        common = [tool, "-processors", "1", "-mem", "32M", "-no-wildcards", "-offset", str(offset)]
        entries = _listing(_run(common + ["-lln", str(path)], MAX_ARCHIVE_LISTING_BYTES))
        desktop_names = [
            n
            for n, (kind, _) in entries.items()
            if "/" not in n and n.endswith(".desktop") and kind in ("-", "l")
        ]
        if len(desktop_names) != 1:
            return None
        desktop_name = desktop_names[0]
        desktop_file = _regular(desktop_name, entries)
        if desktop_file is None:
            return None
        desktop = DesktopParser(interpolation=None, strict=True)
        desktop.read_string(
            _run(common + ["-cat", str(path), desktop_file], MAX_DESKTOP_ENTRY_BYTES).decode(
                "utf-8"
            )
        )
        entry = desktop["Desktop Entry"]
        if entry.get("Type") != "Application" or entry.get("Hidden", "").lower() == "true":
            return None
        candidates = [".DirIcon"]
        icon_name = entry.get("Icon", "")
        if _safe_name(icon_name):
            candidates.extend([icon_name, icon_name + ".png", icon_name + ".svg"])
            candidates.extend(
                sorted(
                    n
                    for n in entries
                    if n.startswith("usr/share/icons/")
                    and PurePosixPath(n).name in (icon_name, icon_name + ".png", icon_name + ".svg")
                )
            )
        data = b""
        for candidate in candidates:
            regular = _regular(candidate, entries)
            if regular:
                data = _run(common + ["-cat", str(path), regular], MAX_BUNDLED_ICON_BYTES)
                break
        if not data:
            return None

        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            suffix = ".png"
        elif _safe_svg(data):
            suffix = ".svg"
        else:
            return None
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            return None
        cache_directory.mkdir(parents=True, exist_ok=True)
        destination = cache_directory / (hashlib.sha256(data).hexdigest() + suffix)
        fd, temporary = tempfile.mkstemp(dir=cache_directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return BundleIcon(
            entry.get("Name", path.stem),
            destination,
            desktop_name,
            f"Type-2 AppImage bundled icon at offset {offset}",
        )
    except (
        OSError,
        ValueError,
        UnicodeError,
        configparser.Error,
        KeyError,
        subprocess.TimeoutExpired,
    ):
        return None

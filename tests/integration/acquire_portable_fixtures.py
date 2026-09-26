import hashlib
import json
import shutil
import tarfile
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build/portable-fixtures"
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = [
    (
        "Godot",
        "https://godotengine.org/download/linux/",
        "https://downloads.godotengine.org/?flavor=stable&platform=linux.64&slug=linux.x86_64.zip&version=4.7.2",
        "godot.zip",
    ),
    (
        "Telegram",
        "https://desktop.telegram.org/",
        "https://telegram.org/dl/desktop/linux",
        "telegram.tar.xz",
    ),
]
manifest = {
    "retrieved_at": datetime.now(UTC).isoformat(),
    "executed": False,
    "uploads": False,
    "fixtures": [],
}
for name, page, source, filename in SOURCES:
    archive = OUT / filename
    request = urllib.request.Request(
        source, headers={"User-Agent": "AppFaces/0.2 fixture verification"}
    )
    with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as out:
        total = 0
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > 300_000_000:
                raise ValueError("Archive exceeds test download limit")
            out.write(block)
        final = response.url
    if filename.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            candidates = [i for i in z.infolist() if i.filename.endswith("linux.x86_64")]
            if len(candidates) != 1 or candidates[0].file_size > 1_000_000_000:
                raise ValueError("Unexpected Godot archive shape")
            member = candidates[0]
            target = OUT / "Godot" / Path(member.filename).name
            target.parent.mkdir(exist_ok=True)
            with z.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive, "r:xz") as t:
            member = t.getmember("Telegram/Telegram")
            if not member.isfile() or member.size > 1_000_000_000:
                raise ValueError("Unexpected Telegram archive shape")
            target = OUT / "Telegram/Telegram"
            target.parent.mkdir(exist_ok=True)
            with t.extractfile(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    target.chmod(0o700)
    with target.open("rb") as stream:
        assert stream.read(4) == b"\x7fELF"
    manifest["fixtures"].append(
        {
            "name": name,
            "official_page": page,
            "source_url": source,
            "download_url": final,
            "archive": str(archive),
            "archive_sha256": hashlib.file_digest(archive.open("rb"), "sha256").hexdigest(),
            "executable": str(target),
            "sha256": hashlib.file_digest(target.open("rb"), "sha256").hexdigest(),
            "bytes": target.stat().st_size,
            "publisher_checksum_verified": False,
            "icon_redistribution_permission": "not assessed",
        }
    )
controls = OUT / "negative-controls"
controls.mkdir(exist_ok=True)
for name in ("Telegram",):
    path = controls / name
    shutil.copyfile("/usr/bin/true", path)
    path.chmod(0o700)
manifest["negative_controls"] = [str(controls / n) for n in ("Telegram",)]
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(
    json.dumps(
        {
            "manifest": str(OUT / "manifest.json"),
            "applications": [f["name"] for f in manifest["fixtures"]],
        }
    )
)

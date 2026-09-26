import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from app_faces.automatic import candidates, run_once
from app_faces.catalog import publish
from app_faces.core import Resolver, atomic_json, custom_icon
from app_faces.identity import fingerprint
from app_faces.state import undo

parser = argparse.ArgumentParser()
parser.add_argument("--path", type=Path, required=True)
parser.add_argument("--icon", type=Path, required=True)
parser.add_argument("--app-id", required=True)
parser.add_argument("--name", required=True)
parser.add_argument("--artwork-source", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
path = args.path.resolve(strict=True)
root = Path(__file__).resolve().parents[2]
asset = args.icon.resolve(strict=True)
original = custom_icon(path)
before_stat = path.stat()
before_hash = fingerprint(path)
resolver = Resolver()
baseline = resolver.resolve(path, fingerprint=True)
was_candidate = path in candidates(resolver)
report = dict(
    path=str(path),
    size=before_stat.st_size,
    sha256=before_hash,
    baseline=baseline.to_dict(),
    discovered_by_real_scanner=was_candidate,
    artwork_source=args.artwork_source,
    seeded_mapping_is_test_only=True,
    program_executed=False,
)
if original:
    raise SystemExit(
        "Existing custom icon present; preserve it and choose an uncustomized test copy"
    )
assert was_candidate, "Selected file is not found by the background scanner"
with tempfile.TemporaryDirectory(prefix="app-faces-integration-") as directory:
    temporary = Path(directory)
    os.environ.update(
        XDG_DATA_HOME=str(temporary / "data"),
        XDG_CACHE_HOME=str(temporary / "cache"),
        XDG_CONFIG_HOME=str(temporary / "config"),
    )
    atomic_json(
        temporary / "config/app-faces/config.json", {"directories": [], "automatic_enabled": True}
    )
    publish(
        {
            "version": 1,
            "icons": [],
            "fingerprints": {
                before_hash: {
                    "id": args.app_id,
                    "name": args.name,
                    "icon": str(asset),
                    "source": args.artwork_source,
                }
            },
        }
    )
    try:
        recognized = Resolver().resolve(path, fingerprint=True)
        assert recognized.method == "sha256" and recognized.name == args.name

        with patch("app_faces.automatic.candidates", return_value=[path]):
            first = run_once()
            assert len(first["applied"]) == 1 and not first["errors"], first
            applied = custom_icon(path)
            assert applied and applied != original
            undo(path)
            assert custom_icon(path) == original
            second = run_once()
            assert not second["applied"] and custom_icon(path) == original
        report.update(seeded_auto_apply=True, real_gvfs_restore=True, undo_prevents_reapply=True)
    finally:
        if custom_icon(path) != original:
            undo(path, suppress=False)
        assert custom_icon(path) == original

after_hash = hashlib.sha256(path.read_bytes()).hexdigest()
assert after_hash == before_hash and path.stat().st_mode == before_stat.st_mode
report.update(binary_unchanged=True, original_icon_restored=True, passed=True)
atomic_json(args.output, report)
print(json.dumps(report, indent=2))

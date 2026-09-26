import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app_faces.catalog import publish, validate
from app_faces.core import Resolver
from app_faces.identity import fingerprint
from app_faces.state import store_icon


def seed(evidence_path: Path, icon: Path, application_id: str, name: str) -> dict[str, Any]:
    evidence = json.loads(evidence_path.read_text())
    target = Path(evidence["path"])
    if not application_id.strip() or not name.strip() or not evidence.get("artwork_source"):
        raise ValueError("Unexpected artwork provenance")
    if not evidence.get("passed") or fingerprint(target) != evidence.get("sha256"):
        raise ValueError("Exact build no longer matches the provided evidence")
    previous = validate(Resolver().catalog)
    digest = evidence["sha256"]
    if digest in previous.get("fingerprints", {}):
        raise ValueError("A mapping already exists; preserve the user's existing choice")

    backup_revision = publish(previous)
    artwork = store_icon(str(icon))
    updated = dict(previous)
    updated["fingerprints"] = dict(previous.get("fingerprints", {}))
    updated["fingerprints"][digest] = {
        "id": application_id,
        "name": name,
        "icon": str(artwork),
        "provenance": {
            "kind": "local-user-identified-exact-build",
            "evidence": str(evidence_path),
            "source": evidence["artwork_source"],
            "license": "unknown; local use only; no redistribution authorized",
            "scope": "this user's exact file bytes; no version or publisher verification",
        },
    }
    revision = publish(updated)
    result = Resolver().resolve(target, read_custom=False, fingerprint=True)
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "backup_revision": backup_revision,
        "revision": revision,
        "status": result.status,
        "method": result.method,
        "name": result.name,
        "artwork_local": artwork.is_file(),
        "build_scope": "User-identified exact build, no publisher verification",
        "upload_performed": False,
        "icon_applied_by_script": False,
        "rollback": f"app-faces catalog --revision {backup_revision}",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed a user-identified exact build in the local catalog"
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--icon", type=Path, required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = seed(args.evidence, args.icon, args.app_id, args.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

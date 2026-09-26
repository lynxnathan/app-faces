#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

PROJECT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--endpoint", default="http://localhost:8787")
parser.add_argument("--secrets-file", type=Path)
parser.add_argument("--result", type=Path, default=PROJECT / "state/community-integration.json")
args = parser.parse_args()
ENDPOINT = args.endpoint.rstrip("/")
RESULT = args.result


def moderator_token() -> str:
    if args.secrets_file:
        secrets = json.loads(args.secrets_file.read_text())
        reviewers = json.loads(secrets["REVIEWERS"])
        return str(next(r["token"] for r in reviewers if r["role"] == "admin"))
    for line in (PROJECT / "backend/.dev.vars").read_text().splitlines():
        if line.startswith("REVIEWERS="):
            value = shlex.split(line.partition("=")[2])
            reviewers = json.loads(value[0])
            for reviewer in reviewers:
                if reviewer["role"] == "admin":
                    return str(reviewer["token"])
    raise RuntimeError("No local admin reviewer configured")


def admin_request(path: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        ENDPOINT + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
            "User-Agent": "AppFaces/0.2",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return cast(dict[str, Any], json.load(response))


def main() -> int:
    result: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "endpoint": ENDPOINT,
        "scope": "Synthetic fixture only; isolated temporary XDG client state; explicitly selected backend",
        "checks": [],
        "passed": False,
    }
    checks = cast(list[str], result["checks"])
    try:
        with urllib.request.urlopen(
            urllib.request.Request(ENDPOINT + "/health", headers={"User-Agent": "AppFaces/0.2"}),
            timeout=5,
        ) as response:
            assert json.load(response)["ok"] is True
        token = moderator_token()
        checks.append("Backend healthy; moderator secret read without logging")
        with tempfile.TemporaryDirectory(prefix="app-faces-community-integration-") as tmp:
            base = Path(tmp)
            for key, name in (
                ("XDG_CONFIG_HOME", "config"),
                ("XDG_DATA_HOME", "data"),
                ("XDG_CACHE_HOME", "cache"),
                ("XDG_STATE_HOME", "state"),
            ):
                os.environ[key] = str(base / name)

            sys.path.insert(0, str(PROJECT))
            from app_faces import community
            from app_faces.core import data_dir

            config = base / "config/app-faces/config.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"community_url": ENDPOINT}))
            fixture_id = uuid.uuid4().hex
            application_id = "org.appfaces.Integration." + fixture_id
            svg = base / "fixture.svg"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
                f'<rect width="64" height="64" fill="#{fixture_id[:6]}"/>'
                f'<circle cx="32" cy="32" r="20" fill="#{fixture_id[6:12]}"/></svg>'
            )
            payload = community.preview(
                application_id,
                "App Faces synthetic integration fixture",
                str(svg),
                source_url="https://example.invalid/app-faces-synthetic-fixture",
                license_name="CC0-1.0; synthetic integration fixture",
                variant="synthetic-test",
            )
            assert set(payload) == {
                "applicationId",
                "name",
                "sourceUrl",
                "license",
                "variant",
                "iconBase64",
            }
            assert str(base) not in json.dumps(payload)
            checks.append(
                "SVG normalized to upload PNG; preview contains only allowlisted metadata"
            )
            try:
                community.enqueue(payload, consent=False)
                raise AssertionError("Upload accepted without consent")
            except ValueError:
                pass
            assert not list((data_dir() / "outbox").glob("*.json"))
            identity = community.enqueue(payload, consent=True)
            assert community.enqueue(payload, consent=True) == identity
            outcomes = community.drain_outbox()
            assert outcomes == [{"id": identity, "status": "submitted"}], outcomes
            assert community.drain_outbox() == []
            checks.append(
                "No-consent enqueue refused; consented enqueue and real upload succeed once"
            )
            item = json.loads((data_dir() / "outbox" / f"{identity}.json").read_text())
            remote_id = item["receipt"]["id"]
            assert community.submission_status(identity)["status"] == "pending"
            assert not any(
                e["id"] == application_id for e in community.sync_approved()["applications"]
            )
            checks.append(
                "Private receipt reports pending; pending association absent from public catalog"
            )
            decision_path = f"/admin/submissions/{remote_id}/decision"
            approval = admin_request(
                decision_path,
                token,
                {
                    "action": "approve",
                    "version": 0,
                    "reason": "Synthetic deployment integration test",
                },
            )
            assert approval["status"] == "approved"
            assert community.submission_status(identity)["status"] == "approved"
            manifest = community.sync_approved()
            entry = next(e for e in manifest["applications"] if e["id"] == application_id)
            cached = community.fetch_approved(application_id)
            assert cached.is_relative_to(base)
            assert cached.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            assert hashlib.sha256(cached.read_bytes()).hexdigest() == entry["sha256"]
            assert community.fetch_approved(application_id) == cached
            checks.append(
                "Approval visible via receipt; catalog sync and verified PNG download/cache succeed"
            )
            revoked = admin_request(
                decision_path,
                token,
                {"action": "revoke", "version": 1, "reason": "Remove synthetic test artwork"},
            )
            assert revoked["status"] == "revoked"
            assert community.submission_status(identity)["status"] == "revoked"
            assert not any(
                e["id"] == application_id for e in community.sync_approved()["applications"]
            )
            try:
                community.fetch_approved(application_id)
                raise AssertionError("Revoked mapping still fetchable through client")
            except ValueError:
                pass
            try:
                urllib.request.urlopen(
                    urllib.request.Request(
                        entry["iconUrl"], headers={"User-Agent": "AppFaces/0.2"}
                    ),
                    timeout=5,
                )
                raise AssertionError("Revoked asset still publicly served")
            except urllib.error.HTTPError as error:
                assert error.code == 404
            checks.append(
                "Revocation removes catalog mapping; client refuses cached selection; asset endpoint 404"
            )
        checks.append("Temporary client state deleted; no real user configuration or icons changed")
        result["passed"] = True
    except Exception as error:
        result["failure_type"] = type(error).__name__
        result["failure_stage"] = len(checks)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "result": str(RESULT)}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

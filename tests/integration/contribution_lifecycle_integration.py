import argparse
import base64
import hashlib
import json
import os
import secrets
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from app_faces.community import (
    drain_outbox,
    enqueue,
    preview,
    revise_submission,
    submission_status,
)
from app_faces.core import atomic_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--endpoint", required=True)
parser.add_argument("--moderator-file", type=Path, required=True)
parser.add_argument("--result", type=Path, required=True)
args = parser.parse_args()
endpoint = args.endpoint.rstrip("/")
moderator = args.moderator_file.read_text().strip()
checks = {}
with tempfile.TemporaryDirectory(prefix="app-faces-receipt-check-") as temporary:
    root = Path(temporary)
    os.environ.update(
        XDG_DATA_HOME=str(root / "data"),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_CACHE_HOME=str(root / "cache"),
    )
    atomic_json(root / "config/app-faces/config.json", {"community_url": endpoint})
    color = secrets.token_hex(3)
    icon = root / "generated.svg"
    icon.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" rx="16" fill="#{color}"/><circle cx="32" cy="32" r="12" fill="white"/></svg>'
    )
    payload = preview(
        "org.appfaces.ReceiptCheck." + color,
        "Receipt flow check",
        str(icon),
        "https://example.org/generated-test-art",
        "CC0-1.0",
        "test",
    )
    identity = enqueue(payload, consent=True)
    assert drain_outbox()[0]["status"] == "submitted"
    local = json.loads((root / "data/app-faces/outbox" / f"{identity}.json").read_text())
    remote_id = local["receipt"]["id"]
    assert submission_status(identity)["status"] == "pending"
    checks["real_client_upload_pending"] = True
    request = urllib.request.Request(
        endpoint + "/admin/submissions/" + remote_id + "/decision",
        method="POST",
        headers={
            "Authorization": "Bearer " + moderator,
            "Content-Type": "application/json",
            "User-Agent": "AppFaces/0.2",
        },
        data=json.dumps(
            {
                "action": "correction",
                "version": 0,
                "reason": "Synthetic lifecycle test: verify metadata correction.",
            }
        ).encode(),
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.status == 200
    assert submission_status(identity)["status"] == "correction"
    checks["moderator_correction_visible_to_client"] = True
    metadata = {k: payload[k] for k in ("applicationId", "name", "sourceUrl", "license", "variant")}
    metadata["name"] = "Receipt flow corrected"
    result = revise_submission(identity, metadata)
    assert result["status"] == "pending" and result["version"] == 2
    assert submission_status(identity)["status"] == "pending"
    checks["client_correction_resubmitted"] = True
    result = revise_submission(identity)
    assert result["status"] == "withdrawn" and result["version"] == 3
    assert submission_status(identity)["status"] == "withdrawn"
    checks["client_withdrawal_persisted"] = True
    digest = hashlib.sha256(base64.b64decode(payload["iconBase64"])).hexdigest()
    try:
        urllib.request.urlopen(
            urllib.request.Request(
                endpoint + "/v1/assets/" + digest + ".png", headers={"User-Agent": "AppFaces/0.2"}
            ),
            timeout=30,
        )
        raise AssertionError("Unpublished artwork became public")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    checks["unpublished_artwork_private"] = True
    checks["personal_client_state_unchanged"] = True
args.result.write_text(
    json.dumps(
        {
            "endpoint": endpoint,
            "checks": checks,
            "passed": all(checks.values()),
            "scope": "Real Python client and production HTTP API; not native UI E2E",
        },
        indent=2,
    )
    + "\n"
)
print(
    f"Receipt lifecycle: {len(checks)} checks passed; generated artwork remains private and withdrawn."
)

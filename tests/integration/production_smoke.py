import base64
import json
import os
import struct
import time
import urllib.error
import urllib.request
import uuid
import zlib
from pathlib import Path

root = Path(__file__).resolve().parents[2]
endpoint = "https://app-faces-catalog.lynxnathan.workers.dev"
secrets = json.loads((Path.home() / ".config/app-faces/cloudflare-secrets.json").read_text())
token = json.loads(secrets["REVIEWERS"])[0]["token"]


def request(path, payload=None, admin=False, headers=None):
    options = {"User-Agent": "AppFaces/0.2", **(headers or {})}
    if admin:
        options["Authorization"] = "Bearer " + token
    if payload is not None:
        options["Content-Type"] = "application/json"
    req = urllib.request.Request(
        endpoint + path,
        headers=options,
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.status, response.read()


def chunk(name, content):
    block = name + content
    return struct.pack(">I", len(content)) + block + struct.pack(">I", zlib.crc32(block))


checks = []
status, content = request("/admin")
assert status == 200 and b"Access password" in content
checks.append("HTTPS approval page served")
try:
    request("/admin/submissions")
    raise AssertionError("Unauthorized admin access allowed")
except urllib.error.HTTPError as error:
    assert error.code == 401
checks.append("Unauthenticated moderation rejected with 401")
status, queue = request("/admin/submissions", admin=True)
assert status == 200 and json.loads(queue)["reviewer"]["role"] == "admin"
checks.append("Production reviewer secret authenticates as admin")
for width, height, channels in [(512, 512, 4), (512, 170, 3)]:
    raw = b"".join(
        b"\0" + (os.urandom(width * channels) if channels == 3 else b"\x81" * (width * channels))
        for _ in range(height)
    )
    image = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(
            b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6 if channels == 4 else 2, 0, 0, 0)
        )
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    assert len(image) <= 262144
    identity = uuid.uuid4().hex
    payload = dict(
        applicationId="org.appfaces.CpuTest." + identity,
        name="Synthetic deployment boundary test",
        sourceUrl="https://example.invalid/generated-test",
        license="CC0-1.0",
        variant="synthetic-test",
        iconBase64=base64.b64encode(image).decode(),
    )
    started = time.monotonic()
    status, receipt = request("/v1/submissions", payload, headers={"Idempotency-Key": identity})
    assert status == 201
    receipt = json.loads(receipt)
    elapsed = time.monotonic() - started

    status, decision = request(
        "/admin/submissions/" + receipt["id"] + "/decision",
        dict(
            action="reject", version=0, reason="Synthetic deployment CPU/boundary check completed"
        ),
        admin=True,
    )
    assert status == 200 and json.loads(decision)["status"] == "rejected"
    checks.append(
        dict(
            dimensions=[width, height],
            png_bytes=len(image),
            upload_http=201,
            wall_seconds=round(elapsed, 3),
            test_proposal_rejected=True,
        )
    )
report = dict(
    endpoint=endpoint,
    passed=True,
    checks=checks,
    free_plan_evidence="Cloudflare deployment API code100328 confirmed Free; custom CPU limits removed, fixed Free quota applies",
    r2_used=False,
)
(root / "state/production-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))

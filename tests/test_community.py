import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app_faces import community


@pytest.fixture
def configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(community, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(community, "settings", lambda: {"community_url": "https://catalog.example"})
    monkeypatch.setattr(community, "png_bytes", lambda _: b"PNG fixture")
    return tmp_path


def payload() -> dict[str, str]:
    return community.preview("org.demo.App", "Demo", "/private/local/path.png")


def test_consent_and_allowlisted_payload(configured: Path) -> None:
    value = payload()
    assert set(value) == {"applicationId", "name", "sourceUrl", "license", "variant", "iconBase64"}
    assert "/private" not in json.dumps(value)
    with pytest.raises(ValueError, match="opt-in"):
        community.enqueue(value, False)
    with pytest.raises(ValueError, match="Unexpected"):
        community.enqueue(dict(value, executable="/secret"), True)
    identity = community.enqueue(value, True)
    assert community.enqueue(value, True) == identity
    assert len(list((configured / "outbox").glob("*.json"))) == 1


def test_retry_idempotency_endpoint_and_receipt(
    configured: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = community.enqueue(payload(), True)
    requests: list[urllib.request.Request] = []

    def read(request: urllib.request.Request, limit: int) -> bytes:
        requests.append(request)
        if len(requests) == 1:
            raise urllib.error.HTTPError(request.full_url, 429, "throttled", {}, None)
        return json.dumps(
            {"id": "a" * 32, "receipt": "private-token", "status": "pending"}
        ).encode()

    monkeypatch.setattr(community, "_read", read)
    assert community.drain_outbox()[0]["status"] == "pending"
    assert community.drain_outbox() == []
    community.retry_submission(identity)
    monkeypatch.setattr(community, "settings", lambda: {"community_url": "https://new.example"})
    assert community.drain_outbox()[0]["status"] == "submitted"
    assert requests[0].get_header("Idempotency-key") == requests[1].get_header("Idempotency-key")
    assert requests[1].full_url.startswith("https://catalog.example/")
    assert set(json.loads(requests[1].data)) == set(payload())

    def status(request: urllib.request.Request, limit: int) -> bytes:
        assert request.get_header("Authorization") == "Receipt private-token"
        assert request.full_url == "https://catalog.example/v1/submissions/" + "a" * 32
        return b'{"status":"approved","reason":"Looks good"}'

    monkeypatch.setattr(community, "_read", status)
    assert community.submission_status(identity)["status"] == "approved"


def test_cancel_and_path_validation(configured: Path) -> None:
    identity = community.enqueue(payload(), True)
    community.cancel_submission(identity)
    assert community.drain_outbox() == []
    with pytest.raises(ValueError):
        community.retry_submission(identity)
    with pytest.raises(ValueError):
        community.submission_status("../../etc/passwd")


def test_redirects_rejected_before_forwarding() -> None:
    handler = community.NoRedirect()
    request = urllib.request.Request("https://catalog.example/v1/submissions", data=b"private")
    with pytest.raises(ValueError, match="redirects"):
        handler.redirect_request(request, None, 307, "redirect", {}, "https://other.example/upload")


def test_approved_integrity_and_invalid_catalog_preserves_cache(
    configured: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = b"\x89PNG\r\n\x1a\nfixture"
    digest = hashlib.sha256(image).hexdigest()
    value = {
        "schemaVersion": 1,
        "applications": [
            {
                "id": "org.demo.App",
                "name": "Demo",
                "sha256": digest,
                "iconUrl": "https://catalog.example/v1/assets/" + digest + ".png",
            }
        ],
    }
    monkeypatch.setattr(community, "_read", lambda *_: json.dumps(value).encode())
    community.sync_approved()
    saved = (configured / "community-catalog.json").read_bytes()
    value["applications"][0]["iconUrl"] = "https://catalog.example/v1/assets/../../secret"
    with pytest.raises(ValueError):
        community.sync_approved()
    assert (configured / "community-catalog.json").read_bytes() == saved
    monkeypatch.setattr(community, "_read", lambda *_: b"wrong")
    with pytest.raises(ValueError, match="integrity"):
        community.fetch_approved("org.demo.App")
    monkeypatch.setattr(community, "_read", lambda *_: image)
    assert community.fetch_approved("org.demo.App").read_bytes() == image


def test_catalog_requests_identify_client_and_keep_redirect_protection(monkeypatch):
    import io

    captured = []

    class Opener:
        def open(self, request, timeout):
            captured.append(request)
            assert timeout == 20
            return io.BytesIO(b"{}")

    def build(handler):
        assert isinstance(handler, community.NoRedirect)
        return Opener()

    monkeypatch.setattr(community.urllib.request, "build_opener", build)
    assert community._read("https://catalog.example/v1/catalog", 100) == b"{}"
    assert captured[0].get_header("User-agent") == "AppFaces/0.2"


def test_correction_retry_reuses_operation_after_uncertain_response(
    configured: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = community.enqueue(payload(), True)
    file = configured / "outbox" / (identity + ".json")
    stored = json.loads(file.read_text())
    stored.update(status="submitted", receipt={"id": "a" * 32, "receipt": "secret"})
    file.write_text(json.dumps(stored))
    metadata = {k: v for k, v in payload().items() if k != "iconBase64"}
    metadata["sourceUrl"] = "https://example.com/art"
    requests: list[urllib.request.Request] = []

    def read(request: urllib.request.Request, limit: int) -> bytes:
        requests.append(request)
        if request.get_method() == "GET":
            return b'{"status":"correction","version":2}'
        if len(requests) == 2:
            raise TimeoutError("response lost after server commit")
        return b'{"status":"pending","version":3,"reason":""}'

    monkeypatch.setattr(community, "_read", read)
    with pytest.raises(TimeoutError):
        community.revise_submission(identity, metadata)
    assert json.loads(file.read_text())["operation"]["body"]["version"] == 2
    community.revise_submission(identity, metadata)
    assert len(requests) == 3
    assert requests[1].data == requests[2].data
    assert requests[1].get_header("Idempotency-key") == requests[2].get_header("Idempotency-key")
    assert "operation" not in json.loads(file.read_text())
    assert community.submissions()[0]["sourceUrl"] == "https://example.com/art"
    assert "secret" not in json.dumps(community.submissions())


def test_withdraw_terminal_and_conflict_refresh(
    configured: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = community.enqueue(payload(), True)
    file = configured / "outbox" / (identity + ".json")
    stored = json.loads(file.read_text())
    stored.update(status="submitted", receipt={"id": "a" * 32, "receipt": "secret"})
    file.write_text(json.dumps(stored))
    monkeypatch.setattr(community, "_read", lambda *_: b'{"status":"approved","version":2}')
    with pytest.raises(ValueError, match="already reviewed"):
        community.revise_submission(identity)
    assert "operation" not in json.loads(file.read_text())

    def conflict(request: urllib.request.Request, limit: int) -> bytes:
        if request.get_method() == "GET":
            return b'{"status":"pending","version":2}'
        raise urllib.error.HTTPError(request.full_url, 409, "stale", {}, None)

    monkeypatch.setattr(community, "_read", conflict)
    with pytest.raises(urllib.error.HTTPError):
        community.revise_submission(identity)
    assert "operation" not in json.loads(file.read_text())


def test_failed_unsent_contribution_can_be_cancelled(configured: Path) -> None:
    identity = community.enqueue(payload(), True)
    file = configured / "outbox" / (identity + ".json")
    stored = json.loads(file.read_text())
    stored["status"] = "failed"
    file.write_text(json.dumps(stored))
    community.cancel_submission(identity)
    assert community.submission_status(identity, refresh=False)["status"] == "cancelled"

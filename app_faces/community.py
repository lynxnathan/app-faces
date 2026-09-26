import base64
import fcntl
import hashlib
import json
import os
import re
import secrets
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, ParamSpec, TypeVar, cast

import gi

from .core import atomic_json, data_dir, icon_path
from .i18n import t

HTTP_TIMEOUT_SECONDS = 20
MAX_SOURCE_IMAGE_BYTES = 8_000_000
MAX_CATALOG_BYTES = 8_000_000
MAX_RESPONSE_BYTES = 64_000
MAX_COMMUNITY_ICON_BYTES = 256 * 1024
RETRY_MAX_SECONDS = 86_400
RETRY_BASE_SECONDS = 60
RETRY_MAX_EXPONENT = 10
RECEIPT_TOKEN_BYTES = 32


P = ParamSpec("P")
R = TypeVar("R")


def serialized_outbox(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        root = data_dir()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "outbox.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return function(*args, **kwargs)

    return wrapped


def settings() -> dict[str, Any]:
    file = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "app-faces/config.json"
    )
    value = json.loads(file.read_text()) if file.exists() else {}
    if not isinstance(value, dict):
        raise ValueError("Invalid community settings")
    return cast(dict[str, Any], value)


def endpoint() -> str:
    url = str(settings().get("community_url", "")).rstrip("/")
    if not url:
        raise ValueError("Community sharing is not configured yet")
    return _validate_endpoint(url)


def _validate_endpoint(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Invalid community endpoint")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("Community endpoint requires HTTPS (localhost development allowed)")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise ValueError("Community redirects are not allowed")


def _read(request: str | urllib.request.Request, limit: int) -> bytes:
    if isinstance(request, str):
        request = urllib.request.Request(request)
    request.add_header("User-Agent", "AppFaces/0.2")
    with urllib.request.build_opener(NoRedirect()).open(
        request, timeout=HTTP_TIMEOUT_SECONDS
    ) as response:
        content = bytes(response.read(limit + 1))
    if len(content) > limit:
        raise ValueError("Community response exceeds size limit")
    return content


def _object(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Invalid community response")
    return cast(dict[str, Any], value)


def png_bytes(icon: str) -> bytes:
    asset = icon_path(icon)
    if not asset or asset.stat().st_size > MAX_SOURCE_IMAGE_BYTES:
        raise ValueError("Choose an available image smaller than 8 MB")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    for size in (512, 256, 128):
        image = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(asset), size, size, True)
        ok, content = image.save_to_bufferv("png", [], [])
        if ok and len(content) <= MAX_COMMUNITY_ICON_BYTES:
            return bytes(content)
    raise ValueError("Image is too large for community submission")


def preview(
    application_id: str,
    name: str,
    icon: str,
    source_url: str = "",
    license_name: str = "Unknown — review required",
    variant: str = "custom",
) -> dict[str, str]:
    if not application_id.strip() or not name.strip():
        raise ValueError("Application ID and name are required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,159}", application_id):
        raise ValueError("Use an application ID, not a file path")
    if source_url and urllib.parse.urlsplit(source_url).scheme not in {"https", "http"}:
        raise ValueError("Artwork source must be a public web URL, not a local path")
    return dict(
        applicationId=application_id,
        name=name,
        sourceUrl=source_url,
        license=license_name,
        variant=variant,
        iconBase64=base64.b64encode(png_bytes(icon)).decode("ascii"),
    )


@serialized_outbox
def enqueue(payload: dict[str, str], consent: bool) -> str:
    if not consent:
        raise ValueError("Sharing requires an explicit opt-in")

    url = endpoint()
    allowed = {"applicationId", "name", "sourceUrl", "license", "variant", "iconBase64"}
    if set(payload) != allowed:
        raise ValueError("Unexpected submission fields")
    raw = json.dumps(payload, sort_keys=True).encode()
    identity = hashlib.sha256(raw + url.encode()).hexdigest()
    queue = data_dir() / "outbox" / f"{identity}.json"
    if not queue.exists():
        atomic_json(
            queue,
            dict(
                payload=payload,
                idempotency_key=secrets.token_hex(RECEIPT_TOKEN_BYTES),
                endpoint=url,
                status="pending",
                attempts=0,
                next_attempt=0,
                created_at=time.time(),
            ),
        )
    return identity


@serialized_outbox
def drain_outbox(limit: int = 3) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for file in sorted((data_dir() / "outbox").glob("*.json")):
        if len(results) >= limit:
            break
        item = json.loads(file.read_text())
        if item["status"] != "pending" or item.get("next_attempt", 0) > time.time():
            continue
        request = urllib.request.Request(
            _validate_endpoint(str(item["endpoint"])) + "/v1/submissions",
            data=json.dumps(item["payload"]).encode(),
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": str(item.get("idempotency_key", file.stem)),
                "User-Agent": "AppFaces/0.2",
            },
            method="POST",
        )
        try:
            data = _object(_read(request, MAX_RESPONSE_BYTES))
            if not all(
                isinstance(data.get(key), str) and data[key] for key in ("id", "receipt", "status")
            ):
                raise ValueError("Invalid submission receipt")
            item.update(status="submitted", receipt=data)
            results.append({"id": file.stem, "status": "submitted"})
        except urllib.error.HTTPError as exc:
            item["last_error"] = f"HTTP {exc.code}"
            if exc.code in {400, 401, 403, 404, 405, 409, 410, 413, 415, 422}:
                item["status"] = "failed"
            else:
                item["next_attempt"] = time.time() + min(
                    RETRY_MAX_SECONDS,
                    RETRY_BASE_SECONDS * 2 ** min(item["attempts"], RETRY_MAX_EXPONENT),
                )
            results.append({"id": file.stem, "status": item["status"]})
        except (OSError, ValueError) as exc:
            item["last_error"] = str(exc)
            item["next_attempt"] = time.time() + min(
                RETRY_MAX_SECONDS,
                RETRY_BASE_SECONDS * 2 ** min(item["attempts"], RETRY_MAX_EXPONENT),
            )
            results.append({"id": file.stem, "status": "pending"})
        item["attempts"] += 1
        atomic_json(file, item)
    return results


@serialized_outbox
def cancel_submission(identity: str) -> None:
    if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("Invalid submission receipt")
    file = data_dir() / "outbox" / f"{identity}.json"
    item = json.loads(file.read_text())
    if item["status"] not in {"pending", "failed"}:
        raise ValueError("Submission already sent; use its review receipt for status")
    item["status"] = "cancelled"
    atomic_json(file, item)


def sync_approved() -> dict[str, Any]:
    url = endpoint()
    raw = _read(url + "/v1/catalog", MAX_CATALOG_BYTES)
    if len(raw) > MAX_CATALOG_BYTES:
        raise ValueError("Community catalog is too large")
    value = _object(raw)
    if value.get("schemaVersion") != 1 or not isinstance(value.get("applications"), list):
        raise ValueError("Unsupported community catalog")
    seen: set[str] = set()
    for entry in value["applications"]:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(k), str) for k in ("id", "name", "iconUrl", "sha256")
        ):
            raise ValueError("Invalid community application")
        if entry["id"] in seen:
            raise ValueError("Duplicate community application")
        seen.add(entry["id"])
        if entry["iconUrl"] != url + "/v1/assets/" + entry["sha256"] + ".png":
            raise ValueError("Community asset is outside configured provider")
        if len(entry["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in entry["sha256"]):
            raise ValueError("Invalid artwork digest")
    atomic_json(data_dir() / "community-catalog.json", value)
    return value


def approved_icons() -> list[dict[str, Any]]:
    file = data_dir() / "community-catalog.json"
    if not file.exists():
        return []
    catalog = json.loads(file.read_text())
    return [
        dict(
            name=e["name"],
            slug=e["id"],
            provider="community",
            attribution=e.get("license", ""),
            asset_license=e.get("license", "unknown"),
            source=e.get("sourceUrl", ""),
            url=e["iconUrl"],
            sha256=e["sha256"],
        )
        for e in catalog["applications"]
    ]


def fetch_approved(identity: str) -> Path:
    entries = [e for e in approved_icons() if e["slug"] == identity]
    if len(entries) != 1:
        raise ValueError("No unique approved community application")
    entry = entries[0]
    digest = str(entry["sha256"])
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("Invalid artwork digest")
    if entry["url"] != endpoint() + "/v1/assets/" + digest + ".png":
        raise ValueError("Community artwork provider changed")
    path = data_dir() / "artwork/community" / (digest + ".png")
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]:
        return path
    content = _read(str(entry["url"]), MAX_COMMUNITY_ICON_BYTES)
    if (
        len(content) > MAX_COMMUNITY_ICON_BYTES
        or hashlib.sha256(content).hexdigest() != entry["sha256"]
    ):
        raise ValueError("Community artwork integrity check failed")
    path.parent.mkdir(parents=True, exist_ok=True)

    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Community artwork must be PNG")
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def _submission(identity: str) -> tuple[Path, dict[str, Any]]:
    if not re.fullmatch(r"[a-f0-9]{64}", identity):
        raise ValueError("Invalid submission receipt")
    file = data_dir() / "outbox" / f"{identity}.json"
    return file, _object(file.read_bytes())


@serialized_outbox
def retry_submission(identity: str) -> None:
    file, item = _submission(identity)
    if item["status"] not in {"pending", "failed"}:
        raise ValueError("Only pending or failed submissions may be retried")
    item.update(status="pending", next_attempt=0)
    atomic_json(file, item)


@serialized_outbox
def submission_status(identity: str, refresh: bool = True) -> dict[str, str]:
    file, item = _submission(identity)
    result = {
        "id": identity,
        "status": str(item["status"]),
        "reason": str(item.get("last_error", "")),
    }
    review = item.get("review")
    if isinstance(review, dict):
        result.update(
            status=str(review.get("status", result["status"])), reason=str(review.get("reason", ""))
        )
    receipt = item.get("receipt")
    if refresh and isinstance(receipt, dict):
        remote_id, token = receipt.get("id"), receipt.get("receipt")
        if (
            not isinstance(remote_id, str)
            or not re.fullmatch(r"[a-f0-9]{32}", remote_id)
            or not isinstance(token, str)
        ):
            raise ValueError("Invalid stored submission receipt")
        request = urllib.request.Request(
            _validate_endpoint(str(item["endpoint"])) + "/v1/submissions/" + remote_id,
            headers={"Authorization": "Receipt " + token, "User-Agent": "AppFaces/0.2"},
        )
        response = _object(_read(request, MAX_RESPONSE_BYTES))
        if not isinstance(response.get("status"), str) or not isinstance(
            response.get("reason", ""), str
        ):
            raise ValueError("Invalid review status")
        item["review"] = response
        atomic_json(file, item)
        result.update(status=str(response["status"]), reason=str(response.get("reason", "")))
    return result


def submissions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file in sorted((data_dir() / "outbox").glob("*.json"), reverse=True):
        item = _object(file.read_bytes())
        payload = item["payload"]
        status = submission_status(file.stem, refresh=False)
        rows.append(
            dict(
                status,
                name=payload["name"],
                applicationId=payload["applicationId"],
                sourceUrl=payload["sourceUrl"],
                license=payload["license"],
                variant=payload["variant"],
                sent=bool(item.get("receipt")),
            )
        )
    return rows


@serialized_outbox
def revise_submission(identity: str, metadata: dict[str, str] | None = None) -> dict[str, Any]:
    file, item = _submission(identity)
    receipt = item.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError(t("Contribution not sent. Cancel the local upload."))
    remote_id, token = receipt.get("id"), receipt.get("receipt")
    if (
        not isinstance(remote_id, str)
        or not re.fullmatch(r"[a-f0-9]{32}", remote_id)
        or not isinstance(token, str)
    ):
        raise ValueError(t("Invalid contribution receipt"))
    allowed = {"applicationId", "name", "sourceUrl", "license", "variant"}
    if metadata is not None and set(metadata) != allowed:
        raise ValueError(t("Complete the contribution details"))
    action = "withdraw" if metadata is None else "correction"
    url = _validate_endpoint(str(item["endpoint"])) + "/v1/submissions/" + remote_id
    headers = {"Authorization": "Receipt " + token, "Content-Type": "application/json"}
    operation = item.get("operation")
    if (
        isinstance(operation, dict)
        and operation.get("action") == action
        and operation.get("metadata") == metadata
    ):
        body, key = operation["body"], operation["key"]
    else:
        review = _object(_read(urllib.request.Request(url, headers=headers), MAX_RESPONSE_BYTES))
        if review.get("status") not in {"pending", "correction"}:
            raise ValueError(t("Contribution already reviewed. Changes are no longer allowed."))
        version = review.get("version")
        if not isinstance(version, int):
            raise ValueError(t("Server did not return the contribution version"))
        body = {"version": version, **(metadata or {})}
        key = secrets.token_hex(RECEIPT_TOKEN_BYTES)
        item["operation"] = dict(action=action, metadata=metadata, body=body, key=key)
        atomic_json(file, item)
    headers["Idempotency-Key"] = key
    request = urllib.request.Request(
        url + "/" + action, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        response = _object(_read(request, MAX_RESPONSE_BYTES))
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            item.pop("operation", None)
            atomic_json(file, item)
        raise
    if not isinstance(response.get("status"), str) or not isinstance(response.get("version"), int):
        raise ValueError(t("Invalid response. Retry the same operation."))
    item["review"] = response
    if metadata is not None:
        item["payload"].update(metadata)
    item.pop("operation", None)
    atomic_json(file, item)
    return response

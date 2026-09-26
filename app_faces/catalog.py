import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from .core import SOURCE_REVISION, atomic_json, cache_dir, provider_asset_url
from .upstreams import IDENTIFIER, asset_url

MAX_CATALOG_ENTRIES = 50_000
MAX_CATALOG_FILE_BYTES = 16_000_000
MAX_APPLICATION_NAME_LENGTH = 200


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("Unsupported catalog version")
    icons = value.get("icons")
    if not isinstance(icons, list) or len(icons) > MAX_CATALOG_ENTRIES:
        raise ValueError("Invalid catalog icon list")
    for item in icons:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("provider"), str)
            or not IDENTIFIER.fullmatch(item["provider"])
            or item["provider"] == "community"
        ):
            raise ValueError("Invalid catalog provider")
        if not isinstance(item.get("slug"), str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]{0,150}", item["slug"]
        ):
            raise ValueError("Invalid catalog identifier")
        if (
            not isinstance(item.get("name"), str)
            or not 0 < len(item["name"]) <= MAX_APPLICATION_NAME_LENGTH
        ):
            raise ValueError("Invalid application name")
        revision = item.get("source_revision")
        if revision is not None:
            if not isinstance(revision, str) or not SOURCE_REVISION.fullmatch(revision):
                raise ValueError("Invalid catalog source revision")
            expected = (
                asset_url(item["source_repository"], item["slug"], revision)
                if "source_repository" in item
                else provider_asset_url(item["provider"], item["slug"], revision)
            )
            if item.get("source_url") != expected:
                raise ValueError("Catalog artwork URL does not match its source revision")
        elif "source_url" in item:
            raise ValueError("Catalog artwork URL requires a source revision")
    sources = value.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("Invalid catalog sources")
    for provider, revision in sources.items():
        if (
            not isinstance(provider, str)
            or not IDENTIFIER.fullmatch(provider)
            or not isinstance(revision, str)
            or not SOURCE_REVISION.fullmatch(revision)
        ):
            raise ValueError("Invalid catalog source revision")
        if any(
            item["provider"] == provider and item.get("source_revision") != revision
            for item in icons
        ):
            raise ValueError("Inconsistent catalog source revisions")
    fingerprints = value.get("fingerprints", {})
    if not isinstance(fingerprints, dict):
        raise ValueError("Invalid fingerprints")
    for key, entry in fingerprints.items():
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[a-f0-9]{64}", key)
            or not isinstance(entry, dict)
        ):
            raise ValueError("Invalid fingerprint")
        if not all(isinstance(entry.get(x), str) and entry[x] for x in ("id", "name", "icon")):
            raise ValueError("Invalid fingerprint identity")
    return cast(dict[str, Any], value)


def _revision(value: dict[str, Any]) -> str:
    content = dict(value)
    content.pop("revision", None)
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def publish(value: dict[str, Any]) -> str:
    validate(value)
    value = dict(value)
    value.pop("revision", None)
    revision = _revision(value)
    value["revision"] = revision
    root = cache_dir()
    atomic_json(root / "catalog-history" / f"{revision}.json", value)
    atomic_json(root / "catalog.json", value)
    return revision


def rollback(revision: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise ValueError("Invalid catalog revision")
    value = validate(json.loads((cache_dir() / "catalog-history" / f"{revision}.json").read_text()))
    if value.get("revision") != revision or _revision(value) != revision:
        raise ValueError("Catalog revision integrity check failed")
    atomic_json(cache_dir() / "catalog.json", value)
    return {"revision": revision}


def import_catalog(path: Path) -> str:
    if path.stat().st_size > MAX_CATALOG_FILE_BYTES:
        raise ValueError("Catalog exceeds size limit")
    return publish(validate(json.loads(path.read_text())))

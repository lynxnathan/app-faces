import hashlib
import json
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_PRIORITY = 100
DASHBOARD_SOURCE_PRIORITY = 200
MAX_SOURCE_PRIORITY = 10_000
MAX_SOURCE_CONFIG_BYTES = 65_536
MAX_CONFIGURED_SOURCES = 32
MAX_SOURCE_NAME_LENGTH = 200


IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,150}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*\Z")
REVISION = re.compile(r"[a-f0-9]{40}\Z")


def selfhst(document: Any) -> list[tuple[str, str]]:
    if not isinstance(document, list):
        raise ValueError("Invalid selfh.st metadata")
    result = []
    for item in document:
        if not isinstance(item, dict):
            raise ValueError("Invalid selfh.st entry")
        if item.get("PNG") == "Yes":
            slug, name = item.get("Reference"), item.get("Name")
            if not isinstance(slug, str) or not isinstance(name, str):
                raise ValueError("Invalid selfh.st entry name or reference")
            result.append((slug, name))
    return result


def dashboard(document: Any) -> list[tuple[str, str]]:
    if not isinstance(document, dict) or not isinstance(document.get("png"), list):
        raise ValueError("Invalid Dashboard Icons metadata")
    return [
        (filename[:-4], filename[:-4].replace("-", " ").title())
        for filename in document["png"]
        if isinstance(filename, str) and filename.endswith(".png")
    ]


ADAPTERS: dict[str, tuple[str, Callable[[Any], list[tuple[str, str]]]]] = {
    "selfhst": ("index.json", selfhst),
    "dashboard": ("tree.json", dashboard),
}


@dataclass(frozen=True)
class Source:
    id: str
    repository: str
    format: str
    ref: str = "main"
    enabled: bool = True
    priority: int = DEFAULT_SOURCE_PRIORITY


def validate_source(value: dict[str, Any]) -> Source:
    if set(value) - {"id", "repository", "format", "ref", "enabled", "priority"}:
        raise ValueError("Unknown upstream configuration field")
    source = Source(**value)
    if (
        not isinstance(source.id, str)
        or not IDENTIFIER.fullmatch(source.id)
        or source.id == "community"
    ):
        raise ValueError("Invalid upstream ID")
    if not isinstance(source.repository, str) or not REPOSITORY.fullmatch(source.repository):
        raise ValueError("Invalid upstream repository (expected owner/repository)")
    if not isinstance(source.format, str) or source.format not in ADAPTERS:
        raise ValueError("Unknown upstream format")
    if (
        not isinstance(source.ref, str)
        or not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", source.ref)
        or ".." in source.ref
    ):
        raise ValueError("Invalid upstream ref")
    if (
        type(source.enabled) is not bool
        or type(source.priority) is not int
        or not 0 <= source.priority <= MAX_SOURCE_PRIORITY
    ):
        raise ValueError("Invalid upstream enabled state or priority")
    return source


def sources() -> dict[str, Source]:
    result = {
        "selfhst": Source("selfhst", "selfhst/icons", "selfhst", priority=DEFAULT_SOURCE_PRIORITY),
        "dashboard": Source(
            "dashboard",
            "homarr-labs/dashboard-icons",
            "dashboard",
            priority=DASHBOARD_SOURCE_PRIORITY,
        ),
    }
    path = (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "app-faces/upstreams.toml"
    )
    if not path.exists():
        return result
    if path.stat().st_size > MAX_SOURCE_CONFIG_BYTES:
        raise ValueError("Upstream configuration exceeds size limit")
    document = tomllib.loads(path.read_text())
    if (
        set(document) != {"sources"}
        or not isinstance(document["sources"], list)
        or len(document["sources"]) > MAX_CONFIGURED_SOURCES
    ):
        raise ValueError("Expected at most 32 [[sources]] entries")
    seen = set()
    for value in document["sources"]:
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            raise ValueError("Upstream requires a stable ID")
        identity = value["id"]
        if identity in seen:
            raise ValueError("Duplicate upstream ID")
        seen.add(identity)
        base = asdict(result[identity]) if identity in result else {}
        try:
            result[identity] = validate_source(base | value)
        except TypeError as exc:
            raise ValueError("Incomplete upstream configuration") from exc
    return result


def records(source: Source, document: Any) -> list[tuple[str, str]]:
    entries = ADAPTERS[source.format][1](document)
    normalized: dict[str, str] = {}
    for slug, name in entries:
        if not isinstance(slug, str) or not IDENTIFIER.fullmatch(slug):
            continue
        if not isinstance(name, str) or not 0 < len(name) <= MAX_SOURCE_NAME_LENGTH:
            raise ValueError("Invalid application name")
        if slug in normalized and normalized[slug] != name:
            raise ValueError("Conflicting duplicate upstream slug")
        normalized[slug] = name
    if not normalized:
        raise ValueError("Empty provider metadata")
    return sorted(normalized.items())


def asset_url(repository: str, slug: str, revision: str) -> str:
    if (
        not REPOSITORY.fullmatch(repository)
        or not IDENTIFIER.fullmatch(slug)
        or not REVISION.fullmatch(revision)
    ):
        raise ValueError("Invalid provider artwork reference")
    return f"https://raw.githubusercontent.com/{repository}/{revision}/png/{slug}.png"


def configuration_revision() -> str:
    document = {identity: asdict(source) for identity, source in sources().items()}
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()

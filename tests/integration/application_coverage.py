import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app_faces.core import Resolver, desktop_entries, icon_path


def sample(entries: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    eligible = [e for e in entries if not e["nodisplay"]]
    return sorted(eligible, key=lambda e: hashlib.sha256(e["id"].encode()).hexdigest())[:count]


def measure(entry: dict[str, Any], resolver: Resolver) -> dict[str, Any]:
    executable = entry["executable"]
    result = resolver.resolve(executable, read_custom=False) if executable else None
    return {
        "name": entry["name"],
        "desktop_id": entry["id"],
        "declared_identity": True,
        "executable_association": result.status if result else "unsupported-wrapper",
        "method": result.method if result else "none",
        "exact_desktop_association": bool(
            result and result.method == "desktop" and result.application_id == entry["id"]
        ),
        "declared_artwork_available": bool(entry["icon"] and icon_path(entry["icon"])),
        "resolved_artwork_available": bool(result and result.icon and icon_path(result.icon)),
    }


def measure_portable(path: Path, resolver: Resolver, hash_file: bool = False) -> dict[str, Any]:
    row: dict[str, Any] = {"path": str(path), "name": path.name, "present": path.is_file()}
    if not row["present"]:
        return row
    result = resolver.resolve(path, read_custom=False, fingerprint=hash_file)
    row.update(
        status=result.status,
        method=result.method,
        artwork_available=bool(result.icon and icon_path(result.icon)),
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=24, choices=range(19, 30))
    parser.add_argument("--portable", type=Path, action="append", default=[])
    parser.add_argument("--fingerprint", action="store_true")
    args = parser.parse_args()
    resolver = Resolver()
    entries = list(desktop_entries())
    selected = sample(entries, args.count)
    rows = []
    for entry in selected:
        path = entry["executable"]
        if path and path.suffix.casefold() == ".appimage":
            assert any(e["executable"] == path.resolve() for e in resolver.entries)
        rows.append(measure(entry, resolver))
    portable = [measure_portable(path, resolver, args.fingerprint) for path in args.portable]
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "selection": f"{args.count} lowest SHA-256 desktop IDs, excluding NoDisplay; {len(portable)} explicitly selected portable files",
        "eligible_desktop_entries": sum(not e["nodisplay"] for e in entries),
        "sample_size": len(rows),
        "totals": {
            "exact_desktop_association": sum(r["exact_desktop_association"] for r in rows),
            "declared_artwork_available": sum(r["declared_artwork_available"] for r in rows),
            "resolved_artwork_available": sum(r["resolved_artwork_available"] for r in rows),
            "association_states": dict(Counter(r["executable_association"] for r in rows)),
        },
        "applications": rows,
        "portable": portable,
        "network_requests": 0,
        "programs_executed": 0,
        "icons_changed": 0,
        "limitations": [
            "Single-machine installed-app sample, not a universal success rate.",
            "Declared artwork availability is independent of executable identity resolution.",
            "NoDisplay apps excluded; wrapper-based launches retained as misses.",
            "Read-only integration benchmark, not UI E2E or proof of dock presentation.",
            "Portable files are explicitly selected inputs; missing files remain in the report.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"totals": report["totals"], "portable": portable}, indent=2))


if __name__ == "__main__":
    main()

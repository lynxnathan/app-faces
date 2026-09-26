import argparse
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--portable", type=Path, action="append", default=[])
args = parser.parse_args()
manifest = json.loads((ROOT / "build/portable-fixtures/manifest.json").read_text())
with tempfile.TemporaryDirectory(prefix="appfaces-portable-", dir=ROOT / "build") as temporary:
    os.environ["XDG_CACHE_HOME"] = temporary + "/cache"
    os.environ["XDG_DATA_HOME"] = temporary + "/data"
    from app_faces.automatic import confidence
    from app_faces.core import Resolver

    catalog = json.loads(
        (ROOT / "build/portable-fixtures/catalog-cache/app-faces/catalog.json").read_text()
    )
    resolver = Resolver(directories=[], catalog=catalog)
    rows = []
    for item in (
        manifest["fixtures"]
        + [{"name": p.stem, "executable": str(p)} for p in args.portable]
        + [
            {
                "name": "Misleading Telegram name (true bytes)",
                "executable": manifest["negative_controls"][0],
            },
        ]
    ):
        path = Path(item["executable"])
        result = resolver.resolve(path, read_custom=False)
        score = confidence(path, result)
        search = resolver.search("Telegram" if "Misleading" in item["name"] else item["name"])
        rows.append(
            {
                "name": item["name"],
                "path": str(path),
                "status": result.status,
                "method": result.method,
                "confidence": score,
                "automatic_eligible": score >= 0.90,
                "legacy_initial_ui_search": path.stem.split("-")[0],
                "legacy_initial_ui_search_matches": len(resolver.search(path.stem.split("-")[0])),
                "suggestions": [
                    {"name": c["name"], "slug": c.get("slug"), "provider": c.get("provider")}
                    for c in (result.candidates or [])
                ],
                "manual_search_matches": [
                    {"name": c["name"], "slug": c["slug"], "provider": c["provider"]}
                    for c in search
                ],
            }
        )
    report = {
        "source_revisions": catalog["sources"],
        "scope": "Fresh real provider catalog, no installed desktop association, loose ELF files; no execution/apply/upload",
        "applications": rows,
        "misleading_name_not_applied": not rows[-1]["automatic_eligible"],
    }
    (ROOT / "state/portable-coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

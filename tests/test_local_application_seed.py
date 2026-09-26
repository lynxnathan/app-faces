import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import seed_local_application


def test_seed_rejects_changed_build_without_mutation(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "path": "/example-app",
                "passed": True,
                "sha256": "old",
                "artwork_source": "https://example.org/icon.png",
            }
        )
    )
    monkeypatch.setattr(seed_local_application, "fingerprint", lambda _: "new")
    monkeypatch.setattr(
        seed_local_application, "publish", lambda _: pytest.fail("Unexpected mutation")
    )
    with pytest.raises(ValueError, match="Exact build"):
        seed_local_application.seed(evidence, Path("/icon"), "org.example.App", "Example")


def test_seed_preserves_existing_mapping(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    digest = "a" * 64
    evidence.write_text(
        json.dumps(
            {
                "path": "/example-app",
                "passed": True,
                "sha256": digest,
                "artwork_source": "https://example.org/icon.png",
            }
        )
    )
    monkeypatch.setattr(seed_local_application, "fingerprint", lambda _: digest)
    prior = {
        "version": 1,
        "icons": [],
        "fingerprints": {digest: {"id": "existing", "name": "Mine", "icon": "/mine.png"}},
    }
    monkeypatch.setattr(seed_local_application, "Resolver", lambda: SimpleNamespace(catalog=prior))
    monkeypatch.setattr(
        seed_local_application, "publish", lambda _: pytest.fail("Unexpected mutation")
    )
    with pytest.raises(ValueError, match="already exists"):
        seed_local_application.seed(evidence, Path("/icon"), "org.example.App", "Example")


@pytest.mark.parametrize("name", ["Example Editor", "Other Application"])
def test_seed_uses_requested_identity_and_can_roll_back(tmp_path, monkeypatch, name):
    from app_faces.catalog import rollback
    from app_faces.core import Resolver
    from app_faces.identity import fingerprint

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    target = tmp_path / "application"
    target.write_bytes(b"fixture executable; never launched")
    digest = fingerprint(target)
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "path": str(target),
                "passed": True,
                "sha256": digest,
                "artwork_source": "https://example.org/art",
            }
        )
    )
    icon = Path(__file__).parent / "fixtures/artwork/processor.svg"
    result = seed_local_application.seed(evidence, icon, "org.example.Custom", name)
    entry = Resolver().catalog["fingerprints"][digest]
    assert entry["id"] == "org.example.Custom"
    assert entry["name"] == name
    assert entry["provenance"]["source"] == "https://example.org/art"
    assert Path(entry["icon"]).is_file()
    assert result["status"] == "resolved"
    rollback(result["backup_revision"])
    assert digest not in Resolver().catalog.get("fingerprints", {})

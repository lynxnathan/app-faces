from pathlib import Path
from types import SimpleNamespace

from app_faces.core import Result
from tests.integration.application_coverage import measure, sample


def test_selection_is_order_independent_and_keeps_unresolved_launchers():
    entries = [
        {"id": f"app-{i}.desktop", "nodisplay": False, "executable": None} for i in range(30)
    ]
    entries.append({"id": "hidden.desktop", "nodisplay": True})
    assert sample(entries, 24) == sample(list(reversed(entries)), 24)
    assert len(sample(entries, 24)) == 24
    assert all(e["executable"] is None for e in sample(entries, 24))


def test_artwork_does_not_count_as_executable_identification(monkeypatch):
    monkeypatch.setattr(
        "tests.integration.application_coverage.icon_path", lambda _: Path("/icon.png")
    )
    entry = {"id": "app.desktop", "name": "App", "icon": "app", "executable": None}
    row = measure(entry, SimpleNamespace())
    assert row["declared_artwork_available"]
    assert not row["resolved_artwork_available"]
    assert not row["exact_desktop_association"]
    assert row["executable_association"] == "unsupported-wrapper"


def test_exact_identity_with_missing_theme_artwork_is_not_artwork_success(monkeypatch):
    monkeypatch.setattr("tests.integration.application_coverage.icon_path", lambda _: None)
    result = Result("resolved", "desktop", "App", "missing", "app.desktop")
    resolver = SimpleNamespace(resolve=lambda *a, **kw: result)
    entry = {"id": "app.desktop", "name": "App", "icon": "missing", "executable": Path("/app")}
    row = measure(entry, resolver)
    assert row["exact_desktop_association"]
    assert not row["declared_artwork_available"]
    assert not row["resolved_artwork_available"]


def test_portable_selection_preserves_misses_and_requires_explicit_hashing(tmp_path):
    from tests.integration.application_coverage import measure_portable

    calls = []

    def resolve(path, **kwargs):
        calls.append((path, kwargs))
        return Result("unknown", "none")

    resolver = SimpleNamespace(resolve=resolve)
    present = tmp_path / "Example"
    present.write_bytes(b"unrecognized")
    missing = tmp_path / "Missing"
    assert measure_portable(missing, resolver)["present"] is False
    assert not calls
    assert measure_portable(present, resolver)["status"] == "unknown"
    assert calls[-1] == (present, {"read_custom": False, "fingerprint": False})
    measure_portable(present, resolver, True)
    assert calls[-1][1]["fingerprint"] is True

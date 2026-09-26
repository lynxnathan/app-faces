import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("APP_FACES_GTK_TEST") != "1", reason="requires graphical GTK session"
)


def test_apply_is_local_even_when_sharing_validation_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, Gtk

    from app_faces import community, ui

    monkeypatch.setattr(ui.Chooser, "ensure_catalog", lambda _: False)
    monkeypatch.setattr(community, "endpoint", lambda: "https://example.com")
    app = Gtk.Application(
        application_id="io.github.appfaces.ComponentTest", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.register(None)
    applied = []
    monkeypatch.setattr(ui, "apply", lambda *a, **k: applied.append((a, k)))
    monkeypatch.setattr(
        community, "preview", lambda *a: (_ for _ in ()).throw(ValueError("invalid metadata"))
    )
    window = ui.Chooser(app, tmp_path / "Example")
    assert not window.share.get_active()
    window.source_entry.set_text("https://old-provider.example/art")
    window.license_entry.set_text("Old artwork license")
    window.pick_local(
        None, {"application_id": "org.example.App", "name": "Example"}, "/example.png"
    )
    assert window.source_entry.get_text() == ""
    assert window.license_entry.get_text() == "Unknown — review required"
    window.share.set_active(True)
    window.apply()
    assert applied == [((tmp_path / "Example", "/example.png"), {"replace": True})]
    assert "Icon applied" in window.status.get_text()
    assert "Sharing failed" in window.status.get_text()
    window.close()
    app.quit()


def test_contribution_empty_and_failed_states(monkeypatch: pytest.MonkeyPatch) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, Gtk

    from app_faces import community, ui

    app = Gtk.Application(
        application_id="io.github.appfaces.ReceiptTest", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.register(None)
    monkeypatch.setattr(community, "submissions", lambda: [])
    window = ui.Contributions(app)
    assert window.listing.get_row_at_index(0) is None
    monkeypatch.setattr(
        community,
        "submissions",
        lambda: [dict(id="a" * 64, name="Example", status="failed", reason="HTTP 422", sent=False)],
    )
    window.render()
    row = window.listing.get_row_at_index(0).get_child()
    actions = row.get_last_child()
    assert actions.get_first_child().get_label() == "Retry upload"
    assert actions.get_last_child().get_label() == "Cancel upload"
    window.close()
    app.quit()


@pytest.mark.parametrize("locale", ["en", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur"])
def test_native_locale_and_direction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, locale: str
) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, Gtk

    from app_faces import i18n, ui

    monkeypatch.setenv("APP_FACES_LANGUAGE", locale)
    monkeypatch.setattr(ui.Chooser, "ensure_catalog", lambda _: False)
    app = Gtk.Application(
        application_id="io.github.appfaces.LocaleTest." + locale,
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    app.register(None)
    path = tmp_path / "My العربية বাংলা App"
    path.write_bytes(b"test")
    window = ui.Chooser(app, path)
    try:
        assert window.apply_button.get_label() == i18n.catalog(locale)["Apply icon"]
        assert window.name_entry.get_text() == path.name
        assert not window.share.get_active()
        assert window.get_direction() == (
            Gtk.TextDirection.RTL if locale in i18n.RTL_LANGUAGES else Gtk.TextDirection.LTR
        )
        assert not window.apply_button.get_sensitive()
    finally:
        window.destroy()

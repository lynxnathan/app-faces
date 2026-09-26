import ast
import json
import re
from pathlib import Path

import pytest

from app_faces import i18n


def test_catalogs_have_matching_messages_and_parameters() -> None:
    english = i18n.catalog("en")
    for locale in i18n.LANGUAGES:
        messages = i18n.catalog(locale)
        assert messages.keys() == english.keys(), locale
        for key, value in messages.items():
            assert value.strip(), (locale, key)
            assert sorted(re.findall(r"\{\w+\}", key)) == sorted(re.findall(r"\{\w+\}", value)), (
                locale,
                key,
            )


def test_python_interface_messages_are_in_catalog() -> None:
    root = Path(__file__).resolve().parents[1] / "app_faces"
    for file in root.glob("*.py"):
        for node in ast.walk(ast.parse(file.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "t"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                assert node.args[0].value in i18n.catalog("en"), (file.name, node.lineno)


@pytest.mark.parametrize("locale", i18n.LANGUAGES)
def test_localized_parameters_preserve_user_content(
    monkeypatch: pytest.MonkeyPatch, locale: str
) -> None:
    monkeypatch.setenv("APP_FACES_LANGUAGE", locale)
    name = '<script>{name} & تطبيق বাংলা "App"'
    translated = i18n.t("Share {name}", name=name)
    assert name in translated
    assert translated == i18n.catalog(locale)["Share {name}"].replace("{name}", name)
    assert i18n.t("unregistered diagnostic") == "unregistered diagnostic"


def test_language_precedence_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_FACES_LANGUAGE", raising=False)
    monkeypatch.setenv("LANGUAGE", "xx:fr_CA:ar")
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    assert i18n.language() == "fr"
    monkeypatch.setenv("APP_FACES_LANGUAGE", "zh_Hant_TW.UTF-8")
    assert i18n.language() == "zh"
    monkeypatch.setenv("APP_FACES_LANGUAGE", "../../unexpected")
    assert i18n.language() == "en"
    assert i18n.negotiate(["C.UTF-8", "fr"]) == "en"
    assert i18n.negotiate(["xx", "pt-BR"]) == "pt"


def test_catalog_files_are_independent_json_objects() -> None:
    root = Path(__file__).resolve().parents[1] / "app_faces/locales"
    for file in root.glob("*.json"):
        pairs = json.loads(file.read_text(), object_pairs_hook=list)
        assert len(pairs) == len(dict(pairs)), file.name


@pytest.mark.parametrize("locale", i18n.LANGUAGES)
def test_desktop_protocol_values_are_locale_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, locale: str
) -> None:
    from app_faces.core import desktop_entries
    from app_faces.state import apply_marker, plan_marker

    monkeypatch.setenv("APP_FACES_LANGUAGE", locale)
    entry = tmp_path / "example.desktop"
    entry.write_text(
        "[Desktop Entry]\nType=Application\nName=Example\nExec=/bin/true\nIcon=example\n"
    )
    assert len(list(desktop_entries([tmp_path]))) == 1
    missing = tmp_path / "missing"
    assert plan_marker(missing, {}, None)["status"] == "unavailable"
    record = {"refresh_marker": {"status": "planned"}}
    apply_marker(missing, record)
    assert record["refresh_marker"]["status"] == "unavailable"

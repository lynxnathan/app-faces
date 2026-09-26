import json
import os
from functools import cache
from importlib.resources import files

LANGUAGES = ("en", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur")
RTL_LANGUAGES = frozenset({"ar", "ur"})


def negotiate(preferences: list[str]) -> str:
    for preference in preferences:
        language = preference.split(".", 1)[0].split("@", 1)[0].replace("_", "-").lower()
        language = language.split("-", 1)[0]
        if language in LANGUAGES:
            return language
        if language in {"c", "posix"}:
            return "en"
    return "en"


def language() -> str:
    override = os.environ.get("APP_FACES_LANGUAGE")
    if override:
        return negotiate([override])
    preferences = os.environ.get("LANGUAGE", "").split(":")
    preferences.append(
        os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG", "en")
    )
    return negotiate(preferences)


@cache
def catalog(locale: str) -> dict[str, str]:
    data = json.loads(files("app_faces").joinpath("locales", locale + ".json").read_text())
    if not isinstance(data, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in data.items()
    ):
        raise ValueError("Invalid translation catalog")
    return data


def t(message: str, **values: object) -> str:
    translated = catalog(language()).get(message, message)
    return translated.format_map(values) if values else translated

from __future__ import annotations

from bot.i18n import normalize, t


def test_normalize_supported() -> None:
    assert normalize("ru") == "ru"
    assert normalize("en") == "en"


def test_normalize_handles_locale_variants() -> None:
    assert normalize("en-US") == "en"
    assert normalize("ru-RU") == "ru"


def test_normalize_unknown_falls_back_to_default() -> None:
    assert normalize(None) == "ru"
    assert normalize("") == "ru"
    assert normalize("de") == "ru"


def test_translation_returns_target_locale() -> None:
    assert t("menu.catalog", lang="ru").startswith("🎁")
    assert "Catalog" in t("menu.catalog", lang="en")


def test_missing_key_returns_key_back() -> None:
    assert t("definitely.missing", lang="ru") == "definitely.missing"


def test_format_arguments() -> None:
    msg = t("product.stock", lang="ru", n=7)
    assert "7" in msg

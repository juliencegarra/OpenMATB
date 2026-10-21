"""Tests of the translations: locales/*/LC_MESSAGES (gettext) and the start page of the web version."""

from __future__ import annotations

import gettext
import re
import sys
from pathlib import Path

import pytest

from core import bidi

ROOT: Path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "locales"))
import build  # noqa: E402

PO_FILES: list[Path] = build.po_files()
LANGUAGES: list[str] = [path.parents[1].name for path in PO_FILES]
SOURCE_LANGUAGE: str = "en_EN"  # The messages are written in English
POT_MESSAGES: list[str] = list(build.read_po(build.POT)[1])


def test_languages():
    assert {"en_EN", "fr_FR", "de_DE", "es_ES", "it_IT", "zh_CN", "ja_JP", "ar_SA"} <= set(LANGUAGES)


def test_pot_is_up_to_date():
    """locales/openmatb.pot has all the messages of the code: run python locales/build.py pot after a change."""
    assert set(POT_MESSAGES) == set(build.extract())


def test_dynamic_messages_are_translated_through_a_variable():
    """The messages added by hand to the .pot are not found in the code as _("...") (otherwise remove them)."""
    listed = build.extract
    code_messages = {m for m, locations in listed().items() if locations != [build.DYNAMIC_MESSAGES.get(m)]}
    assert not code_messages & set(build.DYNAMIC_MESSAGES)


@pytest.fixture(params=PO_FILES, ids=LANGUAGES)
def catalog(request) -> tuple[str, dict[str, str], dict[str, str]]:
    path: Path = request.param
    header, translations = build.read_po(path)
    return path.parents[1].name, header, translations


class TestCatalogs:
    def test_mo_is_compiled_from_po(self, catalog):
        """The .mo has exactly the translations of the .po: run python locales/build.py mo after a change."""
        language, _, translations = catalog
        loaded = gettext.translation("openmatb", ROOT / "locales", [language])
        compiled = {k: v for k, v in loaded._catalog.items() if k}
        assert compiled == {k: v for k, v in translations.items() if v}

    def test_utf8(self, catalog):
        _, header, _ = catalog
        assert "charset=UTF-8" in header.get("Content-Type", "")

    def test_language_header(self, catalog):
        language, header, _ = catalog
        if language not in ("en_EN", "fr_FR"):  # Older files, written by Poedit
            assert header.get("Language") == language
            assert header.get("Plural-Forms", "").startswith("nplurals=")

    def test_complete(self, catalog):
        """Every message of the code is translated (en_EN too: its translations are the messages themselves)."""
        _, _, translations = catalog
        missing = [m for m in POT_MESSAGES if not translations.get(m)]
        assert not missing

    def test_no_obsolete_message(self, catalog):
        """Messages removed from the code are removed from the catalogs (python locales/build.py update)."""
        _, _, translations = catalog
        assert [m for m in translations if m not in POT_MESSAGES] == []

    def test_source_language_is_identity(self, catalog):
        language, _, translations = catalog
        if language == SOURCE_LANGUAGE:
            assert {m: t for m, t in translations.items() if t != m} == {}

    def test_placeholders_are_kept(self, catalog):
        """%s, {error}, tabs (columns) and the spaces at both ends (messages are concatenated) are kept."""
        _, _, translations = catalog
        for msgid, msgstr in translations.items():
            if not msgstr:
                continue
            assert msgstr.count("%s") == msgid.count("%s"), msgid
            assert re.findall(r"%[^s]", msgstr.replace("%%", "")) == re.findall(r"%[^s]", msgid.replace("%%", ""))
            assert sorted(re.findall(r"\{\w+\}", msgstr)) == sorted(re.findall(r"\{\w+\}", msgid)), msgid
            assert msgstr.count("\t") == msgid.count("\t"), msgid
            assert msgstr.startswith(" ") == msgid.startswith(" "), msgid
            assert msgstr.endswith(" ") == msgid.endswith(" "), msgid

    def test_messages_can_be_formatted(self, catalog):
        _, _, translations = catalog
        for msgid, msgstr in translations.items():
            if msgstr and "%s" in msgid:
                msgstr % tuple("x" * msgid.count("%s"))
            if msgstr and "{error}" in msgid:
                msgstr.format(error="x")

    def test_loaded_by_main(self, catalog):
        """main.py loads the language of config.ini with gettext.translation (fallback=True would hide an error)."""
        language, _, _ = catalog
        translation = gettext.translation("openmatb", ROOT / "locales", [language])
        assert translation.gettext("Continue")


# ──────────────────────────────────────────────
# Start page of the web version (web/index.html, web/openmatb.js)
# ──────────────────────────────────────────────

INDEX: str = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
SCRIPT: str = (ROOT / "web" / "openmatb.js").read_text(encoding="utf-8")


def _web_texts() -> dict[str, dict[str, str]]:
    """The TEXTS of web/openmatb.js: {language: {key: text}} (string concatenations joined)."""
    block: str = SCRIPT[SCRIPT.index("const TEXTS = {") : SCRIPT.index("\n};", SCRIPT.index("const TEXTS = {"))]
    texts: dict[str, dict[str, str]] = {}
    for language, body in re.findall(r"\n    (\w+): \{(.*?)\n    \},", block, re.S):
        texts[language] = {}
        for key, value in re.findall(r"\n        (\w+): ((?:\"(?:[^\"\\]|\\.)*\"\s*\+?\s*)+),", body):
            texts[language][key] = "".join(re.findall(r"\"((?:[^\"\\]|\\.)*)\"", value))
    return texts


WEB_TEXTS: dict[str, dict[str, str]] = _web_texts()


class TestWebStartPage:
    def test_menu_has_every_language(self):
        options: list[str] = re.findall(r'<option value="(\w\w_\w\w)">', INDEX)
        assert sorted(options) == sorted(LANGUAGES)

    def test_texts_of_every_language(self):
        assert sorted(WEB_TEXTS) == sorted(LANGUAGES)

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_texts_complete(self, language):
        assert set(WEB_TEXTS[language]) == set(WEB_TEXTS["en_EN"])
        assert all(WEB_TEXTS[language].values())

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_texts_placeholders(self, language):
        for key, text in WEB_TEXTS["en_EN"].items():
            assert sorted(re.findall(r"\{\w+\}", WEB_TEXTS[language][key])) == sorted(re.findall(r"\{\w+\}", text))

    def test_rtl_languages_as_in_core_bidi(self):
        listed: str = re.search(r"const RTL_LANGUAGES = \[(.*?)\];", SCRIPT).group(1)
        assert tuple(re.findall(r"\"(\w+)\"", listed)) == bidi.RTL_LANGUAGES

    def test_rtl_web_fonts_are_built(self):
        """The Arabic and Hebrew fonts loaded by the page are downloaded by web/build.py."""
        build_script: str = (ROOT / "web" / "build.py").read_text(encoding="utf-8")
        for name in re.findall(r'"(noto-sans[\w-]*)": ', SCRIPT):
            assert f'    "{name}": "' in build_script, name

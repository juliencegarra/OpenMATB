"""Tests of the translations: locales/*/LC_MESSAGES (gettext) and the start page of the web version."""

from __future__ import annotations

import gettext
import importlib.util
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

# The languages kept complete: every message is translated (test_complete). A new language (e.g. started in Weblate)
# is only checked for consistency (placeholders, compiled .mo...), its untranslated messages are shown in English:
# add it here once it is complete
COMPLETE_LANGUAGES: tuple[str, ...] = (
    "en_EN", "fr_FR", "de_DE", "es_ES", "es_AR", "it_IT", "pt_BR", "zh_CN", "ja_JP", "ar_SA"
)


def test_languages():
    assert set(COMPLETE_LANGUAGES) <= set(LANGUAGES)


def test_pot_is_up_to_date():
    """locales/openmatb.pot has all the messages of the code: run python locales/build.py pot after a change."""
    assert set(POT_MESSAGES) == set(build.extract())


def test_update_keeps_the_fuzzy_translations(tmp_path):
    """A translation to review (fuzzy, e.g. "Needs editing" in Weblate) is kept by update, and not compiled. The
    wrapped lines, the previous message (#|) and the obsolete entries (#~) written by Weblate are read."""
    po: Path = tmp_path / "openmatb.po"
    po.write_text(
        'msgid ""\nmsgstr ""\n"Language: de_DE\\n"\n\n'
        '#, fuzzy\n#| msgid "Warn"\nmsgid "Warning"\nmsgstr ""\n"Warn"\n"ung?"\n\n'
        'msgid "Continue"\nmsgstr "Weiter"\n\n#~ msgid "Old message"\n#~ msgstr "Alte Nachricht"\n',
        encoding="utf-8",
    )
    header, translations = build.read_po(po)
    assert header == {"Language": "de_DE"}
    assert translations == {"Continue": "Weiter"}
    assert build.read_fuzzy(po) == {"Warning": "Warnung?"}

    build.write_po(po, header, {"Warning": ["a.py:1"], "Continue": ["a.py:2"]}, translations, build.read_fuzzy(po))
    assert '#, fuzzy\nmsgid "Warning"\nmsgstr "Warnung?"' in po.read_text(encoding="utf-8")
    assert build.read_fuzzy(po) == {"Warning": "Warnung?"}
    assert build.read_po(po)[1] == {"Continue": "Weiter"}


def test_format_flags(tmp_path):
    """The messages with placeholders are flagged as xgettext does, so that Weblate checks the translations, and the
    flags are written with fuzzy."""
    assert build.flags("Session ID: %s") == ["python-format"]
    assert build.flags("Parallel port error: {error}") == ["python-brace-format"]
    assert build.flags("Continue") == []
    assert build.flags("100%% done") == []
    assert build.flags("(R,G,B,a) values") == []

    po: Path = tmp_path / "openmatb.po"
    build.write_po(po, {}, {"%s was not found": ["a.py:1"]}, {}, {"%s was not found": "%s introuvable"})
    assert '#, fuzzy, python-format\nmsgid "%s was not found"' in po.read_text(encoding="utf-8")
    assert build.read_fuzzy(po) == {"%s was not found": "%s introuvable"}


def test_placeholders_are_named_when_several():
    """A message with several placeholders names them, %(line)s, so that a translation can change their order."""
    for message in POT_MESSAGES:
        assert message.replace("%%", "").count("%s") <= 1, message


def test_pot_flags_the_placeholders():
    """Every message of the .pot with a placeholder is flagged (python locales/build.py pot after a change)."""
    text: str = build.POT.read_text(encoding="utf-8")
    for message in POT_MESSAGES:
        if build.flags(message):
            assert f"#, {', '.join(build.flags(message))}\nmsgid {build._quote(message)}" in text, message


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
        """Every message is translated in the complete languages (en_EN too: its translations are the messages
        themselves)."""
        language, _, translations = catalog
        if language not in COMPLETE_LANGUAGES:
            pytest.skip(f"{language} is being translated (not in COMPLETE_LANGUAGES)")
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
            assert sorted(re.findall(r"%\(\w+\)s", msgstr)) == sorted(re.findall(r"%\(\w+\)s", msgid)), msgid
            assert re.findall(r"%[^s(]", msgstr.replace("%%", "")) == re.findall(r"%[^s(]", msgid.replace("%%", ""))
            assert sorted(re.findall(r"\{\w+\}", msgstr)) == sorted(re.findall(r"\{\w+\}", msgid)), msgid
            assert msgstr.count("\t") == msgid.count("\t"), msgid
            assert msgstr.startswith(" ") == msgid.startswith(" "), msgid
            assert msgstr.endswith(" ") == msgid.endswith(" "), msgid

    def test_messages_can_be_formatted(self, catalog):
        _, _, translations = catalog
        for msgid, msgstr in translations.items():
            names: list[str] = re.findall(r"%\((\w+)\)s", msgid)
            if msgstr and names:
                msgstr % dict.fromkeys(names, "x")
            elif msgstr and "%s" in msgid:
                msgstr % tuple("x" * msgid.count("%s"))
            if msgstr and "{error}" in msgid:
                msgstr.format(error="x")

    def test_loaded_by_main(self, catalog):
        """main.py loads the language of config.ini with gettext.translation (fallback=True would hide an error)."""
        language, _, _ = catalog
        translation = gettext.translation("openmatb", ROOT / "locales", [language])
        assert translation.gettext("Continue")


# ──────────────────────────────────────────────
# Start page of the web version (web/index.html, web/openmatb.js, web/texts.json)
# ──────────────────────────────────────────────

INDEX: str = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
SCRIPT: str = (ROOT / "web" / "openmatb.js").read_text(encoding="utf-8")


def _web_build():
    spec = importlib.util.spec_from_file_location("_web_build_texts", ROOT / "web" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The texts of the start page in each language, as web/build.py writes them (texts.js): {language: {key: text}}
WEB_TEXTS: dict[str, dict[str, str]] = _web_build().start_page_texts()
ENGLISH: dict[str, str] = build.web_texts()


class TestWebStartPage:
    def test_every_language_is_offered(self):
        """The menu of the page is made of the languages of locales/, English first."""
        assert list(WEB_TEXTS)[0] == "en_EN"
        assert sorted(WEB_TEXTS) == sorted(LANGUAGES)
        assert '<select id="lang"></select>' in INDEX

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_texts_of_each_language(self, language):
        """Every text is there, translated or (language being translated) in English."""
        assert list(WEB_TEXTS[language]) == list(ENGLISH)
        assert all(WEB_TEXTS[language].values())

    @pytest.mark.parametrize("language", [language for language in LANGUAGES if language in COMPLETE_LANGUAGES])
    def test_texts_translated(self, language):
        """In a complete language, every text of the page comes from the catalog."""
        translations: dict[str, str] = build.read_po(build.LOCALES / language / "LC_MESSAGES" / "openmatb.po")[1]
        assert [text for text in ENGLISH.values() if not translations.get(text)] == []

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_texts_placeholders(self, language):
        for key, text in ENGLISH.items():
            assert sorted(re.findall(r"\{\w+\}", WEB_TEXTS[language][key])) == sorted(re.findall(r"\{\w+\}", text))

    def test_keys_used_by_the_page_exist(self):
        """The keys of the page (data-i18n of index.html, t("...") and status("...") of openmatb.js) are in
        web/texts.json."""
        used: set[str] = set(re.findall(r'data-i18n(?:-title)?="(\w+)"', INDEX))
        used |= set(re.findall(r'\b(?:t|status)\("(\w+)"', SCRIPT))
        assert used
        assert used <= set(ENGLISH), used - set(ENGLISH)

    def test_rtl_languages_as_in_core_bidi(self):
        listed: str = re.search(r"const RTL_LANGUAGES = \[(.*?)\];", SCRIPT).group(1)
        assert tuple(re.findall(r"\"(\w+)\"", listed)) == bidi.RTL_LANGUAGES

    def test_default_variants_exist(self):
        """The default variants used by the language detection of the page are languages of locales/."""
        listed: str = re.search(r"const DEFAULT_VARIANTS = \[(.*?)\];", SCRIPT).group(1)
        variants: list[str] = re.findall(r"\"(\w+)\"", listed)
        assert variants
        assert set(variants) <= set(LANGUAGES)

    def test_rtl_web_fonts_are_built(self):
        """The Arabic and Hebrew fonts loaded by the page are downloaded by web/build.py."""
        build_script: str = (ROOT / "web" / "build.py").read_text(encoding="utf-8")
        for name in re.findall(r'"(noto-sans[\w-]*)": ', SCRIPT):
            assert f'    "{name}": "' in build_script, name

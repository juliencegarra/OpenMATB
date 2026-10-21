"""Tests for core.bidi: Arabic shaping and bidirectional reordering of right-to-left text."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

from core import bidi

ROOT: Path = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def ltr_language():
    bidi.set_language("en_EN")
    yield
    bidi.set_language("en_EN")


def names(text: str) -> list[str]:
    return [unicodedata.name(c, hex(ord(c))) for c in text]


def shaped(text: str) -> str:
    return bidi.shape(text)[0]


# ──────────────────────────────────────────────
# Detection
# ──────────────────────────────────────────────


class TestDetection:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("", False),
            ("OpenMATB", False),
            ("Surveillance système ÄÖÜ", False),
            ("系统监控 システム監視", False),
            ("مراقبة النظام", True),
            ("שלום", True),
            ("Esc: خروج", True),
            ("ﻻ", True),  # Presentation form
            ("١٢٣", False),  # Arabic-Indic digits are numbers, not letters
        ],
    )
    def test_has_rtl(self, text, expected):
        assert bidi.has_rtl(text) is expected

    @pytest.mark.parametrize("iso", ["ar_SA", "ar", "he_IL", "fa_IR", "ur_PK", "ar-EG", "AR_SA"])
    def test_rtl_languages(self, iso):
        assert bidi.is_rtl_language(iso)

    @pytest.mark.parametrize("iso", ["en_EN", "fr_FR", "zh_CN", "ja_JP", "de_DE", "es_ES", "it_IT", ""])
    def test_ltr_languages(self, iso):
        assert not bidi.is_rtl_language(iso)


# ──────────────────────────────────────────────
# Arabic shaping
# ──────────────────────────────────────────────


class TestShaping:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("ب", "ﺏ"),  # Isolated
            ("بب", "ﺑﺐ"),  # Initial, final
            ("ببب", "ﺑﺒﺐ"),  # Initial, medial, final
            ("بد", "ﺑﺪ"),  # Dal joins the letter before it...
            ("دب", "ﺩﺏ"),  # ... but not the one after it
            ("بدب", "ﺑﺪﺏ"),
            ("ءب", "ﺀﺏ"),  # Hamza joins nothing
            ("بء", "ﺏﺀ"),
            ("ة", "ﺓ"),
            ("بة", "ﺑﺔ"),
        ],
    )
    def test_contextual_forms(self, text, expected):
        assert shaped(text) == expected, names(shaped(text))

    @pytest.mark.parametrize(
        "alef,isolated",
        [("آ", "ﻵ"), ("أ", "ﻷ"), ("إ", "ﻹ"), ("ا", "ﻻ")],
    )
    def test_lam_alef_ligatures(self, alef, isolated):
        assert shaped("ل" + alef) == isolated
        final: str = chr(ord(isolated) + 1)
        assert shaped("م" + "ل" + alef) == "ﻣ" + final  # Meem initial, then the final ligature

    def test_lam_alef_in_words(self):
        assert names(shaped("سلام")) == [
            "ARABIC LETTER SEEN INITIAL FORM",
            "ARABIC LIGATURE LAM WITH ALEF FINAL FORM",
            "ARABIC LETTER MEEM ISOLATED FORM",
        ]
        # After the ligature, a letter starts again (alef does not join the next letter)
        assert names(shaped("ملاحظة"))[2] == "ARABIC LETTER HAH INITIAL FORM"

    def test_only_lam_alef_ligatures(self):
        """Other ligatures of the presentation forms (lam + meem...) are optional: letters stay separate."""
        assert names(shaped("لم")) == ["ARABIC LETTER LAM INITIAL FORM", "ARABIC LETTER MEEM FINAL FORM"]
        assert names(shaped("المتبقي"))[2:4] == ["ARABIC LETTER MEEM MEDIAL FORM", "ARABIC LETTER TEH MEDIAL FORM"]

    def test_lam_alef_sources(self):
        text, sources = bidi.shape("سلام")
        assert len(text) == 3
        assert sources == [0, 1, 3]  # The ligature comes from the lam, the alef is dropped

    def test_marks_are_transparent(self):
        """A mark (fatha) between two letters does not break their joining, and stays after its letter."""
        assert shaped("بَب") == "ﺑَﺐ"

    def test_marks_inside_lam_alef(self):
        text, sources = bidi.shape("لَا")
        assert text == "ﻻَ"
        assert sources == [0, 1]

    def test_tatweel_joins(self):
        assert shaped("بـ") == "ﺑـ"
        assert shaped("ـب") == "ـﺐ"

    def test_zero_width_non_joiner_breaks_joining(self):
        assert shaped("ب‌ب") == "ﺏ‌ﺏ"

    def test_zero_width_joiner_joins(self):
        assert shaped("ب‍") == "ﺑ‍"

    @pytest.mark.parametrize(
        "letter,initial,final",
        [
            ("پ", "ﭘ", "ﭗ"),  # Peh (Persian, Urdu)
            ("چ", "ﭼ", "ﭻ"),  # Tcheh
            ("گ", "ﮔ", "ﮓ"),  # Gaf
            ("ک", "ﮐ", "ﮏ"),  # Keheh
            ("ی", "ﯾ", "ﯽ"),  # Farsi yeh
        ],
    )
    def test_persian_letters(self, letter, initial, final):
        assert shaped(letter + letter) == initial + final

    def test_letters_between_other_characters(self):
        """Spaces, digits and Latin letters do not join."""
        assert shaped("ب ب") == "ﺏ ﺏ"
        assert shaped("ب1ب") == "ﺏ1ﺏ"
        assert shaped("بxب") == "ﺏxﺏ"

    @pytest.mark.parametrize("text", ["", "OpenMATB", "Élément 12", "系统监控", "שלום", "١٢٣"])
    def test_other_scripts_unchanged(self, text):
        assert bidi.shape(text) == (text, list(range(len(text))))

    def test_every_arabic_letter_has_forms(self):
        """All the letters of the Arabic alphabet, and of Persian and Urdu, have presentation forms."""
        letters = "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىيپچژکگی"
        missing = [c for c in letters if c not in bidi.FORMS]
        assert not missing, names("".join(missing))

    def test_no_arabic_letter_is_left_unshaped(self):
        text: str = "ستقوم بأربع مهام في الوقت نفسه: المراقبة، والتتبع، والاتصالات، وإدارة الموارد."
        assert not [c for c in shaped(text) if c in bidi.FORMS]


# ──────────────────────────────────────────────
# Bidirectional reordering
# ──────────────────────────────────────────────


def visual(line: str, rtl: bool | None = None) -> str:
    return bidi.visual_line(line, rtl)[0]


class TestParagraphDirection:
    def test_first_strong_letter(self):
        assert bidi.is_rtl_paragraph("שלום abc")
        assert not bidi.is_rtl_paragraph("abc שלום")
        assert bidi.is_rtl_paragraph("12 שלום")  # Numbers are not strong
        assert not bidi.is_rtl_paragraph("12 + 3")

    def test_rtl_language_makes_mixed_paragraphs_rtl(self):
        assert not bidi.is_rtl_paragraph("Esc: خروج")
        bidi.set_language("ar_SA")
        assert bidi.is_rtl_paragraph("Esc: خروج")
        assert not bidi.is_rtl_paragraph("OpenMATB")  # Only left-to-right letters: stays left-to-right


class TestReordering:
    def test_hebrew_is_reversed(self):
        assert visual("שלום") == "םולש"

    def test_words_are_in_reverse_order(self):
        assert visual("אב גד") == "דג בא"

    @pytest.mark.parametrize("number", ["12", "12:30", "1,000", "3.14", "0:12:30", "2026"])
    def test_numbers_keep_their_order(self, number):
        assert visual(f"אב {number}") == f"{number} בא"
        assert visual(f"{number} אב") == f"בא {number}"

    def test_numbers_after_arabic_letters(self):
        """After an Arabic letter, digits are Arabic numbers: they keep their order too."""
        assert bidi.visual("ب 12:30") == "12:30 ﺏ"

    def test_percent_after_an_arabic_number(self):
        """As in browsers (UAX #9): in Arabic text, % is drawn on the left of the number."""
        assert bidi.visual("ب 50%") == "%50 ﺏ"

    def test_latin_words_keep_their_order(self):
        assert visual("אב OpenMATB גד") == "דג OpenMATB בא"
        assert visual("אב abc def גד") == "דג abc def בא"
        assert visual("אב config.ini גד") == "דג config.ini בא"

    def test_brackets_are_mirrored_in_rtl_runs(self):
        assert visual("אב (גד)") == "(דג) בא"
        assert visual("אב [ג] {ד} <ה> «ו»") == "«ו» <ה> {ד} [ג] בא"

    def test_brackets_around_latin_text(self):
        assert visual("אב (Space) גד") == "דג (Space) בא"

    def test_bracket_pairs_after_latin_text(self):
        """Rule N0: brackets after a left-to-right word, around left-to-right text, are both left-to-right."""
        assert visual("אב pyparallel (pip install) גד") == "דג pyparallel (pip install) בא"
        assert visual("אב (pip) cd") == "cd (pip) בא"

    def test_bracket_pairs_around_mixed_text(self):
        """Brackets around right-to-left text in a right-to-left paragraph are mirrored, both of them."""
        assert visual("אב (abc גד) ה") == "ה (דג abc) בא"

    def test_ltr_paragraph_with_an_rtl_word(self):
        assert visual("abc אב def") == "abc בא def"
        assert visual("abc (אב) def") == "abc (בא) def"

    def test_final_punctuation_goes_left(self):
        assert visual("שלום.") == ".םולש"
        assert visual("שלום?") == "?םולש"

    def test_rtl_paragraph_starting_with_latin(self):
        assert visual("Esc: שלום", rtl=True) == "םולש :Esc"
        assert visual("Esc: שלום", rtl=False) == "Esc: םולש"

    def test_tab_stays_between_its_columns(self):
        """Rule L1: a tab is at the paragraph level, so columns stay in order from the right."""
        assert visual("אב\t12") == "12\tבא"
        assert visual("זמן \t 0:12:30", rtl=True) == "0:12:30 \t ןמז"

    def test_trailing_spaces_stay_at_the_end(self):
        assert visual("אב  ") == "  בא"

    def test_marks_stay_after_their_letter(self):
        """Rule L3: a mark is drawn after its letter, not before."""
        line = "אְב"  # Alef, sheva, bet
        assert visual(line) == "באְ"

    def test_reorder_is_a_permutation(self):
        line = "אב (abc) 12:30, גד «def» \t ה."
        order = bidi.reorder(line)
        assert sorted(order) == list(range(len(line)))

    def test_levels(self):
        assert bidi.levels("אב 12 abc") == [1, 1, 1, 2, 2, 1, 2, 2, 2]
        assert bidi.levels("abc אב") == [0, 0, 0, 0, 1, 1]

    @pytest.mark.parametrize("text", ["", "abc def", "12:30", "系统监控", "Élément (1)"])
    def test_ltr_text_unchanged(self, text):
        assert bidi.visual_line(text) == (text, list(range(len(text))))
        assert bidi.visual(text) == text


class TestVisual:
    def test_each_line_is_reordered(self):
        assert bidi.visual("אב\nגד") == "בא\nדג"
        assert bidi.visual("אב\u2028abc\u2029גד") == "בא\u2028abc\u2029דג"

    def test_arabic_is_shaped_then_reordered(self):
        assert bidi.visual("سلام") == shaped("سلام")[::-1]

    def test_rtl_language_sentence(self):
        bidi.set_language("ar_SA")
        assert bidi.visual("Esc: خروج") == shaped("خروج")[::-1] + " :Esc"


# ──────────────────────────────────────────────
# The translations of the right-to-left languages
# ──────────────────────────────────────────────


def _rtl_translations() -> list[tuple[str, str, str]]:
    import sys

    sys.path.insert(0, str(ROOT / "locales"))
    import build

    cases: list[tuple[str, str, str]] = []
    for path in build.po_files():
        language: str = path.parents[1].name
        if bidi.is_rtl_language(language):
            _, translations = build.read_po(path)
            cases += [(language, msgid, msgstr) for msgid, msgstr in translations.items() if msgstr]
    return cases


RTL_TRANSLATIONS: list[tuple[str, str, str]] = _rtl_translations()
LATIN_TOKEN: re.Pattern[str] = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:[.=][A-Za-z0-9_]+)*")


def test_there_is_a_rtl_language():
    assert {language for language, _, _ in RTL_TRANSLATIONS} >= {"ar_SA"}


@pytest.mark.parametrize("language,msgid,msgstr", RTL_TRANSLATIONS, ids=[m[:40] for _, m, _ in RTL_TRANSLATIONS])
class TestRtlTranslations:
    @staticmethod
    def filled(msgstr: str) -> str:
        return msgstr.replace("%s", "12").replace("{error}", "Errno 13")

    def test_displayed_text_is_complete(self, language, msgid, msgstr):
        """Every character of the shaped message is drawn once (brackets may be mirrored)."""
        bidi.set_language(language)
        text: str = self.filled(msgstr)
        same_bracket = lambda s: sorted(min(c, bidi._MIRRORS.get(c, c)) for c in s)  # noqa: E731
        assert same_bracket(bidi.visual(text)) == same_bracket(shaped(text))

    def test_brackets_face_each_other(self, language, msgid, msgstr):
        """Each displayed bracket pair opens on the left: "(...)", never ")...(" or "(...(" (rule N0)."""
        bidi.set_language(language)
        displayed: str = bidi.visual(self.filled(msgstr))
        depth: int = 0
        for c in displayed:
            depth += {"(": 1, ")": -1}.get(c, 0)
            assert depth >= 0, displayed
        assert depth == 0, displayed

    def test_every_letter_is_shaped(self, language, msgid, msgstr):
        bidi.set_language(language)
        assert not [c for c in bidi.visual(self.filled(msgstr)) if c in bidi.FORMS]

    def test_latin_words_are_kept(self, language, msgid, msgstr):
        """Names (config.ini, OpenMATB, web_serial_trigger=True...) are still readable from left to right."""
        bidi.set_language(language)
        text: str = self.filled(msgstr)
        displayed: str = bidi.visual(text)
        for token in LATIN_TOKEN.findall(text):
            assert token in displayed, (token, displayed)


# ──────────────────────────────────────────────
# Conformance with the Unicode reference (UAX #9)
# ──────────────────────────────────────────────

FIXTURES: Path = ROOT / "tests" / "fixtures"


def _levels(field: str) -> list[int | None]:
    """Levels of a conformance test: x for the characters removed by rule X9 (embeddings, BN)."""
    return [None if x == "x" else int(x) for x in field.split()]


def _character_cases() -> list[tuple[str, bool | None, list[int | None], list[int]]]:
    """Tests of the Unicode BidiCharacterTest.txt (sample in tests/fixtures): line, paragraph direction (None: from
    its first letter), expected levels and visual order."""
    cases = []
    for line in (FIXTURES / "BidiCharacterTest-sample.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        code_points, direction, _, line_levels, order = line.split(";")
        text: str = "".join(chr(int(c, 16)) for c in code_points.split())
        rtl: bool | None = None if direction == "2" else direction == "1"
        cases.append((text, rtl, _levels(line_levels), [int(x) for x in order.split()]))
    return cases


# A character of each bidirectional type, for the tests of BidiTest.txt (given as types)
TYPE_CHARACTERS: dict[str, str] = {
    "L": "a", "R": "\u05d0", "AL": "\u0628", "EN": "1", "ES": "+", "ET": "%", "AN": "\u0661", "CS": ",",
    "NSM": "\u0300", "BN": "\u00ad", "S": "\t", "WS": " ", "ON": "!", "LRE": "\u202a", "LRO": "\u202d",
    "RLE": "\u202b", "RLO": "\u202e", "PDF": "\u202c", "LRI": "\u2066", "RLI": "\u2067", "FSI": "\u2068",
    "PDI": "\u2069",
}  # fmt: skip


def _type_cases() -> list[tuple[str, bool | None, list[int | None], list[int]]]:
    """Tests of the Unicode BidiTest.txt (sample in tests/fixtures): each sequence of types, for each paragraph
    direction of its bitset (1: auto, 2: left-to-right, 4: right-to-left)."""
    cases = []
    expected_levels: list[int | None] = []
    expected_order: list[int] = []
    for line in (FIXTURES / "BidiTest-sample.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("@Levels:"):
            expected_levels = _levels(line[len("@Levels:") :])
        elif line.startswith("@Reorder:"):
            expected_order = [int(x) for x in line[len("@Reorder:") :].split()]
        else:
            types, bitset = line.split(";")
            text: str = "".join(TYPE_CHARACTERS[t] for t in types.split())
            for bit, rtl in ((1, None), (2, False), (4, True)):
                if int(bitset) & bit:
                    cases.append((text, rtl, expected_levels, expected_order))
    return cases


CHARACTER_CASES = _character_cases()
TYPE_CASES = _type_cases()


def test_conformance_samples_are_large():
    assert len(CHARACTER_CASES) > 2000
    assert len(TYPE_CASES) > 5000
    explicit = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
    assert sum(any(c in explicit for c in text) for text, _, _, _ in CHARACTER_CASES) > 100


def check_conformance(text, rtl, expected_levels, expected_order) -> None:
    assert bidi.levels(text, rtl) == expected_levels
    if not any(unicodedata.category(c) in ("Mn", "Me") for c in text):  # Rule L3 (marks after letters) is not in it
        assert bidi.reorder(text, rtl) == expected_order


@pytest.mark.parametrize("text,rtl,expected_levels,expected_order", CHARACTER_CASES)
def test_unicode_character_conformance(text, rtl, expected_levels, expected_order):
    check_conformance(text, rtl, expected_levels, expected_order)


@pytest.mark.parametrize("text,rtl,expected_levels,expected_order", TYPE_CASES)
def test_unicode_type_conformance(text, rtl, expected_levels, expected_order):
    check_conformance(text, rtl, expected_levels, expected_order)


# ──────────────────────────────────────────────
# Explicit formatting characters
# ──────────────────────────────────────────────

LRE, RLE, PDF, LRO, RLO = "\u202a", "\u202b", "\u202c", "\u202d", "\u202e"
LRI, RLI, FSI, PDI = "\u2066", "\u2067", "\u2068", "\u2069"
LRM, RLM = "\u200e", "\u200f"


class TestExplicitFormatting:
    def test_isolate_keeps_its_content_in_order(self):
        """An isolate (here a file name with punctuation) is laid out alone, whatever the text around it."""
        assert visual(f"אב {LRI}file-1.txt!{PDI} גד") == "דג file-1.txt! בא"

    def test_first_strong_isolate_takes_the_direction_of_its_content(self):
        assert visual(f"abc {FSI}אב גד{PDI} def") == "abc דג בא def"
        assert visual(f"אב {FSI}abc def{PDI} גד") == "דג abc def בא"

    def test_isolate_does_not_change_the_paragraph_direction(self):
        """Rule P2: the text inside isolates is skipped to find the direction of the paragraph."""
        assert not bidi.is_rtl_paragraph(f"{RLI}אב{PDI} abc")
        assert bidi.is_rtl_paragraph(f"{LRI}abc{PDI} אב")

    def test_override_reverses_latin_text(self):
        """RLO draws its text from right to left, even without right-to-left letters."""
        assert bidi.needs_reordering(f"{RLO}abc{PDF}")
        assert visual(f"{RLO}abc{PDF}") == "cba"
        assert bidi.visual(f"x {RLO}abc{PDF} y") == "x cba y"

    def test_left_to_right_override_keeps_hebrew_in_order(self):
        assert visual(f"{LRO}אבג{PDF}") == "אבג"

    def test_embedding(self):
        assert visual(f"abc {RLE}def גד{PDF} hij") == "abc דג def hij"

    def test_marks(self):
        """LRM and RLM are strong letters without glyph: they change the direction of the neutral characters."""
        assert visual(f"אב 12{RLM}%") == "%12 בא"
        assert visual(f"אב (abc){LRM}") == "(abc) בא"

    def test_formatting_characters_are_not_displayed(self):
        text, order = bidi.visual_line(f"{RLM}אב {FSI}abc{PDI}{LRM} {RLE}ג{PDF}")
        assert not set(text) & set(LRE + RLE + PDF + LRO + RLO + LRI + RLI + FSI + PDI + LRM + RLM + "\u061c")
        assert text == "ג abc בא"
        assert len(order) == len(text)

    def test_unmatched_controls(self):
        """A PDI or a PDF without opening character, or an isolate without PDI, do not break the line."""
        assert visual(f"אב{PDI} גד{PDF}") == "דג בא"
        assert visual(f"abc {RLI}אב גד") == "abc דג בא"

    def test_deep_nesting_is_bounded(self):
        """Beyond level 125 (rule X5), the embeddings are ignored: no error. Latin letters at this odd level are at
        level 126 (rule I2)."""
        text: str = RLE * 200 + "abc" + PDF * 200
        assert bidi.levels(text)[200:203] == [126, 126, 126]

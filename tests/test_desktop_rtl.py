"""Right-to-left labels (core.rtl_labels) and the glyphs of every translation, in a real desktop window.

Skipped unless OPENMATB_DESKTOP_TESTS=1: a display is needed. tests/desktop/rtl.py runs with the installed pyglet
(pyglet 2 on desktop, pyglet 3 for the web) and saves screenshots of the labels and of the messages of each language
(run with -s to see where).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import bidi

ROOT: Path = Path(__file__).resolve().parents[1]
RUNNER: Path = ROOT / "tests" / "desktop" / "rtl.py"

pytestmark = pytest.mark.skipif(
    os.environ.get("OPENMATB_DESKTOP_TESTS") != "1", reason="desktop window tests: set OPENMATB_DESKTOP_TESTS=1"
)


@pytest.fixture(scope="module")
def result(tmp_path_factory) -> dict:
    out: Path = tmp_path_factory.mktemp("rtl")
    process = subprocess.run([sys.executable, str(RUNNER), str(out)], cwd=ROOT, capture_output=True, timeout=180)
    stderr: str = process.stderr.decode("utf-8", "replace")
    assert process.returncode == 0, stderr
    assert stderr.count("Traceback") == stderr.count("Exception ignored"), stderr
    data: dict = json.loads((out / "result.json").read_text(encoding="utf-8"))
    print(f"\npyglet {data['pyglet']}, screenshots: {out}")
    return data


@pytest.fixture(autouse=True)
def arabic():
    bidi.set_language("ar_SA")
    yield
    bidi.set_language("en_EN")


def displayed_word(word: str) -> str:
    """How an Arabic word is in the document of a label: shaped, letters from left to right."""
    return bidi.shape(word)[0][::-1]


class TestLabels:
    def test_ltr_label_unchanged(self, result):
        label = result["labels"]["english"]
        assert label["document"] == label["text"] == "System monitoring"
        assert label["align"] in (None, "left")

    @pytest.mark.parametrize("name", ["arabic", "mixed"])
    def test_rtl_label_in_display_order(self, result, name):
        label = result["labels"][name]
        assert label["document"] == label["expected"]
        assert label["document"] != label["text"]

    def test_text_property_gives_the_logical_text(self, result):
        assert result["labels"]["arabic"]["text"] == "مراقبة النظام"
        assert result["labels"]["mixed"]["text"] == "الوقت المتبقي \t 0:12:30"

    def test_tab_columns(self, result):
        """The value of a tab separated label stays on the left of its title (columns from the right)."""
        assert result["labels"]["mixed"]["document"].startswith("0:12:30 \t ")


class TestWrapping:
    def test_wrapped_on_several_lines(self, result):
        assert len(result["labels"]["wrapped"]["lines"]) >= 3

    def test_lines_fit_in_the_label(self, result):
        """Once reordered, each line still fits: pyglet does not break it again."""
        wrapped = result["labels"]["wrapped"]
        assert all(line["width"] <= wrapped["width"] for line in wrapped["lines"])

    def test_lines_follow_the_logical_order(self, result):
        """The first words are on the first line (on its right), the last words on the last line."""
        wrapped = result["labels"]["wrapped"]
        lines: list[str] = [line["text"] for line in wrapped["lines"]]
        current: int = 0  # Each word is on the line of the word before it, or on a later line
        for word in wrapped["text"].split():
            if bidi.has_rtl(word):
                while current < len(lines) and displayed_word(word.strip("،.")) not in lines[current]:
                    current += 1
                assert current < len(lines), word
        assert current == len(lines) - 1
        assert lines[0].rstrip("\u2028").endswith(displayed_word("في"))

    def test_aligned_to_the_right(self, result):
        assert result["labels"]["wrapped"]["align"] == "right"

    def test_centered_label_stays_centered(self, result):
        assert result["labels"]["centered"]["align"] == "center"
        assert result["labels"]["centered"]["lines"] >= 3


class TestHtml:
    def test_html_source_is_kept(self, result):
        assert "<b>OpenMATB</b>" in result["labels"]["html"]["text"]

    def test_bold_follows_its_text(self, result):
        assert result["labels"]["html"]["bold"] == [displayed_word("التعليمات"), "OpenMATB"]

    def test_paragraph_alignment(self, result):
        html = result["labels"]["html"]
        expected = ["center", "right"] + (["right"] if html["image"] else []) + [None]
        assert [a if a != "left" else None for a in html["aligns"]] == expected

    def test_ltr_paragraph_unchanged(self, result):
        assert "An English paragraph stays on the left." in result["labels"]["html"]["paragraphs"]

    def test_image_is_kept(self, result):
        html = result["labels"]["html"]
        if not html["image"]:
            pytest.skip("pyglet 3.0.dev10 cannot draw the images of HTML labels on desktop (pyglet#1527)")
        assert html["elements"] == 1


class TestTextChanges:
    def test_back_to_ltr(self, result):
        ltr = result["set_text"]["ltr"]
        assert ltr["document"].startswith("A left-to-right text")
        assert ltr["align"] in (None, "left")

    def test_rtl_again(self, result):
        assert result["set_text"]["rtl_align"] == "right"
        assert result["set_text"]["rtl_lines"] >= 3

    def test_paragraph_direction_depends_on_the_language(self, result):
        assert result["ltr_language"] == "Esc: " + displayed_word("خروج")
        assert result["rtl_language"] == displayed_word("خروج") + " :Esc"


def test_every_character_of_the_translations_has_a_glyph(result):
    """The default font (or the fonts the system falls back on) draws every character of every translation, after
    shaping (Arabic presentation forms): none is drawn as a missing glyph."""
    assert set(result["glyphs"]) >= {"ar_SA", "de_DE", "es_ES", "fr_FR", "it_IT", "ja_JP", "zh_CN"}
    missing = {language: glyphs["missing"] for language, glyphs in result["glyphs"].items() if glyphs["missing"]}
    assert not missing


# ──────────────────────────────────────────────
# OpenMATB in each language
# ──────────────────────────────────────────────

LANGUAGES: list[str] = sorted(p.parents[1].name for p in (ROOT / "locales").glob("*/LC_MESSAGES/openmatb.mo"))


@pytest.mark.parametrize("language", LANGUAGES)
def test_openmatb_runs_in_each_language(tmp_path, language):
    """The scenario of tests/test_desktop_smoke.py, in each language: it runs to its end, its dialogs and failures are
    answered, and the tasks are drawn (screenshot printed with -s)."""
    from tests.test_desktop_smoke import RUNNER as SMOKE_RUNNER
    from tests.test_desktop_smoke import SCENARIO

    scenario: Path = tmp_path / "smoke.txt"
    scenario.write_text(SCENARIO, encoding="utf-8")
    env: dict[str, str] = {**os.environ, "OPENMATB_TEST_LANGUAGE": language, "PYTHONIOENCODING": "utf-8"}
    process = subprocess.run(
        [sys.executable, str(SMOKE_RUNNER), str(tmp_path), str(scenario)], cwd=ROOT, capture_output=True, env=env,
        timeout=120,
    )  # fmt: skip
    stderr: str = process.stderr.decode("utf-8", "replace")
    assert process.returncode == 0, stderr
    assert stderr.count("Traceback") == stderr.count("Exception ignored"), stderr
    run: dict = json.loads((tmp_path / "result_run.json").read_text(encoding="utf-8"))
    print(f"\n{language}: {tmp_path / 'screenshot_run.png'}")
    assert run["answered"] == ["F1", "F5"]
    assert run["screenshot_colors"] > 50

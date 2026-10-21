# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Right-to-left labels and the glyphs of the translations, in a real desktop window, for tests/test_desktop_rtl.py.

    python tests/desktop/rtl.py OUT_DIR

Writes OUT_DIR/result.json: what pyglet labels (patched by core.rtl_labels) contain and how they are laid out, and
for each language of locales/, the characters of its messages that the default font cannot draw (drawn as the glyph
of an unassigned character). Screenshots of the labels and of the messages of each language: OUT_DIR/*.png.
"""

from __future__ import annotations

import builtins
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT: Path = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path[:0] = [str(ROOT), str(ROOT / "locales")]
builtins._ = lambda s: s

import build  # noqa: E402
import pyglet  # noqa: E402

from core import bidi, rtl_labels  # noqa: E402
from core.pyglet_compat import PYGLET_3, get_screenshot  # noqa: E402

if PYGLET_3:
    from pyglet.graphics.api import gl
else:
    from pyglet import gl

out: Path = Path(sys.argv[1]).resolve()
rtl_labels.install()
window = pyglet.window.Window(1000, 700, visible=True)
gl.glClearColor(1, 1, 1, 1)
BLACK = (0, 0, 0, 255)
ARABIC_TEXT: str = (
    "في هذه المهمة، يجب عليك مراقبة الأضواء والمقاييس. اضغط على المفتاح F1 عندما يتغير لون الضوء، "
    "وعلى F5 عندما يبتعد المؤشر عن المركز. ستستمر المهمة 5 دقائق."
)
result: dict[str, Any] = {"pyglet": pyglet.version}


def screenshot(name: str, batch: pyglet.graphics.Batch) -> None:
    window.switch_to()
    window.dispatch_events()
    window.clear()
    batch.draw()
    get_screenshot().save(str(out / f"{name}.png"))


def lines(label: Any) -> list[dict[str, Any]]:
    """The lines laid out by pyglet: their text and width."""
    text: str = label.document.text
    starts: list[int] = [line.start for line in label._lines] + [len(text)]
    return [{"text": text[a:b], "width": line.width} for (a, b), line in zip(zip(starts, starts[1:]), label._lines)]


def bold(document: Any) -> list[str]:
    """The runs of bold text of a formatted document (bold=True in pyglet 2, weight="bold" in pyglet 3)."""
    runs: list[str] = []
    for attribute in ("bold", "weight"):
        for start, end, value in document.get_style_runs(attribute).ranges(0, len(document.text)):
            if value is True or value == "bold":
                runs.append(document.text[start:end])
    return runs


# ──────────────────────────────────────────────
# Labels
# ──────────────────────────────────────────────

bidi.set_language("ar_SA")
batch = pyglet.graphics.Batch()
K: dict[str, Any] = dict(batch=batch, color=BLACK, font_size=14)

english = pyglet.text.Label("System monitoring", x=10, y=680, **K)
arabic = pyglet.text.Label("مراقبة النظام", x=10, y=650, **K)
mixed = pyglet.text.Label("الوقت المتبقي \t 0:12:30", x=10, y=620, **K)
wrapped = pyglet.text.Label(ARABIC_TEXT, x=10, y=590, width=300, multiline=True, anchor_y="top", **K)
centered = pyglet.text.Label(ARABIC_TEXT, x=330, y=590, width=300, multiline=True, anchor_y="top", align="center", **K)
# pyglet 3.0.dev10 cannot draw the images of HTML labels on desktop (MissingAttributeException), with or without
# right-to-left text: fixed by pyglet#1527, after 3.0.dev11
IMAGE: str = "" if PYGLET_3 else '<p>صورة: <img src="logo32.png"> نهاية.</p>'
html = pyglet.text.HTMLLabel(
    "<center><b>التعليمات</b></center>"
    "<p>مرحباً بك في <b>OpenMATB</b>. ستقوم بأربع مهام في الوقت نفسه: المراقبة، والتتبع، والاتصالات، وإدارة الموارد.</p>"
    + IMAGE
    + "<p>An English paragraph stays on the left.</p>",
    x=650, y=590, width=340, multiline=True, anchor_y="top", batch=batch,
    location=pyglet.resource.FileLocation("includes/img"),
)  # fmt: skip
screenshot("labels", batch)

result["labels"] = {
    "english": {"text": english.text, "document": english.document.text, "align": english.document.get_style("align")},
    "arabic": {"text": arabic.text, "document": arabic.document.text, "expected": bidi.visual(arabic.text)},
    "mixed": {"text": mixed.text, "document": mixed.document.text, "expected": bidi.visual(mixed.text)},
    "wrapped": {
        "text": wrapped.text,
        "lines": lines(wrapped),
        "align": wrapped.document.get_style("align"),
        "width": wrapped.width,
    },
    "centered": {"align": centered.document.get_style("align"), "lines": len(centered._lines)},
    "html": {
        "text": html.text,
        "document": html.document.text,
        "bold": bold(html.document),
        "elements": len(html.document._elements),
        "image": bool(IMAGE),
        "aligns": [
            html.document.get_style("align", i)
            for i, c in enumerate(html.document.text)
            if i == 0 or html.document.text[i - 1] in "\n\u2029"
        ],
        "paragraphs": [p for p in html.document.text.replace("\u2029", "\n").split("\n")],
    },
}

# Changing the text: back to left-to-right, then right-to-left again
wrapped.text = "A left-to-right text, wrapped on several lines like the instructions of a task."
after_ltr: dict[str, Any] = {"document": wrapped.document.text, "align": wrapped.document.get_style("align")}
wrapped.text = ARABIC_TEXT
result["set_text"] = {
    "ltr": after_ltr,
    "rtl_text": wrapped.text,
    "rtl_align": wrapped.document.get_style("align"),
    "rtl_lines": len(wrapped._lines),
}

# In a left-to-right language, a mixed paragraph follows its first letter
bidi.set_language("en_EN")
result["ltr_language"] = pyglet.text.Label("Esc: خروج", batch=batch).document.text
bidi.set_language("ar_SA")
result["rtl_language"] = pyglet.text.Label("Esc: خروج", batch=batch).document.text

# ──────────────────────────────────────────────
# Glyphs of the translations
# ──────────────────────────────────────────────


def glyph_image(font: Any, c: str) -> tuple[int, int, bytes]:
    glyphs: Any = font.get_glyphs(c, True) if PYGLET_3 else font.get_glyphs(c)
    glyph: Any = glyphs[0][0] if isinstance(glyphs, tuple) else glyphs[0]  # (glyphs, offsets) since pyglet 2.1
    data: Any = glyph.get_image_data()
    get = data.get_bytes if hasattr(data, "get_bytes") else data.get_data
    return data.width, data.height, bytes(get("RGBA", data.width * 4))


font = pyglet.font.load(None, 16)  # OpenMATB's default font (font_name empty in config.ini)
missing_glyph = glyph_image(font, "͸")  # Unassigned character
result["glyphs"] = {}
for path in build.po_files():
    language: str = path.parents[1].name
    bidi.set_language(language)
    _, translations = build.read_po(path)
    characters: set[str] = set()
    for msgstr in translations.values():
        characters |= set(bidi.visual(msgstr)) - set(" \t\n\u2028")
    missing: list[str] = sorted(c for c in characters if glyph_image(font, c) == missing_glyph)
    result["glyphs"][language] = {"characters": len(characters), "missing": missing}

    # The messages of the language, as OpenMATB draws them (for a human check)
    language_batch = pyglet.graphics.Batch()
    shown: list[Any] = []
    for i, msgstr in enumerate(m for m in translations.values() if m and len(m) < 70):
        if i >= 36:
            break
        x, y = (10 if i < 18 else 505), 680 - (i % 18) * 37
        shown.append(
            pyglet.text.Label(
                msgstr, x=x, y=y, width=480, multiline=True, anchor_y="top", **{**K, "batch": language_batch}
            )
        )
    screenshot(f"messages_{language}", language_batch)

(out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
window.close()

# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""pyglet labels (Label, HTMLLabel) that display right-to-left text, with core.bidi.

install() patches the pyglet label classes: when the text of a label has right-to-left characters, its document gets
the characters to draw from left to right (shaped Arabic letters, each line in display order). Wrapping is kept: the
lines are those pyglet breaks the logical text into, each one then reordered and ended by a line separator.
Right-to-left paragraphs of multiline labels are aligned to the right, unless they are centered.

label.text still gives the logical text. Labels without right-to-left characters are not changed at all.
Uses two private attributes of pyglet layouts, the same in pyglet 2 and pyglet 3: _lines (their start) and
_wrap_lines; and the _style_runs of formatted documents (HTML labels).
"""

from __future__ import annotations

from typing import Any

from pyglet.text import DocumentLabel, HTMLLabel, Label
from pyglet.text.document import FormattedDocument

from core import bidi

LINE_SEPARATOR: str = "\u2028"  # A line break that does not start a paragraph
OBJECT: str = "\ufffc"  # Object replacement character
_BREAKS: str = "\n\u2028\u2029"
_installed: bool = False


def install() -> None:
    """Patch the pyglet labels (once)."""
    global _installed
    if _installed:
        return
    _installed = True

    document_text: property = DocumentLabel.text
    html_text: property = HTMLLabel.text

    def get_text(label: DocumentLabel) -> str:
        logical: str | None = getattr(label, "_bidi_logical", None)
        return document_text.fget(label) if logical is None else logical

    def set_text(label: DocumentLabel, text: str) -> None:
        label._bidi_logical = None
        document_text.fset(label, text)
        apply(label)

    def set_html_text(label: HTMLLabel, text: str) -> None:
        html_text.fset(label, text)
        apply(label)

    DocumentLabel.text = property(get_text, set_text, doc=document_text.__doc__)
    HTMLLabel.text = property(html_text.fget, set_html_text, doc=html_text.__doc__)

    for cls in (Label, HTMLLabel):
        _wrap_init(cls)


def _wrap_init(cls: type) -> None:
    init = cls.__init__

    def __init__(self: DocumentLabel, *args: Any, **kwargs: Any) -> None:
        init(self, *args, **kwargs)
        apply(self)

    __init__.__wrapped__ = init
    cls.__init__ = __init__


def apply(label: DocumentLabel) -> None:
    """Put the document of the label in display order, if it has right-to-left text."""
    document: Any = label.document
    logical: str = document.text
    if not isinstance(label, HTMLLabel):
        _restore_align(label)
        if not bidi.needs_reordering(logical):
            label._bidi_logical = None
            return
        label._bidi_logical = logical
    elif not bidi.needs_reordering(logical):
        return

    shaped, sources = bidi.shape(logical)
    if isinstance(document, FormattedDocument):
        document = _rebuild(document, shaped, sources)
        label.document = document
    else:
        document.text = shaped
    lines: list[tuple[int, int, str]] = _lines(label, shaped)

    text: list[str] = []
    order: list[int | None] = []  # Index in shaped of each character, None for the line separators added
    rtl_paragraphs: list[tuple[int, int]] = []
    paragraph_rtl: bool = False
    for start, end, ending in lines:
        if start == 0 or shaped[start - 1] in "\n\u2029":
            paragraph_rtl = bidi.is_rtl_paragraph(_paragraph(shaped, start))
        line_start: int = len(text)
        # An inline element (an image) is the character "\0", removed by the bidirectional algorithm (BN): it is laid
        # out as the object replacement character, then put back
        line: str = shaped[start:end].replace("\0", OBJECT)
        visual, line_order = bidi.visual_line(line, paragraph_rtl)
        text.extend("\0" if c == OBJECT and shaped[start + i] == "\0" else c for c, i in zip(visual, line_order))
        order.extend(start + i for i in line_order)
        if paragraph_rtl:
            rtl_paragraphs.append((line_start, len(text)))
        if ending:
            text.append(ending)
            order.append(end if shaped[end : end + 1] == ending else None)
    visual_text: str = "".join(text)

    if isinstance(document, FormattedDocument):
        document = _rebuild(document, visual_text, order)
        for start, end in rtl_paragraphs:
            if document.get_style("align", start) in (None, "left"):
                document.set_paragraph_style(start, max(end, start + 1), {"align": "right"})
        label.document = document
    else:
        document.text = visual_text
        if rtl_paragraphs and label.multiline and document.get_style("align") in (None, "left"):
            label._bidi_align = document.get_style("align")
            document.set_style(0, len(visual_text), {"align": "right"})


def _restore_align(label: DocumentLabel) -> None:
    """A label aligned to the right for a right-to-left text gets back its alignment."""
    if hasattr(label, "_bidi_align"):
        label.document.set_style(0, len(label.document.text), {"align": label._bidi_align})
        del label._bidi_align


def _paragraph(text: str, start: int) -> str:
    end: int = start
    while end < len(text) and text[end] not in "\n\u2029":
        end += 1
    return text[start:end]


def _lines(label: DocumentLabel, text: str) -> list[tuple[int, int, str]]:
    """The lines of the text in the label: (start, end, line break), end excluding the line break and, for a wrapped
    line, its trailing spaces. The line break of a wrapped line is a line separator."""
    starts: list[int] = [0]
    if getattr(label, "_wrap_lines", False):
        starts = sorted({line.start for line in label._lines} | {0})
    starts.extend(i + 1 for i, c in enumerate(text) if c in _BREAKS)
    starts = sorted({s for s in starts if s <= len(text)})

    lines: list[tuple[int, int, str]] = []
    for k, start in enumerate(starts):
        end: int = starts[k + 1] if k + 1 < len(starts) else len(text)
        if end > start and text[end - 1] in _BREAKS:
            lines.append((start, end - 1, text[end - 1]))
        elif k + 1 < len(starts):  # Wrapped: the spaces where the line was broken are not drawn
            trimmed: int = end
            while trimmed > start and text[trimmed - 1] in " ​":
                trimmed -= 1
            lines.append((start, trimmed, LINE_SEPARATOR))
        else:
            lines.append((start, end, ""))
    return lines


def _rebuild(document: FormattedDocument, text: str, sources: list[int | None]) -> FormattedDocument:
    """A formatted document with the given text, each of its characters taking the style (and the inline element, an
    image) of the character of the document it comes from (sources). A character without source takes the style of the
    character before it."""
    old_text: str = document.text
    names: list[str] = list(document._style_runs)
    styles: list[list[Any]] = []
    for name in names:
        values: list[Any] = [None] * len(old_text)
        for start, end, value in document.get_style_runs(name).ranges(0, len(old_text)):
            values[start:end] = [value] * (end - start)
        styles.append(values)
    elements: dict[int, Any] = {element.position: element for element in document._elements}

    new: FormattedDocument = FormattedDocument()
    chunk: list[str] = []
    chunk_attributes: dict[str, Any] | None = None
    source: int | None = None

    def flush() -> None:
        if chunk:
            new.insert_text(len(new.text), "".join(chunk), chunk_attributes)
            chunk.clear()

    for c, index in zip(text, sources):
        source = index if index is not None else source
        attributes: dict[str, Any] = (
            {name: values[source] for name, values in zip(names, styles)} if source is not None else {}
        )
        element: Any = elements.get(index) if index is not None and c == "\0" else None
        if element is not None:
            flush()
            element._position = None
            new.insert_element(len(new.text), element, attributes)
            continue
        if attributes != chunk_attributes:
            flush()
            chunk_attributes = attributes
        chunk.append(c)
    flush()
    return new

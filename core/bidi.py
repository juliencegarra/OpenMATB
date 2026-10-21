# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Right-to-left text (Arabic, Hebrew, Persian...) for pyglet, which only lays out text from left to right.

pyglet neither reorders right-to-left text nor, in the browser, joins Arabic letters (pyglet 3.0.dev10, see
pyglet/font/dwrite: "Right to left should be handled by pyglet?"). This module turns a text into the characters to
draw from left to right:
- shape(): each Arabic letter is replaced by its contextual form (isolated, initial, medial or final), taken from the
  Unicode presentation forms, and lam + alef by their ligature. Each form is a character of its own, drawn as is.
- visual(): the characters of each line are put in display order, with the Unicode bidirectional algorithm (UAX #9,
  explicit embeddings, overrides and isolates included): right-to-left runs are reversed, numbers and left-to-right
  words keep their order, brackets are mirrored. The formatting characters (LRM, RLE, FSI...) are not displayed.
  Checked with the conformance tests of Unicode (tests/test_bidi.py).

Lines must be split before visual() (wrapping happens on the logical order): core.rtl_labels does it for the labels.
Texts without right-to-left characters (or formatting characters that may reverse text) are returned unchanged.
"""

from __future__ import annotations

import unicodedata

# Languages written from right to left: their paragraphs are right-to-left as soon as they contain such a character
RTL_LANGUAGES: tuple[str, ...] = ("ar", "fa", "he", "ur", "yi")
_rtl_language: bool = False


def set_language(language_iso: str) -> None:
    """Paragraphs mixing both directions are right-to-left in a right-to-left language (en_EN, ar_SA...)."""
    global _rtl_language
    _rtl_language = is_rtl_language(language_iso)


def is_rtl_language(language_iso: str) -> bool:
    return language_iso.split("_")[0].split("-")[0].lower() in RTL_LANGUAGES


def has_rtl(text: str) -> bool:
    """Whether the text has a right-to-left character (Hebrew, Arabic...)."""
    if text.isascii():
        return False
    return any(unicodedata.bidirectional(c) in ("R", "AL") for c in text)


# ──────────────────────────────────────────────
# Arabic shaping
# ──────────────────────────────────────────────

LAM: str = "ل"
ALEFS: str = "آأإا"  # With madda, hamza above, hamza below, alone
# Join with the letters on both sides without changing (tatweel, zero width joiner)
_JOIN_CAUSING: frozenset[str] = frozenset("ـ‍")


def _presentation_forms() -> tuple[dict[str, dict[str, str]], dict[tuple[str, str], dict[str, str]]]:
    """The contextual forms of the Arabic letters, and the lam-alef ligatures (the only mandatory ones), read from the
    Unicode presentation forms (their decomposition is "<final> 0628": the final form of U+0628)."""
    forms: dict[str, dict[str, str]] = {}
    ligatures: dict[tuple[str, str], dict[str, str]] = {}
    for code in [*range(0xFB50, 0xFE00), *range(0xFE70, 0xFF00)]:
        tag, *letters = unicodedata.decomposition(chr(code)).split() or [""]
        form: str = tag.strip("<>")
        if form not in ("isolated", "final", "initial", "medial"):
            continue
        chars: list[str] = [chr(int(letter, 16)) for letter in letters]
        if len(chars) == 1:
            forms.setdefault(chars[0], {}).setdefault(form, chr(code))
        elif len(chars) == 2 and chars[0] == LAM and chars[1] in ALEFS:
            ligatures.setdefault((chars[0], chars[1]), {}).setdefault(form, chr(code))
    return forms, ligatures


FORMS, LIGATURES = _presentation_forms()


def _is_transparent(c: str) -> bool:
    """Marks (harakat...) are skipped when looking for the letters on each side."""
    return unicodedata.category(c) in ("Mn", "Me")


def _joins_next(c: str | None) -> bool:
    """Whether c connects to the letter after it (it has an initial or a medial form)."""
    return c is not None and (c in _JOIN_CAUSING or ("initial" in FORMS.get(c, {}) or "medial" in FORMS.get(c, {})))


def _joins_previous(c: str | None) -> bool:
    """Whether c connects to the letter before it (it has a final or a medial form)."""
    return c is not None and (c in _JOIN_CAUSING or ("final" in FORMS.get(c, {}) or "medial" in FORMS.get(c, {})))


def _neighbour(text: str, index: int, step: int) -> int | None:
    """The index of the first letter (not a mark) before (step=-1) or after (step=1) index."""
    index += step
    while 0 <= index < len(text):
        if not _is_transparent(text[index]):
            return index
        index += step
    return None


def shape(text: str) -> tuple[str, list[int]]:
    """The text with the contextual forms of its Arabic letters, and for each of its characters, the index of the
    character of text it comes from (a lam-alef ligature comes from the lam, the alef is dropped)."""
    if not has_rtl(text):
        return text, list(range(len(text)))
    out: list[str] = []
    sources: list[int] = []
    i: int = 0
    while i < len(text):
        c: str = text[i]
        if c not in FORMS:
            out.append(c)
            sources.append(i)
            i += 1
            continue
        before: int | None = _neighbour(text, i, -1)
        after: int | None = _neighbour(text, i, 1)
        previous: str | None = text[before] if before is not None else None
        following: str | None = text[after] if after is not None else None
        connect_previous: bool = _joins_next(previous) and _joins_previous(c)

        if c == LAM and following is not None and (LAM, following) in LIGATURES:
            ligature: dict[str, str] = LIGATURES[(LAM, following)]
            out.append(ligature["final" if connect_previous and "final" in ligature else "isolated"])
            sources.append(i)
            for mark in range(i + 1, after):  # The marks of the lam, then those of the alef
                out.append(text[mark])
                sources.append(mark)
            i = after + 1
            continue

        connect_next: bool = _joins_next(c) and _joins_previous(following)
        form: str = {
            (True, True): "medial",
            (True, False): "final",
            (False, True): "initial",
            (False, False): "isolated",
        }[(connect_previous, connect_next)]
        out.append(FORMS[c].get(form) or FORMS[c].get("isolated", c))
        sources.append(i)
        i += 1
    return "".join(out), sources


# ──────────────────────────────────────────────
# Bidirectional reordering
# ──────────────────────────────────────────────

_STRONG: dict[str, str] = {"L": "L", "R": "R", "AL": "R"}
# Paired brackets (Bidi_Paired_Bracket, the most common ones): rule N0, and mirrored as the other pairs (rule L4)
BRACKET_PAIRS: tuple[str, ...] = (
    "()", "[]", "{}", "⁅⁆", "⁽⁾", "₍₎", "\u2329\u232a", "\u3008\u3009", "⟨⟩", "⟦⟧", "⦃⦄", "《》", "「」", "『』",
    "【】", "〔〕", "〖〗", "〘〙", "〚〛", "（）", "［］", "｛｝", "｢｣", "༺༻", "༼༽", "᚛᚜",
)  # fmt: skip
_MIRRORS: dict[str, str] = {}
for _pair in (*BRACKET_PAIRS, "<>", "«»", "‹›", "≤≥"):
    _MIRRORS[_pair[0]], _MIRRORS[_pair[1]] = _pair[1], _pair[0]


_OPENING_BRACKETS: dict[str, str] = {pair[0]: pair[1] for pair in BRACKET_PAIRS}


def _canonical(c: str) -> str:
    """〈 (U+2329) and 〈 (U+3008) are the same bracket (canonical equivalents)."""
    return unicodedata.normalize("NFD", c)


def _resolve_brackets(line: str, direction: list[str], base_direction: str, sos: str) -> None:
    """Rule N0: both brackets of a pair take the same direction, from their content and the text before them, so that
    "(pip install pyparallel)" in Arabic text keeps both its brackets on the same side."""
    pairs: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for i, c in enumerate(line):
        if direction[i] != "ON":
            continue
        if c in _OPENING_BRACKETS:
            if len(stack) == 63:  # BD16: too deep, no pair at all
                return
            stack.append((_canonical(_OPENING_BRACKETS[c]), i))
        elif c in _MIRRORS and c not in _OPENING_BRACKETS:
            for depth in range(len(stack) - 1, -1, -1):
                if stack[depth][0] == _canonical(c):
                    pairs.append((stack[depth][1], i))
                    del stack[depth:]
                    break
    for opening, closing in sorted(pairs):
        inside: set[str] = {d for d in direction[opening + 1 : closing] if d in ("L", "R")}
        if not inside:
            continue
        if base_direction in inside:
            resolved: str = base_direction
        else:
            before: str = next((d for d in reversed(direction[:opening]) if d in ("L", "R")), sos)
            resolved = before if before in inside else base_direction
        for bracket in (opening, closing):
            direction[bracket] = resolved
            mark: int = bracket + 1  # The marks of a bracket take its direction
            while mark < len(line) and unicodedata.bidirectional(line[mark]) == "NSM":
                direction[mark] = resolved
                mark += 1


# Explicit formatting characters (rules X1 to X10)
_EMBEDDINGS: frozenset[str] = frozenset(("LRE", "RLE", "LRO", "RLO", "PDF"))
_ISOLATE_INITIATORS: frozenset[str] = frozenset(("LRI", "RLI", "FSI"))
_REMOVED: frozenset[str] = _EMBEDDINGS | {"BN"}  # Rule X9: ignored by the following rules, not displayed
# Characters that may start right-to-left text without being right-to-left letters: RLE, RLO, RLI, FSI
_RTL_CONTROLS: str = "‫‮⁧⁨"
# Invisible marks and isolates, not displayed (pyglet would draw them as blanks)
_INVISIBLE: frozenset[str] = frozenset("‎‏؜⁦⁧⁨⁩")
MAX_DEPTH: int = 125


def needs_reordering(text: str) -> bool:
    """Whether the text has right-to-left characters, or explicit formatting characters that may reverse text."""
    return has_rtl(text) or any(c in _RTL_CONTROLS for c in text)


def _matching_pdis(types: list[str]) -> dict[int, int]:
    """Rule BD9: the PDI that closes each isolate initiator (an initiator may have none)."""
    matching: dict[int, int] = {}
    stack: list[int] = []
    for i, t in enumerate(types):
        if t in _ISOLATE_INITIATORS:
            stack.append(i)
        elif t == "PDI" and stack:
            matching[stack.pop()] = i
    return matching


def _first_strong(types: list[str], start: int, end: int) -> str | None:
    """Rules P2, P3: the direction (L or R) of the first letter, skipping the text inside isolates."""
    depth: int = 0
    for i in range(start, end):
        t: str = types[i]
        if t in _ISOLATE_INITIATORS:
            depth += 1
        elif t == "PDI":
            depth = max(0, depth - 1)
        elif depth == 0 and t in _STRONG:
            return _STRONG[t]
    return None


def is_rtl_paragraph(text: str) -> bool:
    """The direction of a paragraph: right-to-left in a right-to-left language as soon as it has a right-to-left
    character, otherwise the direction of its first letter (rules P2, P3 of UAX #9)."""
    if _rtl_language and has_rtl(text):
        return True
    return _first_strong([unicodedata.bidirectional(c) for c in text], 0, len(text)) == "R"


def _explicit_levels(types: list[str], base: int) -> tuple[list[int], list[str]]:
    """Rules X1 to X8: the embedding level of each character, and the types changed by the overrides (LRO, RLO)."""
    matching: dict[int, int] = _matching_pdis(types)
    result_levels: list[int] = [base] * len(types)
    result_types: list[str] = list(types)
    stack: list[tuple[int, str | None, bool]] = [(base, None, False)]  # Level, override, isolate
    overflow_isolates: int = 0
    overflow_embeddings: int = 0
    valid_isolates: int = 0
    for i, t in enumerate(types):
        level, override, _ = stack[-1]
        if t in ("RLE", "LRE", "RLO", "LRO"):
            new_level: int = (level + 1) | 1 if t[0] == "R" else (level + 2) & ~1
            if new_level <= MAX_DEPTH and overflow_isolates == 0 and overflow_embeddings == 0:
                stack.append((new_level, {"RLO": "R", "LRO": "L"}.get(t), False))
            elif overflow_isolates == 0:
                overflow_embeddings += 1
            result_levels[i] = level
        elif t in _ISOLATE_INITIATORS:
            result_levels[i] = level
            if override:
                result_types[i] = override
            rtl: bool = t == "RLI"
            if t == "FSI":
                rtl = _first_strong(types, i + 1, matching.get(i, len(types))) == "R"
            new_level = (level + 1) | 1 if rtl else (level + 2) & ~1
            if new_level <= MAX_DEPTH and overflow_isolates == 0 and overflow_embeddings == 0:
                valid_isolates += 1
                stack.append((new_level, None, True))
            else:
                overflow_isolates += 1
        elif t == "PDI":
            if overflow_isolates > 0:
                overflow_isolates -= 1
            elif valid_isolates > 0:
                overflow_embeddings = 0
                while not stack[-1][2]:
                    stack.pop()
                stack.pop()
                valid_isolates -= 1
            level, override, _ = stack[-1]
            result_levels[i] = level
            if override:
                result_types[i] = override
        elif t == "PDF":
            if overflow_isolates == 0:
                if overflow_embeddings > 0:
                    overflow_embeddings -= 1
                elif not stack[-1][2] and len(stack) >= 2:
                    stack.pop()
            result_levels[i] = level
        elif t == "B":
            result_levels[i] = base
        else:
            result_levels[i] = level
            if override and t != "BN":
                result_types[i] = override
    return result_levels, result_types


def _isolating_run_sequences(types: list[str], embedding_levels: list[int]) -> list[list[int]]:
    """Rules BD13, X10: the characters (not removed by X9) in runs of the same level, an isolate joined to the run
    that starts with its matching PDI."""
    runs: list[list[int]] = []
    for i, t in enumerate(types):
        if t in _REMOVED:
            continue
        if runs and embedding_levels[runs[-1][-1]] == embedding_levels[i]:
            runs[-1].append(i)
        else:
            runs.append([i])
    matching: dict[int, int] = _matching_pdis(types)
    closing: set[int] = set(matching.values())
    run_starting_at: dict[int, list[int]] = {run[0]: run for run in runs}
    sequences: list[list[int]] = []
    for run in runs:
        if run[0] in closing:
            continue  # Continues the sequence of its isolate initiator
        sequence: list[int] = list(run)
        while sequence[-1] in matching and matching[sequence[-1]] in run_starting_at:
            sequence.extend(run_starting_at[matching[sequence[-1]]])
        sequences.append(sequence)
    return sequences


def _resolve_sequence(line: str, types: list[str], sequence: list[int], sos: str, eos: str, embedding: str) -> None:
    """Rules W1 to W7, N0, N1 and N2 on an isolating run sequence: its types become L, R, EN or AN."""
    t: list[str] = [types[i] for i in sequence]
    n: int = len(t)
    # W1: a mark takes the type of the character before it (neutral after an isolate initiator or a PDI)
    for k in range(n):
        if t[k] == "NSM":
            previous: str = t[k - 1] if k > 0 else sos
            t[k] = "ON" if previous in _ISOLATE_INITIATORS or previous == "PDI" else previous
    # W2: European numbers after an Arabic letter are Arabic numbers. W3: Arabic letters are right-to-left
    last_strong: str = sos
    for k in range(n):
        if t[k] in ("L", "R", "AL"):
            last_strong = t[k]
        elif t[k] == "EN" and last_strong == "AL":
            t[k] = "AN"
    t = ["R" if x == "AL" else x for x in t]
    # W4: a single separator between two numbers of the same kind belongs to them (1,000 or 12:30)
    for k in range(1, n - 1):
        if t[k] == "ES" and t[k - 1] == "EN" and t[k + 1] == "EN":
            t[k] = "EN"
        elif t[k] == "CS" and t[k - 1] == t[k + 1] and t[k - 1] in ("EN", "AN"):
            t[k] = t[k - 1]
    # W5: terminators (%, $...) next to European numbers belong to them
    for k in range(n):
        if t[k] == "EN":
            j: int = k - 1
            while j >= 0 and t[j] == "ET":
                t[j] = "EN"
                j -= 1
            j = k + 1
            while j < n and t[j] == "ET":
                t[j] = "EN"
                j += 1
    # W6: the other separators and terminators are neutral
    t = ["ON" if x in ("ES", "ET", "CS") else x for x in t]
    # W7: European numbers after a left-to-right letter (or at the start of a left-to-right sequence) are
    # left-to-right
    last_strong = sos
    for k in range(n):
        if t[k] in ("L", "R"):
            last_strong = t[k]
        elif t[k] == "EN" and last_strong == "L":
            t[k] = "L"
    # Numbers count as right-to-left for the neutral characters around them
    direction: list[str] = ["R" if x in ("R", "EN", "AN") else x for x in t]
    _resolve_brackets("".join(line[i] for i in sequence), direction, embedding, sos)
    t = [d if x == "ON" and d in ("L", "R") else x for x, d in zip(t, direction)]
    # N1, N2: neutral characters between two characters of the same direction take it, otherwise the direction of
    # the embedding
    k = 0
    while k < n:
        if direction[k] in ("L", "R"):
            k += 1
            continue
        j = k
        while j < n and direction[j] not in ("L", "R"):
            j += 1
        before: str = direction[k - 1] if k > 0 else sos
        after: str = direction[j] if j < n else eos
        resolved: str = before if before == after else embedding
        for m in range(k, j):
            t[m] = resolved
        k = j
    for k, i in enumerate(sequence):
        types[i] = t[k]


def _direction(level: int) -> str:
    return "R" if level % 2 else "L"


def levels(line: str, rtl: bool | None = None) -> list[int | None]:
    """The embedding level of each character of a line (even: left-to-right, odd: right-to-left), None for the
    embedding characters and BN, removed by rule X9."""
    original: list[str] = [unicodedata.bidirectional(c) or "L" for c in line]
    base: int = int(is_rtl_paragraph(line) if rtl is None else rtl)
    embedding_levels, types = _explicit_levels(original, base)
    kept: list[int] = [i for i, t in enumerate(original) if t not in _REMOVED]
    position: dict[int, int] = {i: k for k, i in enumerate(kept)}
    for sequence in _isolating_run_sequences(original, embedding_levels):
        level: int = embedding_levels[sequence[0]]
        first, last = position[sequence[0]], position[sequence[-1]]
        before: int = embedding_levels[kept[first - 1]] if first > 0 else base
        after: int = embedding_levels[kept[last + 1]] if last + 1 < len(kept) else base
        if original[sequence[-1]] in _ISOLATE_INITIATORS:
            after = base  # The sequence ends with an isolate initiator without its PDI
        sos, eos = _direction(max(level, before)), _direction(max(level, after))
        _resolve_sequence(line, types, sequence, sos, eos, _direction(level))
    # I1, I2: implicit levels
    result: list[int | None] = [None] * len(line)
    for i in kept:
        level = embedding_levels[i]
        if level % 2 == 0:
            result[i] = level + {"R": 1, "EN": 2, "AN": 2}.get(types[i], 0)
        else:
            result[i] = level + {"L": 1, "EN": 1, "AN": 1}.get(types[i], 0)
    # L1: tabs, and the spaces and isolates before them or at the end of the line, are at the paragraph level
    trailing: bool = True
    for i in reversed(kept):
        if original[i] in ("S", "B"):
            result[i] = base
            trailing = True
        elif original[i] in ("WS", "LRI", "RLI", "FSI", "PDI") and trailing:
            result[i] = base
        else:
            trailing = False
    return result


def reorder(line: str, rtl: bool | None = None) -> list[int]:
    """The indices of the characters of a line (without line break) in display order, from left to right. The
    characters removed by rule X9 (embeddings, BN) are left out."""
    line_levels: list[int | None] = levels(line, rtl)
    # The marks stay after their letter (rule L3): reverse clusters, not characters
    clusters: list[list[int]] = []
    cluster_levels: list[int] = []
    for i, c in enumerate(line):
        level: int | None = line_levels[i]
        if level is None:
            continue
        if clusters and _is_transparent(c) and level == cluster_levels[-1]:
            clusters[-1].append(i)
        else:
            clusters.append([i])
            cluster_levels.append(level)
    # L2: from the highest level to the lowest odd level, reverse each run at this level or higher
    highest: int = max(cluster_levels, default=0)
    lowest_odd: int = min((level for level in cluster_levels if level % 2), default=highest + 1)
    order: list[int] = list(range(len(clusters)))
    for level in range(highest, lowest_odd - 1, -1):
        i = 0
        while i < len(order):
            if cluster_levels[order[i]] >= level:
                j = i
                while j < len(order) and cluster_levels[order[j]] >= level:
                    j += 1
                order[i:j] = order[i:j][::-1]
                i = j
            else:
                i += 1
    return [index for cluster_index in order for index in clusters[cluster_index]]


def visual_line(line: str, rtl: bool | None = None) -> tuple[str, list[int]]:
    """A line in display order, with its brackets mirrored in right-to-left runs (rule L4), and for each of its
    characters, its index in the line. The formatting characters (embeddings, isolates, marks) are not displayed."""
    if not needs_reordering(line):
        return line, list(range(len(line)))
    line_levels: list[int | None] = levels(line, rtl)
    order: list[int] = [i for i in reorder(line, rtl) if line[i] not in _INVISIBLE]
    chars: list[str] = [_MIRRORS.get(line[i], line[i]) if (line_levels[i] or 0) % 2 else line[i] for i in order]
    return "".join(chars), order


def visual(text: str) -> str:
    """A text, shaped, with each of its lines in display order. Unchanged without right-to-left characters."""
    if not needs_reordering(text):
        return text
    shaped, _ = shape(text)
    lines: list[str] = []
    for paragraph in _split_lines(shaped):
        lines.append(visual_line(paragraph)[0])
    return "".join(_join_lines(shaped, lines))


_LINE_BREAKS: str = "\n\u2028\u2029"


def _split_lines(text: str) -> list[str]:
    lines: list[str] = [""]
    for c in text:
        if c in _LINE_BREAKS:
            lines.append("")
        else:
            lines[-1] += c
    return lines


def _join_lines(text: str, lines: list[str]) -> list[str]:
    breaks: list[str] = [c for c in text if c in _LINE_BREAKS]
    out: list[str] = []
    for i, line in enumerate(lines):
        out.append(line)
        if i < len(breaks):
            out.append(breaks[i])
    return out

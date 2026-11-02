# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Translation files, without the gettext tools (run from the root directory of OpenMATB).

    python locales/build.py pot        Extract the messages of the code into locales/openmatb.pot
    python locales/build.py update     Add the new messages of openmatb.pot to each openmatb.po (untranslated)
    python locales/build.py mo         Compile each openmatb.po into openmatb.mo

The messages are those of the code, _("..."), and the texts of the start page of the web version (web/texts.json,
written in each language by web/build.py). The .po files can also be edited with Poedit, or online with Weblate (see
locales/README.md). After a change of the code: pot, update, translate, mo (.github/workflows/translations.yml runs
them after each push). update keeps the fuzzy translations (to review); mo leaves them out, as msgfmt does. pot keeps
the file unchanged when its messages are, so that only real changes are committed.
"""

from __future__ import annotations

import ast
import datetime
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]
LOCALES: Path = ROOT / "locales"
POT: Path = LOCALES / "openmatb.pot"
# The texts of the start page of the web version, in English (key: text): web/build.py writes them in each language
WEB_TEXTS: Path = ROOT / "web" / "texts.json"

# Messages translated through a variable, _(name), so not found by the extraction
DYNAMIC_MESSAGES: dict[str, str] = {
    "Lab streaming layer": "plugins/scheduling.py:44",  # Plugin titles, _(displayedplugins[i])
    "Instructions": "plugins/scheduling.py:44",
    "Generic scales": "plugins/scheduling.py:44",
    "Space": "core/modaldialog.py:70",  # Keys, _(continue_key.capitalize())
    "Escape": "core/modaldialog.py:63",
    "AUTO": "plugins/abstractplugin.py:287",  # _(agent.get_automode_string())
}


def extract() -> dict[str, list[str]]:
    """The messages of the code, _("..."), then the texts of the web start page, with their locations (file:line),
    in order of appearance."""
    listed: str = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True).stdout
    files: list[str] = [f for f in listed.split() if not f.startswith(("tests/", "locales/"))]
    messages: dict[str, list[str]] = {}
    for file in files:
        tree: ast.AST = ast.parse((ROOT / file).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                messages.setdefault(node.args[0].value, []).append(f"{file}:{node.lineno}")
    for message, location in DYNAMIC_MESSAGES.items():
        messages.setdefault(message, [location])
    lines: list[str] = WEB_TEXTS.read_text(encoding="utf-8").splitlines()
    for key, text in web_texts().items():
        line: int = next(n for n, content in enumerate(lines, 1) if content.strip().startswith(f'"{key}":'))
        messages.setdefault(text, []).append(f"web/texts.json:{line}")
    return messages


def web_texts() -> dict[str, str]:
    """The texts of the start page of the web version (key: English text), in their order."""
    return json.loads(WEB_TEXTS.read_text(encoding="utf-8"))


def read_po(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """The header of a .po file (its fields), and its translations (msgid: msgstr). Fuzzy entries are ignored, as
    msgfmt does."""
    return _read_po(path, fuzzy_entries=False)


def read_fuzzy(path: Path) -> dict[str, str]:
    """The fuzzy entries of a .po file (msgid: msgstr): translations to review (e.g. marked "Needs editing" in
    Weblate). They are not compiled, but update keeps them."""
    return _read_po(path, fuzzy_entries=True)[1]


def _read_po(path: Path, fuzzy_entries: bool) -> tuple[dict[str, str], dict[str, str]]:
    entries: dict[str, str] = {}
    # Entries are separated by blank lines: comments ("#," gives the flags), msgid, msgstr and their continuations
    for block in path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").split("\n\n"):
        fields: dict[str, str] = {}
        field: str = ""
        fuzzy: bool = False
        for line in block.strip().splitlines():
            line = line.strip()
            if line.startswith("#,"):
                fuzzy = fuzzy or "fuzzy" in line
            elif line.startswith(("msgid ", "msgstr ")):
                field, _, value = line.partition(" ")
                fields[field] = ast.literal_eval(value)
            elif line.startswith('"') and field:
                fields[field] += ast.literal_eval(line)
        if "msgid" not in fields:  # Comments only, or an obsolete entry (#~ msgid ...)
            continue
        if fields["msgid"] == "" or fuzzy == fuzzy_entries:  # The header is read with both
            entries[fields["msgid"]] = fields.get("msgstr", "")

    header: dict[str, str] = {}
    for header_line in entries.pop("", "").splitlines():
        name, _, value = header_line.partition(":")
        header[name.strip()] = value.strip()
    return header, entries


# The placeholders of a message, as xgettext finds them: Weblate (and msgfmt -c) then checks that the translation keeps
# them. The messages are formatted with %, or with str.format for {error}
PYTHON_FORMAT: re.Pattern[str] = re.compile(r"%(?:\(\w+\))?[#0 +-]*(?:\d+|\*)?(?:\.\d+)?[diouxXeEfFgGcrsa]")
PYTHON_BRACE_FORMAT: re.Pattern[str] = re.compile(r"\{\w*(?:![rsa])?(?::[^{}]*)?\}")


def flags(msgid: str) -> list[str]:
    """The format flags of a message (python-format, python-brace-format), written on the "#," line."""
    found: list[str] = []
    if PYTHON_FORMAT.search(msgid.replace("%%", "")):
        found.append("python-format")
    if PYTHON_BRACE_FORMAT.search(msgid):
        found.append("python-brace-format")
    return found


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t").replace("\n", "\\n") + '"'


def write_po(
    path: Path,
    header: dict[str, str],
    messages: dict[str, list[str]],
    translations: dict[str, str],
    fuzzy: dict[str, str] | None = None,
) -> None:
    """Write a .po file: the messages in order, with their format flags, and their translation, or their fuzzy
    translation (to review)."""
    fuzzy = fuzzy or {}
    lines: list[str] = ["# OpenMATB translations (see locales/build.py).", "#", 'msgid ""', 'msgstr ""']
    lines += [_quote(f"{name}: {value}\n") for name, value in header.items()]
    for msgid, locations in messages.items():
        is_fuzzy: bool = not translations.get(msgid) and bool(fuzzy.get(msgid))
        lines += ["", "#: " + " ".join(locations)]
        entry_flags: list[str] = (["fuzzy"] if is_fuzzy else []) + flags(msgid)
        if entry_flags:
            lines.append("#, " + ", ".join(entry_flags))
        lines += [
            "msgid " + _quote(msgid),
            "msgstr " + _quote(fuzzy[msgid] if is_fuzzy else translations.get(msgid, "")),
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_mo(path: Path, header: dict[str, str], translations: dict[str, str]) -> None:
    """The GNU .mo format, as msgfmt writes it (untranslated messages are left out)."""
    catalog: dict[str, str] = {k: v for k, v in translations.items() if v}
    catalog[""] = "".join(f"{name}: {value}\n" for name, value in header.items())
    keys: list[str] = sorted(catalog)
    ids: bytes = b""
    strs: bytes = b""
    offsets: list[tuple[int, int, int, int]] = []
    for key in keys:
        k, v = key.encode("utf-8"), catalog[key].encode("utf-8")
        offsets.append((len(ids), len(k), len(strs), len(v)))
        ids += k + b"\0"
        strs += v + b"\0"
    key_start: int = 7 * 4 + 16 * len(keys)
    value_start: int = key_start + len(ids)
    table: list[int] = []
    for id_offset, id_length, _, _ in offsets:
        table += [id_length, id_offset + key_start]
    for _, _, str_offset, str_length in offsets:
        table += [str_length, str_offset + value_start]
    head: bytes = struct.pack("<7I", 0x950412DE, 0, len(keys), 7 * 4, 7 * 4 + len(keys) * 8, 0, 0)
    path.write_bytes(head + struct.pack(f"<{len(table)}I", *table) + ids + strs)


def po_files() -> list[Path]:
    return sorted(LOCALES.glob("*/LC_MESSAGES/openmatb.po"))


def main(command: str) -> None:
    now: str = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M%z")
    if command == "pot":
        messages: dict[str, list[str]] = extract()
        previous: str | None = POT.read_text(encoding="utf-8") if POT.exists() else None
        header: dict[str, str] = {
            "Project-Id-Version": "OpenMATB",
            "POT-Creation-Date": now,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
        }
        if previous is not None:
            # Same messages at the same places: the file is kept as it is (its date too), so that the automatic
            # update (.github/workflows/translations.yml) commits only real changes
            header["POT-Creation-Date"] = read_po(POT)[0].get("POT-Creation-Date", now)
            write_po(POT, header, messages, {})
            if POT.read_text(encoding="utf-8") != previous:
                header["POT-Creation-Date"] = now
                write_po(POT, header, messages, {})
        else:
            write_po(POT, header, messages, {})
        print(f"{POT.relative_to(ROOT)}: {len(messages)} messages")
    elif command == "update":
        pot_messages: dict[str, list[str]] = extract()
        for path in po_files():
            header, translations = read_po(path)
            fuzzy: dict[str, str] = read_fuzzy(path)
            missing: list[str] = [m for m in pot_messages if not translations.get(m)]
            write_po(path, header, pot_messages, translations, fuzzy)
            print(f"{path.relative_to(ROOT)}: {len(missing)} messages to translate")
    elif command == "mo":
        for path in po_files():
            header, translations = read_po(path)
            write_mo(path.with_suffix(".mo"), header, translations)
            print(f"{path.with_suffix('.mo').relative_to(ROOT)}: {sum(1 for v in translations.values() if v)} messages")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")

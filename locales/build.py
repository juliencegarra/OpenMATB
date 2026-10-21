# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Translation files, without the gettext tools (run from the root directory of OpenMATB).

    python locales/build.py pot        Extract the messages of the code into locales/openmatb.pot
    python locales/build.py update     Add the new messages of openmatb.pot to each openmatb.po (untranslated)
    python locales/build.py mo         Compile each openmatb.po into openmatb.mo

The .po files can also be edited with Poedit. After a change of the code: pot, update, translate, mo.
"""

from __future__ import annotations

import ast
import datetime
import struct
import subprocess
import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]
LOCALES: Path = ROOT / "locales"
POT: Path = LOCALES / "openmatb.pot"

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
    """The messages of the code, _("..."), with their locations (file:line), in order of appearance."""
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
    return messages


def read_po(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """The header of a .po file (its fields), and its translations (msgid: msgstr). Fuzzy entries are ignored, as
    msgfmt does."""
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
        if "msgid" in fields and (not fuzzy or fields["msgid"] == ""):
            entries[fields["msgid"]] = fields.get("msgstr", "")

    header: dict[str, str] = {}
    for header_line in entries.pop("", "").splitlines():
        name, _, value = header_line.partition(":")
        header[name.strip()] = value.strip()
    return header, entries


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t").replace("\n", "\\n") + '"'


def write_po(path: Path, header: dict[str, str], messages: dict[str, list[str]], translations: dict[str, str]) -> None:
    lines: list[str] = ["# OpenMATB translations (see locales/build.py).", "#", 'msgid ""', 'msgstr ""']
    lines += [_quote(f"{name}: {value}\n") for name, value in header.items()]
    for msgid, locations in messages.items():
        lines += [
            "",
            "#: " + " ".join(locations),
            "msgid " + _quote(msgid),
            "msgstr " + _quote(translations.get(msgid, "")),
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
        header: dict[str, str] = {
            "Project-Id-Version": "OpenMATB",
            "POT-Creation-Date": now,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
        }
        messages: dict[str, list[str]] = extract()
        write_po(POT, header, messages, {})
        print(f"{POT.relative_to(ROOT)}: {len(messages)} messages")
    elif command == "update":
        pot_messages: dict[str, list[str]] = extract()
        for path in po_files():
            header, translations = read_po(path)
            missing: list[str] = [m for m in pot_messages if m not in translations]
            write_po(path, header, pot_messages, translations)
            print(f"{path.relative_to(ROOT)}: {len(missing)} new messages to translate")
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

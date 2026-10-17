"""Tests for the language read from config.ini by main.py, before anything else is imported.

main.py starts OpenMATB when imported: its read_language_iso function is extracted from the source.
"""

import ast
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def read_language_iso():
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "read_language_iso"]
    assert len(functions) == 1, "main.py must define read_language_iso"
    namespace = {}
    exec("import configparser\n" + ast.unparse(functions[0]), namespace)
    return namespace["read_language_iso"]


def _config(tmp_path, text):
    path = tmp_path / "config.ini"
    path.write_text(text, encoding="utf-8")
    return str(path)


class TestReadLanguage:
    def test_language_of_the_config(self, read_language_iso, tmp_path):
        assert read_language_iso(_config(tmp_path, "[Openmatb]\nlanguage=fr_FR\n")) == "fr_FR"

    def test_missing_language_is_english(self, read_language_iso, tmp_path):
        """config.ini: "If language is missing, en_EN will be loaded" (it raised IndexError)."""
        assert read_language_iso(_config(tmp_path, "[Openmatb]\nscreen_index=0\n")) == "en_EN"

    def test_spaces_around_the_equal_sign(self, read_language_iso, tmp_path):
        assert read_language_iso(_config(tmp_path, "[Openmatb]\nlanguage = fr_FR\n")) == "fr_FR"

    def test_commented_language_is_ignored(self, read_language_iso, tmp_path):
        text = "[Openmatb]\n# Example: language=fr_FR\nlanguage=en_EN\n"
        assert read_language_iso(_config(tmp_path, text)) == "en_EN"

    def test_the_shipped_config_is_english(self, read_language_iso):
        assert read_language_iso("config.ini") == "en_EN"

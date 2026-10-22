"""A blocking plugin started again reads its file from its first page.

The replay stops a presentation before its end when it seeks past it: its pages left were shown
before the pages of the next presentation of the same plugin (e.g. instructions before each block).
"""

from unittest.mock import patch

from plugins.abstractplugin import AbstractPlugin
from plugins.instructions import Instructions


def test_pages_left_by_a_stopped_presentation_are_dropped(tmp_path):
    (tmp_path / "block2.txt").write_text("Block 2\n<newpage>\nGo\n", encoding="utf-8")
    plugin = object.__new__(Instructions)
    plugin.slides = ["Page 2 of block 1", "Page 3 of block 1"]
    plugin.folder = tmp_path
    plugin.input_path = None
    plugin.ignore_empty_lines = False
    plugin.parameters = {"filename": "block2.txt"}

    with patch.object(AbstractPlugin, "create_widgets"):
        plugin.create_widgets()

    assert plugin.slides == ["Block 2\n", "Go\n"]

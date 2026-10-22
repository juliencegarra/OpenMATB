"""A blocking plugin started again reads its file from its first page.

The replay stops a presentation before its end when it seeks past it: its pages left were shown
before the pages of the next presentation of the same plugin (e.g. instructions before each block).
"""

from unittest.mock import MagicMock, patch

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


def test_started_again_without_the_widgets_of_its_previous_run():
    """Only its background before its first page: its last page and sliders were shown during one frame."""
    plugin = object.__new__(Instructions)
    plugin.alias = "instructions"
    plugin.verbose = False
    plugin.visible = False
    plugin.parameters = {"taskplacement": "fullscreen"}
    plugin.update_can_receive_key = lambda: None
    background, old_page = MagicMock(), MagicMock()
    plugin.widgets = {"instructions_background": background, "instructions_slide": old_page}
    plugin.current_slide = None

    with patch("plugins.abstractplugin.Window"):
        plugin.show()

    background.show.assert_called_once()
    old_page.show.assert_not_called()
    assert plugin.is_visible() and len(plugin.widgets) == 2

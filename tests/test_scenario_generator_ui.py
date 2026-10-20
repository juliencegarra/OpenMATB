"""Tests for the scenario generator UI logic."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import mouse

from core import validation
from core.constants import PATHS as P
from scenario_generation import BlockConfig
from scenario_generator_ui import ScenarioGeneratorUI, UIAdvancedPanel, UIFileSelector


def _ui():
    ui = object.__new__(ScenarioGeneratorUI)
    ui.blocks = []
    ui._blocks_batch = MagicMock()
    ui._update_scroll = MagicMock()
    ui._inter_block_widgets = []
    return ui


class TestAddBlock:
    def test_config_advanced_parameters_are_kept(self):
        """Cloning a block or loading a preset keeps its advanced parameters."""
        ui = _ui()
        cfg = BlockConfig(
            duration_sec=120,
            plugins={"sysmon": 0.5},
            extra_events=[("sysmon", "alerttimeout", 5000), ("communications", "voiceidiom", "fr")],
        )
        ui._add_block(config=cfg)
        assert ui.blocks[0].get_block_config() == cfg

    def test_duplicated_block_has_the_same_config(self):
        ui = _ui()
        ui._add_block()
        ui.blocks[0].advanced_params = {"sysmon": {"alerttimeout": 5000}}
        ui._duplicate_block_at(0)
        assert ui.blocks[1].get_block_config() == ui.blocks[0].get_block_config()


class TestInterBlockEvents:
    def _offered_files(self, ui, insert):
        """The files offered by the file selector of an insert button."""
        with patch("scenario_generator_ui.UIFileSelector") as selector:
            insert(0)
        return selector.call_args.args[3]

    def test_instructions_file_is_relative_to_the_instructions_folder(self):
        """The instructions plugin reads its filename in includes/instructions: the path from the repository root
        (includes/instructions/default_en/...) was not found, and the generated scenario did not load."""
        ui = _ui()
        ui.WIN_W, ui.WIN_H, ui._overlay_batch = 800, 600, MagicMock()
        ui._add_inter_block_widget = MagicMock()
        ui._close_overlay = MagicMock()
        files = self._offered_files(ui, ui._insert_instructions_at)
        assert files and all(f.is_relative_to(P["INSTRUCTIONS"]) for f in files)
        ui._on_interblock_file_selected(P["INSTRUCTIONS"] / "default_en" / "welcome_screen.txt")
        filename = ui._add_inter_block_widget.call_args.args[2]
        assert filename == "default_en/welcome_screen.txt"
        assert validation.is_available_text_file(filename)[1] is None

    def test_questionnaires_are_offered_for_a_questionnaire(self):
        ui = _ui()
        ui.WIN_W, ui.WIN_H, ui._overlay_batch = 800, 600, MagicMock()
        files = self._offered_files(ui, ui._insert_questionnaire_at)
        assert files and all(f.is_relative_to(P["QUESTIONNAIRES"]) for f in files)

    def test_removed_block_moves_the_following_inter_block_events(self):
        """A questionnaire after the 3rd block is after the 2nd once the 2nd block is removed: its position
        was kept, and the generator left it out of the scenario."""
        ui = _ui()
        ui.blocks = [MagicMock(), MagicMock(), MagicMock()]
        ui.scroll_offset = 0
        before, after = MagicMock(position=1), MagicMock(position=3)
        ui._inter_block_widgets = [before, after]
        ui._remove_block_at(1)
        assert (before.position, after.position) == (1, 2)

    def test_duplicated_block_moves_the_following_inter_block_events(self):
        """The copy is inserted after its block: the inter-block events of the following blocks stay with them."""
        ui = _ui()
        ui._add_block()
        ui._add_block()
        start, between, end = MagicMock(position=0), MagicMock(position=1), MagicMock(position=2)
        ui._inter_block_widgets = [start, between, end]
        ui._duplicate_block_at(0)
        assert (start.position, between.position, end.position) == (0, 1, 3)


class TestAdvancedParameters:
    def test_communications_voices_exist(self):
        """The voice language and gender of the advanced settings are those of includes/sounds: en and fr failed
        the validation (english, french), and the default english female voice does not exist."""
        params = {p[0]: p[3] for p in UIAdvancedPanel.PLUGIN_PARAMS["communications"]}
        idioms, genders = params["voiceidiom"]["options"], params["voicegender"]["options"]
        for idiom in idioms:
            assert validation.is_in_list(idiom, [p.name.lower() for p in P["SOUNDS"].iterdir()])[1] is None
        assert (P["SOUNDS"] / params["voiceidiom"]["default"] / params["voicegender"]["default"]).is_dir()
        assert all(g in ("female", "male") for g in genders)


class TestOldPresetFilenames:
    """The presets saved before held the inter-block file path from the repository root."""

    def test_windows_path_from_root_is_made_relative_to_the_plugin_folder(self):
        ui = _ui()
        name = ui._preset_filename("instructions", r"includes\instructions\default_en\welcome_screen.txt")
        assert name == "default_en/welcome_screen.txt"

    def test_posix_path_from_root_is_made_relative_to_the_plugin_folder(self):
        ui = _ui()
        assert ui._preset_filename("genericscales", "includes/questionnaires/nasatlx_en.txt") == "nasatlx_en.txt"

    def test_current_filename_is_kept(self):
        ui = _ui()
        assert ui._preset_filename("genericscales", "nasatlx_en.txt") == "nasatlx_en.txt"
        assert ui._preset_filename("instructions", "default_en/track.txt") == "default_en/track.txt"


class TestAdvancedPanelDefaults:
    # (communications: only the voices, whose defaults depend on the language)
    @pytest.mark.parametrize("plugin_name", ["sysmon", "resman", "track"])
    def test_untouched_panel_gives_the_plugin_defaults(self, plugin_name, mock_logger):
        """Apply without changing a value wrote the panel default: the track joystick force became 5 (not 1) and
        the cursor red (as when outside the target)."""
        import plugins

        plugin = getattr(plugins, plugin_name.capitalize())()
        panel = UIAdvancedPanel(1000, 700, MagicMock(), plugin_name, {}, on_save=MagicMock(), on_cancel=MagicMock())
        for name, value in panel._get_params().items():
            if isinstance(value, str) and value.startswith("#"):  # A color, given as in a scenario
                value = validation.is_color(value)[0]
            assert value == plugin.parameters[name], name


class TestFileSelectorClick:
    def test_click_on_a_file_name_selects_its_row(self):
        files = [Path(f"f{i}.txt") for i in range(5)]
        selector = UIFileSelector(1000, 700, MagicMock(), files, "t", on_select=MagicMock(), on_cancel=MagicMock())
        baseline = selector._list_top - 1 * selector._row_height  # The second label
        for y in (baseline - 4, baseline + 6, baseline + 18):  # Its highlight band, text included
            selector._last_click_index = -1
            selector.on_mouse_press(selector.panel_x + 50, y, mouse.LEFT, 0)
            assert selector._selected_index == 1, y

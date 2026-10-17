"""Tests for the scenario generator UI logic."""

from unittest.mock import MagicMock

from scenario_generation import BlockConfig
from scenario_generator_ui import ScenarioGeneratorUI


def _ui():
    ui = object.__new__(ScenarioGeneratorUI)
    ui.blocks = []
    ui._blocks_batch = MagicMock()
    ui._update_scroll = MagicMock()
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

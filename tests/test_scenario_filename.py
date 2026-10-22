"""Scenario: a filename (instructions, questionnaire) may contain a space.

check_events removes the spaces of every parameter value not validated by is_string: "my file.txt"
became "myfile.txt", and the scenario was refused (file not found).
"""

from types import SimpleNamespace
from unittest.mock import patch

import core.constants
from core import validation
from core.scenario import Scenario


class _Instructions:
    blocking = True
    folder = None

    def __init__(self):
        self.parameters = {"title": None, "taskplacement": "fullscreen", "taskupdatetime": 15, "filename": None}
        self.validation_dict = {"filename": (validation.is_available_text_file, str(self.folder))}
        self.widgets = {}

    def start(self):
        pass

    def stop(self):
        pass


def test_filename_with_a_space_is_accepted(tmp_path, mock_errors, mock_logger):
    _Instructions.folder = tmp_path
    (tmp_path / "my file.txt").write_text("hello", encoding="utf-8")
    scenario_path = tmp_path / "scenario.txt"
    scenario_path.write_text(
        "0:00:00;instructions;filename;my file.txt\n0:00:00;instructions;start\n", encoding="utf-8"
    )
    errors_path = tmp_path / "errors.log"
    with (
        patch("core.scenario.plugins", SimpleNamespace(Instructions=_Instructions)),
        patch.dict(core.constants.PATHS, {"SCENARIO_ERRORS": errors_path}),
    ):
        Scenario(scenario_path=scenario_path)

    errors = errors_path.read_text(encoding="utf-8")
    assert "No error" in errors, errors

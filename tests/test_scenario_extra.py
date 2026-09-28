"""Extra tests for core.scenario - loading real scenario files end to end.

The plugins package is replaced by light fake plugins so that Scenario.__init__
runs fully (file reading, plugin loading, validation, error file) without a
window. Scenario files are real text files written in tmp_path.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import core.constants
from core import validation
from core.scenario import Scenario


class _FakePlugin:
    """Minimal plugin: parameters, blocking flag, start/stop methods, widgets."""

    blocking = False
    instances = 0

    def __init__(self):
        type(self).instances += 1
        self.parameters = {"title": "Fake", "taskplacement": "fullscreen", "taskupdatetime": 50, "sub": {"level": 1}}
        self.validation_dict = {"sub-level": validation.is_natural_integer}
        self.widgets = {}

    def start(self):
        pass

    def stop(self):
        pass


class Sysmon(_FakePlugin):
    pass


class Track(_FakePlugin):
    pass


class Instructions(_FakePlugin):
    blocking = True

    def __init__(self):
        super().__init__()
        self.parameters["filename"] = None
        self.validation_dict = {"filename": validation.is_string}


@pytest.fixture()
def fake_plugins():
    """Replace the plugins package seen by core.scenario with fake plugins."""
    ns = SimpleNamespace(Sysmon=Sysmon, Track=Track, Instructions=Instructions)
    with patch("core.scenario.plugins", ns):
        yield ns


@pytest.fixture()
def errors(mock_errors):
    """mock_errors whose some_fatals flag follows fatal add_error() calls."""

    def add_error(msg, fatal=False):
        mock_errors.errors_list.append(msg)
        if fatal:
            mock_errors.some_fatals = True

    mock_errors.add_error.side_effect = add_error
    return mock_errors


@pytest.fixture()
def error_file(tmp_path):
    """Redirect the scenario error report to tmp_path."""
    path = tmp_path / "last_scenario_errors.log"
    with patch.dict(core.constants.PATHS, {"SCENARIO_ERRORS": path}):
        yield path


def _write(tmp_path, text, name="scenario.txt", encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return path


VALID = """# A comment line
0:00:00;sysmon;title;My monitoring

0:00:00;sysmon;start
0:00:00;track;start
0:00:00;system;mousecontrol;True
0:01:00;sysmon;stop
0:01:00;track;stop
"""


# ──── Loading files ────


class TestLoadScenarioFile:
    def test_valid_file(self, tmp_path, fake_plugins, errors, error_file, mock_logger):
        """A valid file is parsed, plugins loaded and 'No error' is reported."""
        path = _write(tmp_path, VALID)
        s = Scenario(scenario_path=path)

        assert len(s.events) == 6
        assert set(s.plugins) == {"sysmon", "track"}
        assert isinstance(s.plugins["sysmon"], Sysmon)
        assert error_file.read_text(encoding="utf-8").strip() == "No error"
        assert errors.errors_list == []
        mock_logger.log_manual_entry.assert_called_once_with(path, key="scenario_path")

    def test_comments_and_blank_lines_skipped(self, tmp_path, fake_plugins, errors, error_file, mock_logger):
        """Comment and blank lines do not become events, line numbers are kept."""
        s = Scenario(scenario_path=_write(tmp_path, VALID))
        assert [e.line for e in s.events] == [1, 3, 4, 5, 6, 7]

    def test_default_path_from_config(self, tmp_path, fake_plugins, errors, error_file, mock_logger):
        """Without explicit path, the file comes from config.ini in the SCENARIOS folder."""
        _write(tmp_path, VALID, name="conf.txt")
        with (
            patch.dict(core.constants.PATHS, {"SCENARIOS": tmp_path}),
            patch("core.scenario.get_conf_value", return_value="conf.txt") as conf,
        ):
            s = Scenario()
        conf.assert_called_once_with("Openmatb", "scenario_path")
        assert len(s.events) == 6

    def test_missing_file_is_fatal(self, tmp_path, fake_plugins, errors, error_file, mock_logger):
        """A missing scenario file is reported as a fatal error naming the file."""
        s = Scenario(scenario_path=tmp_path / "nope.txt")
        assert s.events == [] and s.plugins == {}
        assert "nope.txt" in errors.errors_list[0]
        assert errors.some_fatals
        assert not error_file.exists()
        mock_logger.log_manual_entry.assert_not_called()

    def test_contents_take_precedence_over_path(self, tmp_path, fake_plugins, errors, error_file, mock_logger):
        """Given contents (replay) are used even if a path is provided."""
        s = Scenario(["0:00:00;sysmon;start\n", "0:00:05;sysmon;stop\n"], scenario_path=tmp_path / "nope.txt")
        assert len(s.events) == 2
        mock_logger.log_manual_entry.assert_not_called()

    def test_utf8_bom_file(self, tmp_path, fake_plugins, errors, error_file, mock_logger):
        """A scenario file with a UTF-8 BOM is read like the same file without BOM."""
        path = _write(tmp_path, VALID, encoding="utf-8-sig")
        s = Scenario(scenario_path=path)
        assert len(s.events) == 6


# ──── Errors reported to the user ────


class TestScenarioErrors:
    def test_unknown_plugin_stops_before_loading(self, fake_plugins, errors, error_file, mock_logger):
        """An unknown plugin name is fatal and no plugin is instantiated."""
        Sysmon.instances = 0
        s = Scenario(["0:00:00;sysmon;start\n", "0:00:00;sysmonn;start\n"])
        assert s.plugins == {}
        assert "sysmonn" in errors.errors_list[0]
        assert "(l. 1)" in errors.errors_list[0]
        assert Sysmon.instances == 0
        assert not error_file.exists()

    def test_invalid_events_written_to_error_file(self, fake_plugins, errors, error_file, mock_logger):
        """Validation errors are listed in the error file and a fatal error points to it."""
        contents = [
            "0:00:00;sysmon;start\n",
            "0:00:00;sysmon;taskupdatetime;-5\n",
            "0:00:00;sysmon;unknownparam;3\n",
            "0:00:00;system;mousecontrol\n",
            "0:00:10;track;start\n",
        ]
        Scenario(contents)
        report = error_file.read_text(encoding="utf-8")
        assert "line 1. taskupdatetime" in report
        assert "does not have a unknownparam parameter" in report
        assert "mousecontrol command requires True/False argument" in report
        assert "(sysmon) plugin does not have a stop command" in report
        assert "(track) plugin does not have a stop command" in report
        assert error_file.name in errors.errors_list[-1]
        assert errors.some_fatals

    def test_nested_parameter_with_plugin_validation(self, fake_plugins, errors, error_file, mock_logger):
        """A nested parameter is validated by the plugin validation dict and evaluated."""
        s = Scenario(["0:00:00;sysmon;start\n", "0:00:00;sysmon;sub-level;3\n", "0:00:01;sysmon;stop\n"])
        assert s.events[1].command == ["sub-level", 3]
        assert errors.errors_list == []

    def test_deprecated_events_are_warned_and_dropped(self, fake_plugins, errors, error_file, mock_logger):
        """Deprecated commands raise a non-fatal warning and are not kept."""
        s = Scenario(["0:00:00;sysmon;start\n", "0:00:00;sysmon;end\n", "0:00:01;sysmon;stop\n"])
        assert [e.command for e in s.events] == [["start"], ["stop"]]
        assert "deprecated" in errors.errors_list[0]
        assert not errors.some_fatals

    def test_blocking_plugin_needs_filename(self, fake_plugins, errors, error_file, mock_logger):
        """A blocking plugin started without filename is reported; with it, it is valid."""
        Scenario(["0:00:00;instructions;start\n"])
        assert "without a preceding filename" in error_file.read_text(encoding="utf-8")

        errors.errors_list.clear()
        errors.some_fatals = False
        Scenario(["0:00:00;instructions;filename;a.txt\n", "0:00:00;instructions;start\n"])
        assert error_file.read_text(encoding="utf-8").strip() == "No error"

    def test_replay_mode_does_not_require_stop(self, fake_plugins, errors, error_file, mock_logger):
        """In replay mode a session exited early (no stop) is not an error."""
        with patch("core.scenario.REPLAY_MODE", True):
            Scenario(["0:00:00;sysmon;start\n"])
        assert error_file.read_text(encoding="utf-8").strip() == "No error"

    def test_malformed_line_is_reported(self, fake_plugins, errors, error_file, mock_logger):
        """A malformed line is reported to the user instead of crashing."""
        try:
            Scenario(["0:00:00;sysmon;start\n", "0:00:10 sysmon stop\n"])
        except ValueError:
            raise AssertionError("ValueError escaped from Scenario()") from None
        assert errors.some_fatals


# ──── Plugin reload ────


class TestReloadPlugins:
    def test_reload_creates_fresh_instances(self, fake_plugins, errors, error_file, mock_logger):
        """reload_plugins empties widget batches and instantiates new plugins."""
        s = Scenario(["0:00:00;sysmon;start\n", "0:00:01;sysmon;stop\n"])
        old = s.plugins["sysmon"]
        widget = MagicMock()
        old.widgets = {"w": widget}
        fake_plugins.sysmon = "module attribute"

        s.reload_plugins()

        widget.empty_batch.assert_called_once()
        assert old.widgets == {}
        assert s.plugins["sysmon"] is not old
        assert isinstance(s.plugins["sysmon"], Sysmon)
        assert not hasattr(fake_plugins, "sysmon")

    def test_reload_without_module_attribute(self, fake_plugins, errors, error_file, mock_logger):
        """reload_plugins works when the plugins package has no lowercase attribute."""
        s = Scenario(["0:00:00;track;start\n", "0:00:01;track;stop\n"])
        old = s.plugins["track"]
        s.reload_plugins()
        assert s.plugins["track"] is not old

"""Replay of a session in the browser (Pyodide), without a browser.

In the browser, the session to replay is given in the page address (?mode=replay&session=12) and looked up
in the browser storage (IndexedDB): sessions run in this browser (one folder per day) and sessions imported
from the start page (sessions/imported). Web session files have extra rows (browser, os, useragent, freeze,
visibility) that the replay must ignore. The complete replay is tested in a browser by tests/web.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

from core.logreader import LogReader

logreader_module = importlib.import_module("core.logreader")
utils_module = importlib.import_module("core.utils")

HEADER = "logtime,scenario_time,type,module,address,value\n"

# A session run in the browser, as written by core.logger (shortened)
WEB_SESSION = HEADER + (
    "1000.0,0,version,,,1.4.5\n"
    "1000.0,0,browser,,,Firefox 156.0\n"
    "1000.0,0,os,,,Windows\n"
    '1000.0,0,useragent,,,"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:156.0) Gecko/20100101 Firefox/156.0"\n'
    "1000.01,0,event,sysmon,self,start\n"
    "1000.02,0,event,resman,self,start\n"
    "1003.0,2.99,input,keyboard,F1,press\n"
    "1003.1,3.09,input,keyboard,F1,release\n"
    "1004.5,4.49,freeze,,,312\n"
    "1005.0,4.99,visibility,,,hidden\n"
    "1006.0,5.0,input,keyboard,NUM_1,press\n"
    "1006.1,5.1,input,keyboard,NUM_1,release\n"
    "1010.0,9.0,event,sysmon,self,stop\n"
    "1010.01,9.0,event,resman,self,stop\n"
)


def _write(path: Path, content: str = WEB_SESSION) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))
    return path


@pytest.fixture
def web_sessions(tmp_path, mock_errors):
    """The sessions folder of the browser storage (/data/openmatb/sessions)."""
    with patch.dict(logreader_module.P, {"SESSIONS": tmp_path}):
        yield tmp_path


class TestSessionIdFromThePage:
    def test_session_given_in_the_page_address(self):
        with patch.object(utils_module, "url_params", return_value={"mode": "replay", "session": "12"}):
            assert utils_module.get_replay_session_id() == 12

    def test_page_address_has_priority_over_the_config(self):
        with (
            patch.object(utils_module, "url_params", return_value={"session": "7"}),
            patch.object(utils_module, "has_conf_value", return_value=True),
            patch.object(utils_module, "get_conf_value", return_value="3"),
        ):
            assert utils_module.get_replay_session_id() == 7

    def test_without_session_in_the_address_the_last_session_is_replayed(self):
        with (
            patch.object(utils_module, "url_params", return_value={"mode": "replay"}),
            patch.object(utils_module, "has_conf_value", return_value=False),
            patch.object(utils_module, "find_the_last_session_number", return_value=4),
            patch.object(utils_module.sys, "argv", ["main.py"]),
        ):
            assert utils_module.get_replay_session_id() == 4


class TestSessionLookupInTheBrowserStorage:
    def test_session_run_in_this_browser(self, web_sessions):
        path = _write(web_sessions / "2026-09-26" / "12_260926_101500.csv")
        assert LogReader(12).session_file_path == path

    def test_session_imported_from_the_start_page(self, web_sessions):
        path = _write(web_sessions / "imported" / "12_260901_090000.csv")
        assert LogReader(12).session_file_path == path

    def test_other_session_ids_are_not_confused(self, web_sessions):
        _write(web_sessions / "2026-09-26" / "112_260926_101500.csv")
        path = _write(web_sessions / "2026-09-26" / "12_260926_111500.csv")
        assert LogReader(12).session_file_path == path

    def test_missing_session(self, web_sessions, mock_errors):
        LogReader(99)
        mock_errors.add_error.assert_called_once()
        assert mock_errors.add_error.call_args.kwargs["fatal"] is True

    def test_imported_copy_of_a_session_of_this_browser_is_ambiguous(self, web_sessions, mock_errors):
        """Importing a session file that was run in this browser gives two files with the same ID."""
        _write(web_sessions / "2026-09-26" / "12_260926_101500.csv")
        _write(web_sessions / "imported" / "12_260926_101500.csv")
        LogReader(12)
        assert "Multiple session files" in mock_errors.add_error.call_args.args[0]


class TestWebSessionFile:
    @pytest.fixture
    def reader(self, web_sessions):
        _write(web_sessions / "2026-09-26" / "12_260926_101500.csv")
        return LogReader(12)

    def test_events_are_replayed(self, reader):
        assert [line.split(";", 1)[1] for line in reader.contents] == [
            "sysmon;start",
            "resman;start",
            "sysmon;stop",
            "resman;stop",
        ]

    def test_keyboard_inputs_are_replayed(self, reader):
        assert [(i["address"], i["value"]) for i in reader.keyboard_inputs] == [
            ("F1", "press"),
            ("F1", "release"),
            ("NUM_1", "press"),
            ("NUM_1", "release"),
        ]

    def test_web_rows_are_ignored(self, reader):
        """browser, os, useragent, freeze and visibility rows are not events nor inputs."""
        assert len(reader.contents) == 4
        assert len(reader.inputs) == 4
        assert reader.states == []

    def test_session_duration(self, reader):
        assert reader.session_duration == pytest.approx(10.01)
        assert reader.replay_session_id == 12

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


# ── Page events of a browser session: hidden page, pauses of the page, browser ──

# Page hidden at 4 s (scenario time frozen at 3.99), visible again at 8 s, pause dialog closed at 9.4 s
PAUSED_SESSION = HEADER + (
    "1000.0,0,version,,,1.4.5\n"
    "1000.0,0,browser,,,Chrome 153.0.0.0\n"
    "1000.0,0,os,,,Windows\n"
    "1000.01,0,event,sysmon,self,start\n"
    "1002.5,2.49,freeze,,,300\n"
    "1004.0,3.99,visibility,,,hidden\n"
    "1006.0,3.99,state,sysmon,x,1\n"
    "1008.0,3.99,visibility,,,visible\n"
    "1009.4,3.99,state,sysmon,x,2\n"
    "1009.5,4.1,state,sysmon,x,3\n"
    "1015.0,9.6,event,sysmon,self,stop\n"
)


class TestPageEvents:
    @pytest.fixture
    def reader(self, web_sessions):
        _write(web_sessions / "2026-09-26" / "12_260926_101500.csv", PAUSED_SESSION)
        return LogReader(12)

    def test_browser_and_system(self, reader):
        assert reader.environment == {"browser": "Chrome 153.0.0.0", "os": "Windows"}

    def test_hidden_page_until_the_scenario_resumes(self, reader):
        """Hidden from 4 s to 8 s, then the scenario stays paused until the pause dialog is closed (9.4 s)."""
        ((hidden, visible, resumed),) = reader.hidden_periods
        assert (hidden, visible, resumed) == pytest.approx((4.0, 8.0, 9.4))

    def test_freeze_starts_when_the_page_stopped(self, reader):
        """A freeze row is written when the page runs again: its period ends at the row."""
        ((start, duration),) = reader.freezes
        assert (start, duration) == pytest.approx((2.2, 0.3))

    def test_page_still_hidden_at_the_end(self, web_sessions):
        content = PAUSED_SESSION.replace("1008.0,3.99,visibility,,,visible\n", "")
        _write(web_sessions / "2026-09-26" / "12_260926_101500.csv", content)
        ((_hidden, visible, _resumed),) = LogReader(12).hidden_periods
        assert visible == pytest.approx(15.0)  # Session end

    def test_desktop_session_has_no_page_event(self, web_sessions):
        desktop = (
            HEADER + "1000.0,0,version,,,1.4.5\n1000.01,0,event,sysmon,self,start\n1005,5,event,sysmon,self,stop\n"
        )
        _write(web_sessions / "2026-09-26" / "3_260926_101500.csv", desktop)
        reader = LogReader(3)
        assert (reader.environment, reader.hidden_periods, reader.freezes) == ({}, [], [])


class TestReplayPageNotice:
    def _replay(self, hidden_periods):
        from unittest.mock import MagicMock

        from core.replayscheduler import ReplayScheduler

        rs = object.__new__(ReplayScheduler)
        rs.logreader = MagicMock(hidden_periods=hidden_periods)
        return rs

    @pytest.mark.parametrize(
        "replay_time,notice",
        [
            (3.9, None),
            (4.0, "Page hidden"),
            (7.9, "Page hidden"),
            (8.0, "Session paused"),
            (9.3, "Session paused"),
            (9.4, None),
        ],
    )
    def test_notice_over_the_tasks(self, replay_time, notice):
        text = self._replay([(4.0, 8.0, 9.4)]).page_notice_at(replay_time)
        assert text == notice if notice is None else text.startswith(notice)

    def test_timeline_marks(self):
        """One mark per hidden period (until the scenario resumed) and per freeze, at their replay times."""
        from unittest.mock import MagicMock

        from core.container import Container

        rs = self._replay([(4.0, 8.0, 9.0)])
        rs.logreader.freezes = [(2.0, 0.3)]
        rs.logreader.session_duration = 20.0
        rs.slider = MagicMock(draw_order=1, rank=1, containers={"allgroove": Container("groove", 100, 10, 200, 4)})
        with patch("core.replayscheduler.Window"):
            marks = rs.create_timeline_marks()
        hidden, freeze = marks
        assert (hidden.x, hidden.width) == pytest.approx((140, 50))  # 4 s to 9 s of 20 s over 200 px
        assert (freeze.x, freeze.width) == pytest.approx((120, 3))

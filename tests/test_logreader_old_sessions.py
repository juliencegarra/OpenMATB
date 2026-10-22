"""LogReader on sessions written by older versions (1.4.x).

- The foreground visibility was logged as 1/0 (True/False since 1.5): every task stayed "not visible"
  for the whole session, and the performance strip was all grey, without any plot.
- The sessions were written in the Windows encoding (cp1252) before the logger wrote UTF-8: a
  non-ASCII character (e.g. "Temps passé") made the replay crash with a UnicodeDecodeError.
"""

from core.logreader import LogReader
from tests.test_logreader_extra import HEADER, _reader


def _visibility_rows(visible, hidden):
    return [
        (100.0, 0.0, "event", "track", "self", "start"),
        (100.0, 0.0, "state", "track", "foreground, visibility", hidden),
        (100.0, 0.0, "state", "track", "foreground, visibility", visible),
        (110.0, 10.0, "performance", "track", "center_deviation", "5.0"),
        (120.0, 20.0, "event", "track", "self", "stop"),
    ]


def test_task_visible_in_a_1_5_session(tmp_path):
    lr = _reader(tmp_path, _visibility_rows(visible="False", hidden="True"))
    assert lr.task_hidden_periods["track"] == [(0.0, 0.0)]


def test_task_visible_in_a_1_4_session(tmp_path):
    lr = _reader(tmp_path, _visibility_rows(visible="0", hidden="1"))
    # Not hidden from 0 to the end of the session (20 s)
    assert lr.task_hidden_periods["track"] == [(0.0, 0.0)]


def test_session_in_the_windows_encoding_is_read(tmp_path):
    path = tmp_path / "12_260101_120000.csv"
    rows = [
        HEADER,
        "100.0,0.0,event,track,self,start",
        '101.0,1.0,state,scheduling,"chrono_label, text",Temps passé',
        "120.0,20.0,event,track,self,stop",
    ]
    path.write_bytes(("\n".join(rows) + "\n").encode("cp1252"))
    lr = LogReader(session_path=str(path))
    assert lr.session_duration == 20.0


def test_last_row_cut_in_its_scenario_time(tmp_path):
    """A session killed while writing: its last row "120.0,20.003,..." cut to "120.0,2" (no end of line)."""
    path = tmp_path / "12_260101_120000.csv"
    rows = [HEADER, "100.0,0.0,event,track,self,start", "119.9,19.9,event,track,self,resume", "120.0,2"]
    path.write_text("\n".join(rows), encoding="utf-8")
    lr = LogReader(session_path=str(path))
    assert lr.end_sec == 19.9
    assert lr.replay_to_scenario_time(lr.session_duration) >= 19.9  # It went back to 2

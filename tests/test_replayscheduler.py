"""Tests for core.replayscheduler - Replay scheduler logic."""

from unittest.mock import patch, MagicMock
import pytest

from core.replayscheduler import ReplayScheduler


def _make_replay(**kwargs):
    """Create a ReplayScheduler bypassing __init__ to avoid GUI/plugin init."""
    rs = object.__new__(ReplayScheduler)
    rs.scenario_time = 0
    rs.replay_time = 0
    rs.is_paused = True
    rs.target_time = 0
    rs.pause_scenario_time = False
    rs.plugins = {}
    rs.events_queue = []
    rs.logreader = MagicMock()
    rs.logreader.end_sec = 300
    rs.logreader.duration_sec = 300
    rs.logreader.session_duration = 300
    rs.playpause = MagicMock()
    rs.slider = MagicMock()
    rs.clock = MagicMock()
    rs.__dict__.update(kwargs)
    return rs


class TestGetTimeHmsStr:
    def test_zero(self):
        """0 seconds formats as 00:00:00.000."""
        rs = _make_replay(replay_time=0)
        assert rs.get_time_hms_str() == '00:00:00.000'

    def test_one_minute(self):
        """60 seconds formats as 00:01:00.000."""
        rs = _make_replay(replay_time=60)
        assert rs.get_time_hms_str() == '00:01:00.000'

    def test_one_hour(self):
        """3600 seconds formats as 01:00:00.000."""
        rs = _make_replay(replay_time=3600)
        assert rs.get_time_hms_str() == '01:00:00.000'

    def test_fractional_seconds(self):
        """Fractional seconds appear in millisecond part."""
        rs = _make_replay(replay_time=65.5)
        assert rs.get_time_hms_str() == '00:01:05.500'

    def test_complex_time(self):
        """Mixed hours/minutes/seconds/ms format correctly."""
        rs = _make_replay(replay_time=3723.5)
        assert rs.get_time_hms_str() == '01:02:03.500'


class TestPausePlayback:
    def test_pause(self):
        """pause_playback sets flag and updates sprite."""
        rs = _make_replay(is_paused=False)
        rs.pause_playback()
        assert rs.is_paused is True
        rs.playpause.update_button_sprite.assert_called_once_with(True)

    def test_resume(self):
        """resume_playback clears flag and updates sprite."""
        rs = _make_replay(is_paused=True)
        rs.resume_playback()
        assert rs.is_paused is False
        rs.playpause.update_button_sprite.assert_called_once_with(False)


class TestTogglePlaypause:
    def test_from_paused_to_playing(self):
        """Resuming sets target to session duration."""
        rs = _make_replay(is_paused=True, replay_time=50)
        rs.logreader.session_duration = 300
        rs.toggle_playpause()
        assert rs.is_paused is False
        assert rs.target_time == 300

    def test_from_playing_to_paused(self):
        """Pausing sets target to current replay_time."""
        rs = _make_replay(is_paused=False, replay_time=50)
        rs.toggle_playpause()
        assert rs.is_paused is True
        assert rs.target_time == 50


class TestCheckPluginsAlive:
    def test_all_alive(self):
        """All alive plugins returns True."""
        p1 = MagicMock(alive=True)
        p2 = MagicMock(alive=True)
        rs = _make_replay(plugins={'a': p1, 'b': p2})
        assert rs.check_plugins_alive() is True

    def test_one_dead(self):
        """One dead plugin returns False."""
        p1 = MagicMock(alive=True)
        p2 = MagicMock(alive=False)
        rs = _make_replay(plugins={'a': p1, 'b': p2})
        assert rs.check_plugins_alive() is False

    def test_empty_plugins(self):
        """Empty plugin dict returns True (vacuous)."""
        rs = _make_replay(plugins={})
        assert rs.check_plugins_alive() is True  # all() of empty is True


class TestPauseIfEndReached:
    def test_pauses_at_end(self):
        """Pauses playback when replay time reaches session duration."""
        rs = _make_replay(replay_time=300, is_paused=False)
        rs.logreader.session_duration = 300
        rs.pause_if_end_reached()
        assert rs.is_paused is True
        rs.playpause.update_button_sprite.assert_called_with(True)

    def test_no_pause_before_end(self):
        """No action while time is before end."""
        rs = _make_replay(replay_time=100, is_paused=False)
        rs.logreader.session_duration = 300
        rs.playpause.reset_mock()
        rs.pause_if_end_reached()
        rs.playpause.update_button_sprite.assert_not_called()

    def test_already_paused_no_action(self):
        """Skip if already paused."""
        rs = _make_replay(replay_time=300, is_paused=True)
        rs.logreader.session_duration = 300
        rs.playpause.reset_mock()
        rs.pause_if_end_reached()
        rs.playpause.update_button_sprite.assert_not_called()


class TestOnKeyPressReplay:
    @patch('core.replayscheduler.Window')
    def test_escape_calls_exit(self, mock_win):
        """Escape triggers exit prompt."""
        rs = _make_replay()
        rs.on_key_press_replay(0xff1b, 0)  # ESCAPE
        mock_win.MainWindow.exit_prompt.assert_called_once()

    def test_space_toggles_playpause(self):
        """Space toggles play/pause."""
        rs = _make_replay(is_paused=True, replay_time=0)
        rs.logreader.session_duration = 300
        rs.on_key_press_replay(0xff20, 0)  # SPACE
        assert rs.is_paused is False

    def test_home_resets_to_start(self):
        """Home key seeks to time 0."""
        rs = _make_replay()
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xff50, 0)  # HOME
        rs.set_target_time.assert_called_once_with(0)

    def test_end_jumps_to_end(self):
        """End key seeks to session duration."""
        rs = _make_replay()
        rs.logreader.session_duration = 300
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xff57, 0)  # END
        rs.set_target_time.assert_called_once_with(300)

    def test_left_steps_back(self):
        """Left arrow steps back 0.1s based on replay_time."""
        rs = _make_replay(replay_time=10.0)
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xff51, 0)  # LEFT
        rs.set_target_time.assert_called_once_with(pytest.approx(9.9))

    def test_right_steps_forward(self):
        """Right arrow steps forward 0.1s based on replay_time."""
        rs = _make_replay(replay_time=10.0)
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xff53, 0)  # RIGHT
        rs.set_target_time.assert_called_once_with(pytest.approx(10.1))

    def test_up_increases_speed(self):
        """Up arrow increases playback speed."""
        rs = _make_replay()
        rs.on_key_press_replay(0xff52, 0)  # UP
        rs.clock.increase_speed.assert_called_once()

    def test_down_decreases_speed(self):
        """Down arrow decreases playback speed."""
        rs = _make_replay()
        rs.on_key_press_replay(0xff54, 0)  # DOWN
        rs.clock.decrease_speed.assert_called_once()


class TestCheckIfMustExit:
    @patch('core.replayscheduler.Window')
    def test_exits_when_window_dead(self, mock_win):
        """Calls exit when window is no longer alive."""
        rs = _make_replay()
        rs.exit = MagicMock()
        mock_win.MainWindow.alive = False
        rs.check_if_must_exit()
        rs.exit.assert_called_once()

    @patch('core.replayscheduler.Window')
    def test_no_exit_when_alive(self, mock_win):
        """Does not exit while window is alive."""
        rs = _make_replay()
        rs.exit = MagicMock()
        mock_win.MainWindow.alive = True
        rs.check_if_must_exit()
        rs.exit.assert_not_called()


class TestUpdateTimers:
    def test_derives_scenario_time_from_mapping(self):
        """update_timers sets scenario_time from replay_to_scenario_time."""
        rs = _make_replay(replay_time=10.0)
        rs.logreader.replay_to_scenario_time.return_value = 5.0
        rs.update_timers(0.1)
        rs.logreader.replay_to_scenario_time.assert_called_once_with(10.0)
        assert rs.scenario_time == 5.0

    def test_sets_logger_scenario_time(self):
        """update_timers updates logger with derived scenario_time."""
        rs = _make_replay(replay_time=7.0)
        rs.logreader.replay_to_scenario_time.return_value = 3.0
        with patch('core.replayscheduler.logger') as mock_logger:
            rs.update_timers(0.1)
            mock_logger.set_scenario_time.assert_called_once_with(3.0)

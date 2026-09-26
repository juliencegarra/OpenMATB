"""Tests for core.replayscheduler - Replay scheduler logic."""

from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import key

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
        assert rs.get_time_hms_str() == "00:00:00.000"

    def test_one_minute(self):
        """60 seconds formats as 00:01:00.000."""
        rs = _make_replay(replay_time=60)
        assert rs.get_time_hms_str() == "00:01:00.000"

    def test_one_hour(self):
        """3600 seconds formats as 01:00:00.000."""
        rs = _make_replay(replay_time=3600)
        assert rs.get_time_hms_str() == "01:00:00.000"

    def test_fractional_seconds(self):
        """Fractional seconds appear in millisecond part."""
        rs = _make_replay(replay_time=65.5)
        assert rs.get_time_hms_str() == "00:01:05.500"

    def test_complex_time(self):
        """Mixed hours/minutes/seconds/ms format correctly."""
        rs = _make_replay(replay_time=3723.5)
        assert rs.get_time_hms_str() == "01:02:03.500"


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
        rs = _make_replay(plugins={"a": p1, "b": p2})
        assert rs.check_plugins_alive() is True

    def test_one_dead(self):
        """One dead plugin returns False."""
        p1 = MagicMock(alive=True)
        p2 = MagicMock(alive=False)
        rs = _make_replay(plugins={"a": p1, "b": p2})
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
    @patch("core.replayscheduler.Window")
    def test_escape_calls_exit(self, mock_win):
        """Escape triggers exit prompt."""
        rs = _make_replay()
        rs.on_key_press_replay(0xFF1B, 0)  # ESCAPE
        mock_win.MainWindow.exit_prompt.assert_called_once()

    def test_space_toggles_playpause(self):
        """Space toggles play/pause."""
        rs = _make_replay(is_paused=True, replay_time=0)
        rs.logreader.session_duration = 300
        rs.on_key_press_replay(0xFF20, 0)  # SPACE
        assert rs.is_paused is False

    def test_home_resets_to_start(self):
        """Home key seeks to time 0."""
        rs = _make_replay()
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xFF50, 0)  # HOME
        rs.set_target_time.assert_called_once_with(0)

    def test_end_jumps_to_end(self):
        """End key seeks to session duration."""
        rs = _make_replay()
        rs.logreader.session_duration = 300
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xFF57, 0)  # END
        rs.set_target_time.assert_called_once_with(300)

    def test_left_steps_back(self):
        """Left arrow steps back 0.1s based on replay_time."""
        rs = _make_replay(replay_time=10.0)
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xFF51, 0)  # LEFT
        rs.set_target_time.assert_called_once_with(pytest.approx(9.9))

    def test_right_steps_forward(self):
        """Right arrow steps forward 0.1s based on replay_time."""
        rs = _make_replay(replay_time=10.0)
        rs.set_target_time = MagicMock()
        rs.on_key_press_replay(0xFF53, 0)  # RIGHT
        rs.set_target_time.assert_called_once_with(pytest.approx(10.1))

    def test_up_increases_speed(self):
        """Up arrow increases playback speed."""
        rs = _make_replay()
        rs.on_key_press_replay(0xFF52, 0)  # UP
        rs.clock.increase_speed.assert_called_once()

    def test_down_decreases_speed(self):
        """Down arrow decreases playback speed."""
        rs = _make_replay()
        rs.on_key_press_replay(0xFF54, 0)  # DOWN
        rs.clock.decrease_speed.assert_called_once()


class TestCheckIfMustExit:
    @patch("core.replayscheduler.Window")
    def test_exits_when_window_dead(self, mock_win):
        """Calls exit when window is no longer alive."""
        rs = _make_replay()
        rs.exit = MagicMock()
        mock_win.MainWindow.alive = False
        rs.check_if_must_exit()
        rs.exit.assert_called_once()

    @patch("core.replayscheduler.Window")
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
        with patch("core.replayscheduler.get_logger") as mock_get_logger:
            rs.update_timers(0.1)
            mock_get_logger.return_value.set_scenario_time.assert_called_once_with(3.0)


class TestCleanupAfterSeek:
    """Tests for _cleanup_after_seek() — stale blocking plugin / modal cleanup."""

    @patch("core.replayscheduler.Window")
    def test_noop_when_nothing_blocking(self, mock_win):
        """No blocking plugin and no modal dialog → nothing happens."""
        rs = _make_replay(replay_time=50.0, pause_scenario_time=False, paused_plugins=[])
        rs.plugins = {}
        mock_win.MainWindow.modal_dialog = None
        rs._cleanup_after_seek()
        # No errors, no calls

    @patch("core.replayscheduler.Window")
    def test_blocking_plugin_inside_segment_untouched(self, mock_win):
        """Blocking plugin still in its segment → not stopped."""
        blocker = MagicMock(blocking=True, paused=False, alive=True)
        rs = _make_replay(
            replay_time=10.0,
            pause_scenario_time=True,
            paused_plugins=[],
            plugins={"instructions": blocker},
        )
        rs.logreader.is_in_blocking_segment.return_value = True
        mock_win.MainWindow.modal_dialog = None

        rs._cleanup_after_seek()

        blocker.stop.assert_not_called()
        assert rs.pause_scenario_time is True

    @patch("core.replayscheduler.Window")
    def test_blocking_plugin_past_segment_force_stopped(self, mock_win):
        """Blocking plugin past its segment → force-stop + resume scenario + resume paused."""
        blocker = MagicMock(blocking=True, paused=False, alive=True)
        paused_p = MagicMock()
        rs = _make_replay(
            replay_time=20.0,
            pause_scenario_time=True,
            paused_plugins=[paused_p],
            plugins={"instructions": blocker},
        )
        rs.logreader.is_in_blocking_segment.return_value = False
        mock_win.MainWindow.modal_dialog = None

        rs._cleanup_after_seek()

        blocker.stop.assert_called_once()
        # Paused plugins should have been shown and resumed
        paused_p.show.assert_called_once()
        paused_p.resume.assert_called_once()
        assert rs.paused_plugins == []
        assert rs.pause_scenario_time is False

    @patch("core.replayscheduler.Window")
    def test_modal_dialog_deleted(self, mock_win):
        """Modal dialog present → on_delete() called."""
        rs = _make_replay(replay_time=50.0, pause_scenario_time=False, paused_plugins=[])
        rs.plugins = {}
        mock_dialog = MagicMock()
        mock_win.MainWindow.modal_dialog = mock_dialog

        rs._cleanup_after_seek()

        mock_dialog.on_delete.assert_called_once()

    @patch("core.replayscheduler.Window")
    def test_both_blocking_and_modal_cleaned(self, mock_win):
        """Both a stale blocking plugin and a modal dialog → both cleaned."""
        blocker = MagicMock(blocking=True, paused=False, alive=True)
        rs = _make_replay(
            replay_time=20.0,
            pause_scenario_time=True,
            paused_plugins=[],
            plugins={"instructions": blocker},
        )
        rs.logreader.is_in_blocking_segment.return_value = False
        mock_dialog = MagicMock()
        mock_win.MainWindow.modal_dialog = mock_dialog

        rs._cleanup_after_seek()

        blocker.stop.assert_called_once()
        assert rs.pause_scenario_time is False
        mock_dialog.on_delete.assert_called_once()


class TestExecuteDueEvents:
    """Seek (fast-forward): every event due at the reached time is executed, not only the first one."""

    def _replay_with_events(self, events):
        from core.event import Event

        rs = _make_replay(scenario_time=8, paused_plugins=[], executed=[], _event_cursor=0)
        rs.events = [Event(line, t, plugin, command) for line, t, plugin, command in events]

        def execute_one_event(event):
            event.done = 1
            rs.executed.append(event.line)
            if event.plugin == "instructions" and event.command == ["start"]:  # Started plugins are not paused
                rs.plugins["instructions"].alive = True
                rs.plugins["instructions"].paused = False

        rs.execute_one_event = execute_one_event
        return rs

    def test_simultaneous_events_at_the_end_are_all_executed(self):
        rs = self._replay_with_events([(1, 8, "sysmon", "stop"), (2, 8, "track", "stop"), (3, 8, "resman", "stop")])
        rs.execute_events()  # The update of the last fast-forward step executes one event
        assert rs.executed == [1]
        rs.execute_due_events()
        assert rs.executed == [1, 2, 3]
        assert rs.events_queue == []

    def test_future_events_are_not_executed(self):
        rs = self._replay_with_events([(1, 8, "sysmon", "stop"), (2, 9, "track", "stop")])
        rs.execute_events()
        rs.execute_due_events()
        assert rs.executed == [1]

    def test_stops_when_a_blocking_plugin_starts(self):
        """Instructions pause the scenario: the next events wait, as in playback."""
        rs = self._replay_with_events(
            [(1, 8, "sysmon", "stop"), (2, 8, "instructions", "start"), (3, 8, "track", "stop")]
        )
        rs.plugins = {"instructions": MagicMock(alive=False, blocking=True, paused=True)}
        rs.execute_events()
        rs.execute_due_events()
        assert rs.executed == [1, 2]
        assert rs.is_scenario_time_paused()
        assert [e.line for e in rs.events_queue] == [3]

    @pytest.mark.parametrize("fast_forward", [True, False])
    def test_only_during_a_fast_forward(self, fast_forward):
        """In playback, events are executed one per update (~every 10 ms), as during the session."""
        from core.scheduler import Scheduler

        rs = _make_replay(is_paused=False, target_time=10, replay_time=5)
        rs.clock.isFastForward = fast_forward
        for name in ("pause_if_end_reached", "update_time_string", "slider_control_update", "execute_due_events"):
            setattr(rs, name, MagicMock())
        rs.events_queue = [MagicMock()]  # Stop before the input emulation
        with patch.object(Scheduler, "update"):
            rs.update(0.1)
        assert rs.execute_due_events.called == fast_forward


def _logreader(keyboard=(), joystick=(), mouse=(), states=(), perf_series=None):
    """LogReader stand-in: each input is (normalized_logtime, address, value)."""

    def rows(items):
        return [{"scenario_time": t, "normalized_logtime": t, "address": a, "value": v} for t, a, v in items]

    lr = MagicMock()
    lr.keyboard_inputs = rows(keyboard)
    lr.joystick_inputs = rows(joystick)
    lr.mouse_inputs = rows(mouse)
    lr.states = rows(states)
    lr.contents = ["0:00:00;sysmon;start"]
    lr.perf_series = perf_series
    lr.duration_sec = 300
    lr.session_duration = 300
    return lr


def _make_loaded_replay(logreader, **kwargs):
    """ReplayScheduler whose time arrays have been computed from ``logreader``."""
    rs = _make_replay(logreader=logreader, _session_path="session.csv", _perf_overlay=None, **kwargs)
    rs._key_logtimes = [i["normalized_logtime"] for i in logreader.keyboard_inputs]
    rs._joy_logtimes = [i["normalized_logtime"] for i in logreader.joystick_inputs]
    rs._mouse_logtimes = [i["normalized_logtime"] for i in logreader.mouse_inputs]
    rs._state_logtimes = [i["normalized_logtime"] for i in logreader.states]
    rs._executed_key_indices = set()
    rs.keys_history = []
    rs.key_widget = MagicMock()
    rs.mouse_label = MagicMock()
    rs.replay_reticle = MagicMock()
    rs._click_marker = None
    rs._click_held = False
    rs._last_mouse_x = None
    rs._last_mouse_y = None
    return rs


class TestInit:
    @patch("core.replayscheduler.Scheduler.__init__", return_value=None)
    @patch("core.replayscheduler.Window")
    def test_builds_the_replay_interface(self, mock_win, _scheduler_init):
        """The media strip, the inputs strip and the key handler are set, playback starts paused."""
        mock_win.MainWindow.width = 1000
        widgets = ("Frame", "PlayPause", "Simpletext", "MuteButton", "Slider", "Reticle", "SimpleHTML")
        patches = [patch(f"core.replayscheduler.{name}") for name in widgets]
        mocks = {name: p.start() for name, p in zip(widgets, patches)}
        try:
            rs = ReplayScheduler(session_path="session.csv")
        finally:
            for p in patches:
                p.stop()

        assert rs._session_path == "session.csv"
        assert rs.is_paused is True
        assert rs._muted is True
        assert rs.keys_history == []
        assert mock_win.MainWindow.on_key_press == rs.on_key_press_replay
        assert rs.playpause is mocks["PlayPause"].return_value
        assert rs.slider is mocks["Slider"].return_value
        mocks["Reticle"].return_value.show.assert_called_once()
        mocks["SimpleHTML"].return_value.show.assert_called_once()
        assert mocks["Frame"].call_count == 2  # Media and inputs backgrounds


class TestSetScenario:
    @patch("core.replayscheduler.PerfOverlay")
    @patch("core.replayscheduler.Scheduler.set_scenario")
    @patch("core.replayscheduler.LogReader")
    @patch("core.replayscheduler.Window")
    def test_loads_the_session_file(self, mock_win, mock_lr, mock_set_scenario, mock_overlay):
        """A session path loads its log once, computes the time arrays and pauses."""
        lr = _logreader(keyboard=[(1.0, "SPACE", "press")], mouse=[(2.0, "x", "10")], perf_series={"track": []})
        mock_lr.return_value = lr
        rs = _make_replay(logreader=None, _session_path="session.csv", _perf_overlay=None, is_paused=False)

        rs.set_scenario()

        mock_lr.assert_called_once_with(session_path="session.csv")
        mock_set_scenario.assert_called_once_with(lr.contents)
        assert rs._key_times == [1.0]
        assert rs._key_logtimes == [1.0]
        assert rs._mouse_logtimes == [2.0]
        assert rs._joy_logtimes == []
        assert rs._perf_overlay is mock_overlay.return_value
        assert rs.slider.value_max == 300
        assert rs.sliding is False
        assert rs.is_paused is True

        # A restart keeps the log and the overlay
        rs.set_scenario()
        mock_lr.assert_called_once()
        mock_overlay.assert_called_once()

    @patch("core.replayscheduler.PerfOverlay")
    @patch("core.replayscheduler.Scheduler.set_scenario")
    @patch("core.replayscheduler.LogReader")
    @patch("core.replayscheduler.Window")
    def test_no_overlay_without_performance_data(self, mock_win, mock_lr, _set_scenario, mock_overlay):
        mock_lr.return_value = _logreader(perf_series={})
        rs = _make_replay(logreader=None, _session_path="session.csv", _perf_overlay=None)
        rs.set_scenario()
        mock_overlay.assert_not_called()

    @patch("core.replayscheduler.Scheduler.set_scenario")
    @patch("core.replayscheduler.get_replay_session_id")
    @patch("core.replayscheduler.LogReader")
    @patch("core.replayscheduler.Window")
    def test_legacy_session_id_reloads_on_change(self, mock_win, mock_lr, mock_id, _set_scenario):
        """Without a path, the log is reloaded only when the replayed session ID changes."""
        mock_win.MainWindow.get_container.return_value = None

        def new_logreader(session_id):
            lr = _logreader()
            lr.replay_session_id = session_id
            return lr

        mock_lr.side_effect = new_logreader
        rs = _make_replay(logreader=None, _session_path=None, _perf_overlay=None)

        mock_id.return_value = 4
        rs.set_scenario()
        rs.set_scenario()
        mock_id.return_value = 5
        rs.set_scenario()

        assert [c.args for c in mock_lr.call_args_list] == [(4,), (5,)]


class TestUpdate:
    INPUTS = ("emulate_keyboard_inputs", "display_joystick_inputs", "display_mouse_inputs", "process_states")

    def _replay(self, **kwargs):
        rs = _make_loaded_replay(_logreader(), **kwargs)
        for name in ("pause_if_end_reached", "update_time_string", "slider_control_update", "check_if_must_exit"):
            setattr(rs, name, MagicMock())
        for name in self.INPUTS:
            setattr(rs, name, MagicMock())
        rs._enforce_mute = MagicMock()
        return rs

    def test_paused_only_checks_exit(self):
        rs = self._replay(is_paused=True, replay_time=5)
        rs.update(0.1)
        rs.check_if_must_exit.assert_called_once()
        assert rs.replay_time == 5

    def test_playing_advances_up_to_the_target(self):
        """The step is limited so that replay_time never exceeds target_time."""
        from core.scheduler import Scheduler

        rs = self._replay(is_paused=False, replay_time=9.95, target_time=10)
        rs.clock.isFastForward = False
        with patch.object(Scheduler, "update") as mock_update:
            rs.update(0.1)
        assert rs.replay_time == pytest.approx(10)
        assert mock_update.call_args.args[0] == pytest.approx(0.05)

    def test_target_reached_does_not_advance(self):
        from core.scheduler import Scheduler

        rs = self._replay(is_paused=False, replay_time=10, target_time=10)
        with patch.object(Scheduler, "update") as mock_update:
            rs.update(0.1)
        mock_update.assert_not_called()
        assert rs.replay_time == 10

    def test_inputs_emulated_and_cursor_updated_when_queue_empty(self):
        rs = self._replay(is_paused=True, replay_time=12)
        rs._perf_overlay = MagicMock()
        rs.logreader.replay_to_scenario_time.return_value = 11
        rs.update(0.1)
        for name in self.INPUTS:
            getattr(rs, name).assert_called_once()
        rs._enforce_mute.assert_called_once()
        rs._perf_overlay.update_cursor.assert_called_once_with(11)

    def test_inputs_deferred_while_events_are_queued(self):
        rs = self._replay(is_paused=True, events_queue=[MagicMock()])
        rs.update(0.1)
        rs.emulate_keyboard_inputs.assert_not_called()

    def test_inputs_emulated_when_blocked_by_a_plugin(self):
        """Queued events cannot fire while a blocking plugin pauses the scenario: inputs must go on."""
        rs = self._replay(is_paused=True, events_queue=[MagicMock()], pause_scenario_time=True)
        rs.update(0.1)
        rs.emulate_keyboard_inputs.assert_called_once()


class TestMute:
    def test_toggle_unmutes_the_radio(self):
        player = MagicMock(volume=0.0)
        rs = _make_replay(_muted=True, mute_button=MagicMock())
        rs.plugins = {"communications": MagicMock(player=player)}
        rs.toggle_mute()
        assert rs._muted is False
        rs.mute_button.update_mute_state.assert_called_once_with(False)
        assert player.volume == 1.0
        rs.toggle_mute()
        assert player.volume == 0.0

    def test_no_communications_plugin(self):
        rs = _make_replay(_muted=True)
        rs._enforce_mute()  # Nothing to mute, no error

    def test_communications_without_player(self):
        rs = _make_replay(_muted=False)
        rs.plugins = {"communications": MagicMock(player=None)}
        rs._enforce_mute()


class TestTogglePlaypauseAtEnd:
    def test_restarts_from_the_beginning(self):
        rs = _make_replay(is_paused=True, replay_time=300)
        rs.set_target_time = MagicMock()
        rs.toggle_playpause()
        rs.set_target_time.assert_called_once_with(0)
        assert rs.is_paused is False
        assert rs.target_time == 300


class TestSliderControlUpdate:
    def test_follows_the_replay_time(self):
        rs = _make_replay(replay_time=42, sliding=False)
        rs.slider.hover = False
        rs.slider.groove_value = 0
        rs.slider_control_update()
        assert rs.slider.groove_value == 42
        rs.slider.set_groove_position.assert_called_once()

    def test_press_pauses_and_release_seeks(self):
        """Grabbing the slider pauses; releasing it seeks and resumes a previously playing replay."""
        rs = _make_replay(replay_time=10, is_paused=False, sliding=False)
        rs.set_target_time = MagicMock()

        rs.slider.hover = True
        rs.slider_control_update()
        assert rs.sliding is True
        assert rs.is_paused is True

        rs.slider.groove_value = 120
        rs.slider_control_update()  # Dragging: the slider does not follow replay_time
        assert rs.slider.groove_value == 120

        rs.slider.hover = False
        rs.slider_control_update()
        assert rs.sliding is False
        rs.set_target_time.assert_called_once_with(120)
        assert rs.is_paused is False
        assert rs.target_time == 300

    def test_release_keeps_a_paused_replay_paused(self):
        rs = _make_replay(replay_time=10, is_paused=True, sliding=False)
        rs.set_target_time = MagicMock()
        rs.slider.hover = True
        rs.slider_control_update()
        rs.slider.hover = False
        rs.slider_control_update()
        assert rs.is_paused is True


class TestPauseIfClockTargetReached:
    def test_reached(self):
        rs = _make_replay(is_paused=False)
        rs.clock.is_target_time_reached.return_value = True
        rs.pause_if_clock_target_reached()
        rs.clock.remove_target_time.assert_called_once()
        assert rs.is_paused is True

    def test_not_reached(self):
        rs = _make_replay(is_paused=False)
        rs.clock.is_target_time_reached.return_value = False
        rs.pause_if_clock_target_reached()
        rs.clock.remove_target_time.assert_not_called()
        assert rs.is_paused is False


class TestSetTargetTime:
    def _replay(self, **kwargs):
        rs = _make_replay(**kwargs)
        rs.clock.isFastForward = False
        rs.restart_scenario = MagicMock()
        rs._cleanup_after_seek = MagicMock()
        return rs

    def test_ignored_during_a_fast_forward(self):
        rs = self._replay(target_time=5)
        rs.clock.isFastForward = True
        rs.set_target_time(100)
        assert rs.target_time == 5
        rs.clock.fastforward_time.assert_not_called()

    def test_same_time_only_pauses(self):
        rs = self._replay(replay_time=50, is_paused=False)
        rs.set_target_time(50)
        assert rs.is_paused is True
        rs.clock.fastforward_time.assert_not_called()
        rs._cleanup_after_seek.assert_not_called()

    def test_forward_fast_forwards_the_difference(self):
        rs = self._replay(replay_time=50)
        rs.set_target_time(80)
        rs.restart_scenario.assert_not_called()
        rs.clock.fastforward_time.assert_called_once_with(30)
        rs._cleanup_after_seek.assert_called_once()
        rs.slider.set_groove_position.assert_called_once()
        assert rs.is_paused is True

    def test_backward_restarts_then_fast_forwards(self):
        rs = self._replay(replay_time=50)
        rs.set_target_time(20)
        rs.restart_scenario.assert_called_once()
        rs.clock.fastforward_time.assert_called_once_with(20)

    def test_backward_to_zero_does_not_fast_forward(self):
        rs = self._replay(replay_time=50)
        rs.set_target_time(0)
        rs.restart_scenario.assert_called_once()
        rs.clock.fastforward_time.assert_not_called()

    @pytest.mark.parametrize("target, expected", [(-10, 0), (1000, 300)])
    def test_clamped_to_the_session(self, target, expected):
        rs = self._replay(replay_time=100)
        rs.set_target_time(target)
        assert rs.target_time == expected


class TestRestartScenario:
    def test_resets_the_replay_state(self):
        marker = MagicMock(visible=True)
        rs = _make_replay(
            replay_time=50,
            scenario_time=40,
            _executed_key_indices={1, 2},
            keys_history=["SPACE (press)"],
            _last_mouse_x=10,
            _last_mouse_y=20,
            _click_held=True,
            _click_marker=marker,
            scenario=MagicMock(),
        )
        rs.set_scenario = MagicMock()

        rs.restart_scenario()

        rs.clock.unschedule.assert_called_once_with(rs.update)
        rs.clock.set_time.assert_called_once_with(0)
        rs.clock.schedule.assert_called_once_with(rs.update)
        rs.scenario.reload_plugins.assert_called_once()
        rs.set_scenario.assert_called_once()
        assert (rs.replay_time, rs.scenario_time, rs.slider.groove_value) == (0, 0, 0)
        assert rs._executed_key_indices == set()
        assert rs.keys_history == []
        assert rs._last_mouse_x is None and rs._last_mouse_y is None
        assert rs._click_held is False
        assert marker.visible is False
        assert rs._click_marker is None


class TestEmulateKeyboardInputs:
    def test_sends_the_keys_of_the_last_step_once(self):
        lr = _logreader(keyboard=[(0.95, "SPACE", "press"), (1.0, "F1", "press"), (1.5, "F2", "press")])
        plugin = MagicMock()
        rs = _make_loaded_replay(lr, replay_time=1.0, plugins={"sysmon": plugin})

        rs.emulate_keyboard_inputs()
        rs.emulate_keyboard_inputs()  # Same step: keys are not sent twice

        assert [c.args for c in plugin.do_on_key.call_args_list] == [
            ("SPACE", "press", True),
            ("F1", "press", True),
        ]
        assert rs.keys_history == ["SPACE (press)", "F1 (press)"]
        rs.key_widget.set_text.assert_called_with("<strong>Keyboard history:\n</strong>SPACE (press)<br>F1 (press)")

    def test_history_skips_repeats_and_keeps_30_entries(self):
        keys = [(i * 0.001, f"K{i // 2}", "press") for i in range(80)]  # Each key twice in a row
        rs = _make_loaded_replay(_logreader(keyboard=keys), replay_time=0.08)
        rs.emulate_keyboard_inputs()
        assert len(rs.keys_history) == 30
        assert rs.keys_history[0] == "K10 (press)"
        assert rs.keys_history[-1] == "K39 (press)"


class TestProcessStates:
    def test_track_cursor(self):
        track = MagicMock()
        track.reticle.proportional_to_relative.return_value = (3, 4)
        lr = _logreader(states=[(1.0, "cursor_proportional", (0.1, 0.2))])
        rs = _make_loaded_replay(lr, replay_time=1.0, plugins={"track": track})
        rs.process_states()
        track.reticle.proportional_to_relative.assert_called_once_with((0.1, 0.2))
        assert track.cursor_position == (3, 4)

    def test_track_without_reticle_is_skipped(self):
        track = MagicMock(spec=[])
        lr = _logreader(states=[(1.0, "cursor_proportional", (0.1, 0.2))])
        rs = _make_loaded_replay(lr, replay_time=1.0, plugins={"track": track})
        rs.process_states()
        assert not hasattr(track, "cursor_position")

    def test_radio_frequency(self):
        radio = {"name": "NAV1", "currentfreq": 110.0}
        comms = MagicMock()
        comms.get_radios_by_key_value.return_value = [radio]
        lr = _logreader(states=[(1.0, "radio_NAV1, radio_frequency", 112.5)])
        rs = _make_loaded_replay(lr, replay_time=1.0, plugins={"communications": comms})
        rs.process_states()
        comms.get_radios_by_key_value.assert_called_once_with("name", "NAV1")
        assert radio["currentfreq"] == 112.5

    def test_genericscales_slider(self):
        slider = MagicMock()
        scales = MagicMock(sliders={"slider_1": slider})
        lr = _logreader(states=[(1.0, "slider_1, value", 7)])
        rs = _make_loaded_replay(lr, replay_time=1.0, plugins={"genericscales": scales})
        rs.process_states()
        assert slider.groove_value == 7
        slider.set_groove_position.assert_called_once()

    def test_states_outside_the_step_are_ignored(self):
        track = MagicMock()
        lr = _logreader(states=[(0.5, "cursor_proportional", (0.1, 0.2))])
        rs = _make_loaded_replay(lr, replay_time=1.0, plugins={"track": track})
        rs.process_states()
        track.reticle.proportional_to_relative.assert_not_called()


class TestMouseInputs:
    @patch("core.replayscheduler.Window")
    def test_remap_into_the_replay_area(self, mock_win):
        from core.constants import REPLAY_PERF_STRIP_PROPORTION as PERF
        from core.constants import REPLAY_STRIP_PROPORTION as STRIP

        mock_win.MainWindow.height = 1000
        rs = _make_replay()
        assert rs._remap_mouse(100, 200) == (int(100 * (1 - STRIP)), int(200 * (1 - STRIP - PERF) + 1000 * STRIP))

    @patch("core.replayscheduler.Window")
    def test_moves_the_cursor(self, mock_win):
        mock_win.MainWindow.height = 1000
        lr = _logreader(mouse=[(0.95, "x", "100.0"), (1.0, "y", "200")])
        rs = _make_loaded_replay(lr, replay_time=1.0)
        rs.display_mouse_inputs()
        assert (rs._last_mouse_x, rs._last_mouse_y) == (100, 200)
        mock_win.MainWindow.set_mouse_position.assert_called_once_with(*rs._remap_mouse(100, 200))
        rs.mouse_label.set_text.assert_called_once_with("Mouse: 100, 200")

    @patch("core.replayscheduler.Window")
    def test_no_position_yet(self, mock_win):
        rs = _make_loaded_replay(_logreader(), replay_time=1.0)
        rs.display_mouse_inputs()
        mock_win.MainWindow.set_mouse_position.assert_not_called()
        rs.mouse_label.set_text.assert_called_once_with("Mouse: --")

    @patch("core.replayscheduler.Window")
    def test_click_marker_follows_the_held_button(self, mock_win):
        """A press shows a marker that moves with the cursor, a release removes it."""
        mock_win.MainWindow.height = 1000
        lr = _logreader(
            mouse=[
                (1.0, "click", "press;100;200"),
                (1.1, "x", "150"),
                (1.1, "y", "250"),
                (1.2, "click", "release;150;250"),
            ]
        )
        rs = _make_loaded_replay(lr, replay_time=1.0)

        rs.display_mouse_inputs()
        marker = rs._click_marker
        assert rs._click_held is True
        assert (marker.x, marker.y) == rs._remap_mouse(100, 200)
        assert marker.opacity == 180
        assert rs.mouse_label.set_text.call_args.args[0] == "Mouse: -- [held]"

        rs.replay_time = 1.1
        rs.display_mouse_inputs()
        assert (marker.x, marker.y) == rs._remap_mouse(150, 250)
        assert rs.mouse_label.set_text.call_args.args[0] == "Mouse: 150, 250 [held]"

        rs.replay_time = 1.2
        rs.display_mouse_inputs()
        assert rs._click_held is False
        assert rs._click_marker is None
        assert marker.visible is False

    @patch("core.replayscheduler.Window")
    def test_new_press_replaces_the_marker(self, mock_win):
        mock_win.MainWindow.height = 1000
        lr = _logreader(mouse=[(1.0, "click", "press;10;10"), (1.05, "click", "press;20;20")])
        rs = _make_loaded_replay(lr, replay_time=1.0)
        rs.display_mouse_inputs()
        first = rs._click_marker
        rs.replay_time = 1.05
        rs.display_mouse_inputs()  # Both presses are in the last step: the first marker is hidden
        assert first.visible is False
        assert rs._click_marker is not first


class TestJoystickInputs:
    def test_moves_the_reticle_to_the_last_position(self):
        lr = _logreader(joystick=[(0.95, "joystick_x", "0.1"), (0.97, "joystick_y", "0.2"), (1.0, "joystick_x", "0.3")])
        rs = _make_loaded_replay(lr, replay_time=1.0)
        rs.replay_reticle.proportional_to_relative.return_value = (5, 6)
        rs.display_joystick_inputs()
        rs.replay_reticle.proportional_to_relative.assert_called_once_with((0.3, 0.2))
        rs.replay_reticle.set_cursor_position.assert_called_once_with(5, 6)

    def test_needs_both_axes(self):
        lr = _logreader(joystick=[(1.0, "joystick_x", "0.3")])
        rs = _make_loaded_replay(lr, replay_time=1.0)
        rs.display_joystick_inputs()
        rs.replay_reticle.set_cursor_position.assert_not_called()


class TestOnKeyPressReplayOthers:
    @patch("core.replayscheduler.Window")
    def test_f12_takes_a_screenshot(self, mock_win):
        rs = _make_replay()
        rs.on_key_press_replay(key.F12, 0)
        mock_win.MainWindow.take_screenshot.assert_called_once()

    def test_m_toggles_mute(self):
        rs = _make_replay()
        rs.toggle_mute = MagicMock()
        rs.on_key_press_replay(key.M, 0)
        rs.toggle_mute.assert_called_once()


class TestUpdateTimeString:
    def test_displays_the_replay_time(self):
        rs = _make_replay(replay_time=65.5, time=MagicMock())
        rs.update_time_string()
        rs.time.set_text.assert_called_once_with("00:01:05.500")

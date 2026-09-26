"""Tests for core.scheduler - Scenario engine (init, update loop, events, exit)."""

from unittest.mock import MagicMock, patch

import pytest

from core.event import Event


def _make_plugin(alive=False, paused=True, blocking=False, parameters=None):
    """Build a mock plugin with the state attributes used by the scheduler."""
    plugin = MagicMock()
    plugin.alive = alive
    plugin.paused = paused
    plugin.blocking = blocking
    plugin.parameters = parameters if parameters is not None else {}
    return plugin


@pytest.fixture
def window():
    """Patch the main window referenced by core.scheduler."""
    with patch("core.scheduler.Window") as win_cls:
        main = win_cls.MainWindow
        main.modal_dialog = None
        main.alive = True
        yield main


@pytest.fixture
def errors():
    """Install an empty mock error collector."""
    from core.error import set_errors

    mock = MagicMock()
    mock.is_empty.return_value = True
    set_errors(mock)
    yield mock
    set_errors(None)


class _FakePlugin:
    """Minimal plugin whose state methods update alive/paused; other calls are recorded."""

    def __init__(self, blocking=False, alive=False, paused=True):
        self.alive, self.paused, self.blocking = alive, paused, blocking
        self.parameters, self.calls = {}, []

    def start(self):
        self.calls.append("start")
        self.alive, self.paused = True, False

    def stop(self):
        self.calls.append("stop")
        self.alive, self.paused = False, True

    def pause(self):
        self.calls.append("pause")
        self.paused = True

    def resume(self):
        self.calls.append("resume")
        self.paused = False

    def on_scenario_loaded(self, scenario):
        pass

    def update(self, scenario_time):
        pass

    def __getattr__(self, name):
        return lambda *a: self.calls.append(name)


def _make_scheduler(plugins=None, events=None, joystick=None):
    """Create a Scheduler without __init__, with a mocked scenario loaded."""
    from core.scheduler import Scheduler

    sched = object.__new__(Scheduler)
    sched.scenario_path = None
    sched.joystick = joystick
    sched.event_loop = MagicMock()
    scenario = MagicMock()
    scenario.events = list(events or [])
    scenario.plugins = dict(plugins or {})
    with patch("core.scheduler.Scenario", return_value=scenario), patch("agents.DefaultAgent"):
        sched.set_scenario()
    return sched


class TestInit:
    def test_init_logs_version_and_runs_loop(self, mock_logger, window):
        """__init__ logs the version, schedules update, loads the scenario and runs the loop."""
        from core.scheduler import Scheduler

        scenario = MagicMock(events=[], plugins={})
        with (
            patch("core.scheduler.Clock") as clock_cls,
            patch("core.scheduler.EventLoop") as loop_cls,
            patch("core.scheduler.Scenario", return_value=scenario) as scen_cls,
            patch("agents.DefaultAgent"),
        ):
            sched = Scheduler(scenario_path="my.txt")

        mock_logger.log_manual_entry.assert_called_once()
        assert mock_logger.log_manual_entry.call_args.kwargs == {"key": "version"}
        clock_cls.assert_called_once_with("main")
        clock_cls.return_value.schedule.assert_called_once_with(sched.update)
        scen_cls.assert_called_once_with(None, scenario_path="my.txt")
        window.display_session_id.assert_called_once()
        loop_cls.return_value.run.assert_called_once()
        assert sched.scenario_time == 0


class TestSetScenario:
    def test_events_sorted_by_time_then_line(self, window):
        """Loaded events are sorted by (time_sec, line)."""
        e1 = Event(3, 5, "a", "start")
        e2 = Event(1, 10, "a", "stop")
        e3 = Event(2, 5, "a", "show")
        sched = _make_scheduler({"a": _make_plugin()}, [e2, e1, e3])
        assert sched.events == [e3, e1, e2]

    def test_explicit_events_ignore_scenario_path(self, window):
        """Passing event lines builds the scenario from them, not from the file."""
        from core.scheduler import Scheduler

        sched = object.__new__(Scheduler)
        sched.scenario_path = "file.txt"
        sched.joystick = None
        with (
            patch("core.scheduler.Scenario", return_value=MagicMock(events=[], plugins={})) as scen_cls,
            patch("agents.DefaultAgent"),
        ):
            sched.set_scenario(["0:00:00;a;start"])
        scen_cls.assert_called_once_with(["0:00:00;a;start"], scenario_path=None)

    def test_agent_assigned_only_to_automaticsolver_plugins(self, window):
        """The default agent is attached only to plugins declaring automaticsolver."""
        auto = _make_plugin(parameters={"automaticsolver": False})
        manual = _make_plugin(parameters={})
        manual.agent = "untouched"
        sched = _make_scheduler({"auto": auto, "manual": manual})
        assert auto.agent is sched.agent
        assert manual.agent == "untouched"

    def test_plugins_receive_joystick_handlers_and_scenario(self, window):
        """Each plugin gets the joystick, key handlers and the loaded scenario."""
        joy = MagicMock()
        p = _make_plugin()
        sched = _make_scheduler({"p": p}, joystick=joy)
        assert p.joystick is joy
        window.push_handlers.assert_called_once_with(p.on_key_press, p.on_key_release)
        p.on_scenario_loaded.assert_called_once_with(sched.scenario)

    def test_replay_mode_skips_key_handlers(self, window):
        """In replay mode, plugin key handlers are not pushed to the window."""
        with patch("core.scheduler.REPLAY_MODE", True):
            _make_scheduler({"p": _make_plugin()})
        window.push_handlers.assert_not_called()

    def test_runtime_state_reset(self, window):
        """Scenario time, queue, cursor and pause flags start from scratch."""
        sched = _make_scheduler()
        assert sched.scenario_time == 0
        assert sched.pause_scenario_time is False
        assert sched.mouse_control_enabled is False
        assert sched._event_cursor == 0
        assert sched.events_queue == []
        assert sched.blocking_plugin is None
        assert sched.paused_plugins == []
        assert sched._dialog_paused is False


class TestUpdate:
    def _sched(self):
        sched = _make_scheduler()
        for name in (
            "update_timers",
            "update_joystick",
            "update_active_plugins",
            "execute_events",
            "check_if_must_exit",
            "execute_plugins_methods",
        ):
            setattr(sched, name, MagicMock())
        return sched

    def test_normal_tick_runs_all_steps(self, window, errors):
        """Without a dialog, a tick updates timers, joystick, plugins, events and exit check."""
        sched = self._sched()
        sched.update(0.1)
        sched.update_timers.assert_called_once_with(0.1)
        sched.update_joystick.assert_called_once()
        sched.update_active_plugins.assert_called_once()
        sched.execute_events.assert_called_once()
        sched.check_if_must_exit.assert_called_once()
        errors.show_errors.assert_not_called()

    def test_errors_are_shown(self, window, errors):
        """Pending errors are displayed on the next tick."""
        errors.is_empty.return_value = False
        sched = self._sched()
        sched.update(0.1)
        errors.show_errors.assert_called_once()

    def test_modal_dialog_pauses_plugins_once_and_freezes(self, window, errors):
        """An open modal dialog pauses active plugins once and stops the tick."""
        sched = self._sched()
        window.modal_dialog = MagicMock()
        sched.update(0.1)
        sched.update(0.1)
        sched.execute_plugins_methods.assert_called_once_with([], ["pause"])
        assert sched._dialog_paused is True
        sched.update_timers.assert_not_called()
        sched.execute_events.assert_not_called()

    def test_dialog_closed_resumes_plugins(self, window, errors):
        """When the dialog closes, active plugins are resumed and the tick proceeds."""
        sched = self._sched()
        window.modal_dialog = MagicMock()
        sched.update(0.1)
        window.modal_dialog = None
        sched.update(0.2)
        sched.execute_plugins_methods.assert_called_with([], ["resume"])
        assert sched._dialog_paused is False
        sched.update_timers.assert_called_once_with(0.2)


class TestModalDialogPause:
    def _open_then_close(self, sched, window):
        window.modal_dialog = MagicMock()
        sched.update(0.1)
        window.modal_dialog = None
        sched.update(0.1)

    def test_only_running_plugins_are_paused(self, window, errors):
        """Opening a dialog pauses running plugins, not the already paused or dead ones."""
        running = _FakePlugin(alive=True, paused=False)
        paused = _FakePlugin(alive=True, paused=True)
        dead = _FakePlugin(alive=False, paused=True)
        sched = _make_scheduler({"running": running, "paused": paused, "dead": dead})
        window.modal_dialog = MagicMock()
        sched.update(0.1)
        assert running.calls == ["pause"]
        assert paused.calls == dead.calls == []
        assert sched._dialog_paused_plugins == [running]

    def test_running_plugins_resumed_after_dialog(self, window, errors):
        """Plugins running before the dialog are resumed when it closes."""
        running = _FakePlugin(alive=True, paused=False)
        sched = _make_scheduler({"running": running})
        self._open_then_close(sched, window)
        assert running.calls == ["pause", "resume"]
        assert running.paused is False
        assert sched._dialog_paused_plugins == []

    def test_already_paused_plugin_stays_paused(self, window, errors):
        """A plugin paused before the dialog is not resumed when it closes."""
        paused = _FakePlugin(alive=True, paused=True)
        sched = _make_scheduler({"paused": paused})
        self._open_then_close(sched, window)
        assert "resume" not in paused.calls
        assert paused.paused is True

    def test_plugin_stopped_during_dialog_not_resumed(self, window, errors):
        """A plugin that stopped while the dialog was open is not resumed."""
        running = _FakePlugin(alive=True, paused=False)
        sched = _make_scheduler({"running": running})
        sched.exit = MagicMock()
        window.modal_dialog = MagicMock()
        sched.update(0.1)
        running.alive = False
        window.modal_dialog = None
        sched.update(0.1)
        assert "resume" not in running.calls

    def test_dialog_during_blocking_plugin(self, window, errors, mock_logger):
        """Tasks hidden by a blocking plugin stay paused across a dialog, then resume with it."""
        instr = _FakePlugin(blocking=True)
        task = _FakePlugin(alive=True, paused=False)
        sched = _make_scheduler({"instr": instr, "task": task}, [Event(1, 0, "instr", "start")])

        sched.update(0.1)  # starts the blocking plugin
        sched.update(0.1)  # pauses and hides the task
        assert task.calls == ["pause", "hide"]

        self._open_then_close(sched, window)
        assert instr.calls == ["start", "pause", "resume"]
        assert instr.paused is False
        assert task.calls == ["pause", "hide"]
        assert task.paused is True

        instr.stop()
        sched.update(0.1)
        assert task.calls == ["pause", "hide", "show", "resume"]
        assert task.paused is False


class TestTimersAndPlugins:
    def test_timer_advances_and_is_logged(self, window, mock_logger):
        """Scenario time accumulates dt and is pushed to the logger."""
        sched = _make_scheduler()
        sched.update_timers(0.5)
        sched.update_timers(0.25)
        assert sched.scenario_time == pytest.approx(0.75)
        mock_logger.set_scenario_time.assert_called_with(pytest.approx(0.75))

    def test_timer_frozen_when_paused(self, window, mock_logger):
        """Scenario time does not advance while paused."""
        sched = _make_scheduler()
        sched.pause_scenario()
        sched.update_timers(1.0)
        assert sched.scenario_time == 0
        mock_logger.set_scenario_time.assert_not_called()

    def test_only_alive_plugins_updated(self, window):
        """update_active_plugins forwards scenario time to alive plugins only."""
        alive = _make_plugin(alive=True)
        dead = _make_plugin(alive=False)
        sched = _make_scheduler({"alive": alive, "dead": dead})
        sched.scenario_time = 3.0
        sched.update_active_plugins()
        alive.update.assert_called_once_with(3.0)
        dead.update.assert_not_called()


class TestUpdateJoystick:
    def _joystick(self, key_change=None):
        joy = MagicMock(x=0.2, y=-0.4)
        joy.key_change = key_change or {}
        joy.has_any_key_changed.return_value = bool(key_change)
        return joy

    def test_no_joystick_is_noop(self, window):
        """Without a joystick, nothing happens."""
        p = _make_plugin(alive=True)
        sched = _make_scheduler({"p": p}, joystick=None)
        sched.update_joystick()
        p.get_joystick_inputs.assert_not_called()

    def test_no_active_plugin_only_polls(self, window):
        """With no alive plugin, the joystick is polled but key changes are not read."""
        joy = self._joystick({"1": "press"})
        sched = _make_scheduler({"p": _make_plugin(alive=False)}, joystick=joy)
        sched.update_joystick()
        joy.update.assert_called_once()
        joy.has_any_key_changed.assert_not_called()

    def test_axes_sent_to_plugins_with_joystick_inputs(self, window):
        """Axes go to plugins exposing get_joystick_inputs; others are skipped."""
        joy = self._joystick()
        track = _make_plugin(alive=True)
        other = _make_plugin(alive=True)
        del other.get_joystick_inputs
        sched = _make_scheduler({"track": track, "other": other}, joystick=joy)
        sched.update_joystick()
        track.get_joystick_inputs.assert_called_once_with(0.2, -0.4)

    def test_button_press_and_release_dispatched(self, window):
        """Button changes are dispatched to alive plugins and then reset."""
        joy = self._joystick({"1": "press", "2": "release", "3": "other"})
        p = _make_plugin(alive=True)
        sched = _make_scheduler({"p": p}, joystick=joy)
        sched.update_joystick()
        p.on_joy_key_press.assert_called_once_with("1")
        p.on_joy_key_release.assert_called_once_with("2")
        assert [c.args[0] for c in joy.reset_key_change.call_args_list] == ["1", "2", "3"]


class TestCheckIfMustExit:
    def test_exit_when_nothing_left(self, window):
        """No alive plugin and an empty queue closes OpenMATB."""
        sched = _make_scheduler({"p": _make_plugin(alive=False)})
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        sched.exit.assert_called_once()

    def test_no_exit_while_plugin_alive(self, window):
        """An alive plugin keeps the scheduler running."""
        sched = _make_scheduler({"p": _make_plugin(alive=True)})
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        sched.exit.assert_not_called()

    def test_no_exit_while_events_queued(self, window):
        """Queued events keep the scheduler running."""
        sched = _make_scheduler({"p": _make_plugin(alive=False)})
        sched.events_queue = [Event(1, 0, "p", "start")]
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        sched.exit.assert_not_called()

    def test_no_exit_before_late_first_start(self, window):
        """A scenario whose first event is after 0:00:00 does not exit before it."""
        sched = _make_scheduler({"p": _make_plugin(alive=False)}, [Event(1, 5, "p", "start")])
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        sched.exit.assert_not_called()

    def test_no_exit_during_gap(self, window):
        """With every plugin stopped but events still to come, the scheduler keeps running."""
        events = [Event(1, 0, "p", "start"), Event(2, 60, "p", "stop"), Event(3, 65, "p", "start")]
        sched = _make_scheduler({"p": _make_plugin(alive=False)}, events)
        sched._event_cursor = 2
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        sched.exit.assert_not_called()

    def test_exit_once_all_events_consumed(self, window):
        """Once every event has been consumed and executed, OpenMATB closes."""
        events = [Event(1, 0, "p", "start"), Event(2, 60, "p", "stop")]
        sched = _make_scheduler({"p": _make_plugin(alive=False)}, events)
        sched._event_cursor = 2
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        sched.exit.assert_called_once()

    def test_gap_scenario_runs_to_the_end(self, window, errors, mock_logger):
        """A scenario with a late start and a gap runs every block and exits at the real end."""
        first, second = _FakePlugin(), _FakePlugin()
        events = [
            Event(1, 5, "first", "start"),
            Event(2, 60, "first", "stop"),
            Event(3, 65, "second", "start"),
            Event(4, 70, "second", "stop"),
        ]
        sched = _make_scheduler({"first": first, "second": second}, events)
        sched.exit = MagicMock()
        while not sched.exit.called and sched.scenario_time < 100:
            sched.update(1)
        assert first.calls == ["start", "stop"]
        assert second.calls == ["start", "stop"]
        assert sched.scenario_time == pytest.approx(70)

    def test_window_killed_stops_alive_plugins(self, window, mock_logger):
        """If the window is closed, alive plugins get a logged stop event, then exit."""
        alive = _make_plugin(alive=True)
        dead = _make_plugin(alive=False)
        sched = _make_scheduler({"alive": alive, "dead": dead})
        sched.scenario_time = 12.7
        window.alive = False
        sched.exit = MagicMock()
        sched.check_if_must_exit()
        alive.stop.assert_called_once()
        dead.stop.assert_not_called()
        event = mock_logger.record_event.call_args.args[0]
        assert (event.plugin, event.command, event.time_sec) == ("alive", ["stop"], 12)
        sched.exit.assert_called_once()


class TestExecuteEvents:
    def test_due_event_executed(self, window, mock_logger):
        """Without a blocking plugin, one due event is executed per tick."""
        p = _make_plugin(alive=False)
        e1 = Event(1, 0, "p", "start")
        e2 = Event(2, 0, "p", "show")
        sched = _make_scheduler({"p": p}, [e1, e2])
        sched.execute_events()
        p.start.assert_called_once()
        p.show.assert_not_called()
        assert sched.events_queue == [e2]
        sched.execute_events()
        p.show.assert_called_once()

    def test_no_due_event(self, window):
        """Future events are not executed."""
        p = _make_plugin()
        sched = _make_scheduler({"p": p}, [Event(1, 10, "p", "start")])
        sched.execute_events()
        p.start.assert_not_called()

    def test_blocking_plugin_pauses_scenario_and_others(self, window):
        """An alive blocking plugin pauses scenario time and hides concurrent plugins."""
        blocker = _make_plugin(alive=True, paused=False, blocking=True)
        other = _make_plugin(alive=True, paused=False)
        sched = _make_scheduler({"blocker": blocker, "other": other}, [Event(1, 0, "other", "stop")])
        sched.execute_events()
        assert sched.is_scenario_time_paused() is True
        assert sched.paused_plugins == [other]
        other.pause.assert_called_once()
        other.hide.assert_called_once()
        blocker.pause.assert_not_called()
        other.stop.assert_not_called()

    def test_blocking_plugin_not_alive_does_nothing(self, window):
        """A blocking plugin that is not alive neither pauses time nor runs events."""
        blocker = _make_plugin(alive=False, paused=False, blocking=True)
        sched = _make_scheduler({"blocker": blocker}, [Event(1, 0, "blocker", "start")])
        sched.execute_events()
        assert sched.is_scenario_time_paused() is False
        blocker.start.assert_not_called()

    def test_blocking_still_active_keeps_pause(self, window):
        """While the blocking plugin is active, the scenario stays paused."""
        blocker = _make_plugin(alive=True, paused=False, blocking=True)
        sched = _make_scheduler({"blocker": blocker})
        sched.pause_scenario()
        sched.execute_events()
        assert sched.is_scenario_time_paused() is True

    def test_blocking_end_resumes_paused_plugins(self, window):
        """Once the blocking plugin ends, paused plugins are shown/resumed and time restarts."""
        blocker = _make_plugin(alive=False, paused=True, blocking=True)
        other = _make_plugin(alive=True, paused=True)
        sched = _make_scheduler({"blocker": blocker, "other": other})
        sched.pause_scenario()
        sched.paused_plugins = [other]
        sched.execute_events()
        other.show.assert_called_once()
        other.resume.assert_called_once()
        assert sched.paused_plugins == []
        assert sched.is_scenario_time_paused() is False

    def test_resume_without_paused_plugins(self, window):
        """With nothing paused by a blocker, the scenario simply resumes."""
        sched = _make_scheduler({"p": _make_plugin()})
        sched.pause_scenario()
        sched.execute_events()
        assert sched.is_scenario_time_paused() is False

    def test_full_blocking_cycle(self, window, mock_logger):
        """Start blocker, pause others, blocker stops, others resume, next event runs."""

        class Fake:
            """Minimal plugin recording calls; start() makes it alive and unpaused."""

            def __init__(self, blocking):
                self.alive, self.paused, self.blocking = False, True, blocking
                self.parameters, self.calls = {}, []

            def start(self):
                self.alive, self.paused = True, False

            def __getattr__(self, name):
                return lambda *a: self.calls.append(name)

        instr, task = Fake(True), Fake(False)
        task.alive, task.paused = True, False
        events = [Event(1, 0, "instr", "start"), Event(2, 1, "task", "stop")]
        sched = _make_scheduler({"instr": instr, "task": task}, events)
        task.calls.clear()

        sched.execute_events()  # starts the blocking plugin
        sched.execute_events()  # detects it: pause scenario and task
        assert sched.is_scenario_time_paused()
        assert task.calls == ["pause", "hide"]

        instr.alive, instr.paused = False, True  # blocker stops
        sched.execute_events()
        assert not sched.is_scenario_time_paused()
        assert task.calls == ["pause", "hide", "show", "resume"]

        sched.scenario_time = 1
        sched.execute_events()
        assert task.calls[-1] == "stop"


class TestExecuteOneEvent:
    def test_method_event(self, window, mock_logger):
        """A single-word command calls the plugin method, marks done and logs it."""
        p = _make_plugin()
        sched = _make_scheduler({"p": p})
        e = Event(1, 0, "p", "start")
        sched.execute_one_event(e)
        p.start.assert_called_once()
        assert e.done == 1
        mock_logger.record_event.assert_called_once_with(e)

    def test_parameter_event(self, window, mock_logger):
        """A two-word command updates a plugin parameter."""
        p = _make_plugin()
        sched = _make_scheduler({"p": p})
        e = Event(1, 0, "p", ["title", "Hello"])
        sched.execute_one_event(e)
        p.set_parameter.assert_called_once_with("title", "Hello")
        assert e.done == 1

    def test_system_event_routed(self, window, mock_logger):
        """System events never touch plugins and are logged."""
        sched = _make_scheduler({"p": _make_plugin()})
        e = Event(1, 0, "system", "pause")
        sched.execute_one_event(e)
        window.pause_prompt.assert_called_once()
        assert e.done == 1
        mock_logger.record_event.assert_called_once_with(e)


class TestSystemCommands:
    def test_agent_switch(self, window, mock_logger):
        """system;agent;<name> creates the agent and gives it to automaticsolver plugins."""
        auto = _make_plugin(parameters={"automaticsolver": True})
        manual = _make_plugin(parameters={})
        manual.agent = None
        sched = _make_scheduler({"auto": auto, "manual": manual})
        with patch("agents.create_agent") as create:
            sched.execute_one_event(Event(1, 0, "system", ["agent", "humanlike"]))
        create.assert_called_once_with("humanlike")
        assert sched.agent is create.return_value
        assert auto.agent is create.return_value
        assert manual.agent is None

    def test_agent_ignored_in_replay(self, window, mock_logger):
        """In replay mode the agent command is logged but not applied."""
        sched = _make_scheduler({"p": _make_plugin(parameters={"automaticsolver": True})})
        previous = sched.agent
        e = Event(1, 0, "system", ["agent", "humanlike"])
        with patch("core.scheduler.REPLAY_MODE", True), patch("agents.create_agent") as create:
            sched.execute_one_event(e)
        create.assert_not_called()
        assert sched.agent is previous
        assert e.done == 1

    @pytest.mark.parametrize("value", [True, "True", "true"])
    def test_mousecontrol_enable(self, window, mock_logger, value):
        """Enabling mouse control pushes mouse handlers of every plugin."""
        p = _make_plugin()
        sched = _make_scheduler({"p": p})
        window.push_handlers.reset_mock()
        sched.execute_one_event(Event(1, 0, "system", ["mousecontrol", value]))
        assert sched.mouse_control_enabled is True
        assert window.mouse_control_active is True
        window.push_handlers.assert_called_once_with(p.on_mouse_press, p.on_mouse_release, p.on_mouse_drag)

    def test_mousecontrol_disable(self, window, mock_logger):
        """Disabling mouse control removes the plugin mouse handlers."""
        p = _make_plugin()
        sched = _make_scheduler({"p": p})
        sched.execute_one_event(Event(1, 0, "system", ["mousecontrol", "false"]))
        assert sched.mouse_control_enabled is False
        assert window.mouse_control_active is False
        window.remove_handlers.assert_called_once_with(p.on_mouse_press, p.on_mouse_release, p.on_mouse_drag)

    def test_mousecontrol_ignored_in_replay(self, window, mock_logger):
        """In replay mode, mousecontrol does not alter handlers."""
        sched = _make_scheduler({"p": _make_plugin()})
        window.push_handlers.reset_mock()
        with patch("core.scheduler.REPLAY_MODE", True):
            sched.execute_one_event(Event(1, 0, "system", ["mousecontrol", "true"]))
        assert sched.mouse_control_enabled is False
        window.push_handlers.assert_not_called()

    def test_unknown_system_command_logged(self, window, mock_logger):
        """An unknown system command is still marked done and logged."""
        sched = _make_scheduler()
        e = Event(1, 0, "system", "whatever")
        sched.execute_one_event(e)
        assert e.done == 1
        mock_logger.record_event.assert_called_once_with(e)


class TestExecutePluginsMethods:
    def test_empty_plugin_list_is_noop(self, window):
        """No plugin means no method lookup at all, even for a bogus method."""
        sched = _make_scheduler()
        sched.execute_plugins_methods([], ["does_not_exist"])

    def test_string_method(self, window):
        """A single method name is accepted as a string."""
        p = _make_plugin()
        sched = _make_scheduler()
        sched.execute_plugins_methods([p], "hide")
        p.hide.assert_called_once()

    def test_methods_applied_in_order(self, window):
        """Each method is applied to all plugins before the next method."""
        order = MagicMock()
        p1, p2 = _make_plugin(), _make_plugin()
        order.attach_mock(p1.pause, "p1_pause")
        order.attach_mock(p2.pause, "p2_pause")
        order.attach_mock(p1.hide, "p1_hide")
        order.attach_mock(p2.hide, "p2_hide")
        sched = _make_scheduler()
        sched.execute_plugins_methods([p1, p2], ["pause", "hide"])
        assert [c[0] for c in order.mock_calls] == ["p1_pause", "p2_pause", "p1_hide", "p2_hide"]


class TestToggle:
    def test_toggle_flips_pause(self, window):
        """toggle_scenario alternates the scenario time pause."""
        sched = _make_scheduler()
        assert sched.toggle_scenario() is True
        assert sched.toggle_scenario() is False


class TestExit:
    def test_exit_closes_everything(self, window, mock_logger):
        """exit logs 'end', stops the loop, closes the window and exits the process."""
        sched = _make_scheduler()
        with pytest.raises(SystemExit) as info:
            sched.exit()
        assert info.value.code == 0
        mock_logger.log_manual_entry.assert_called_with("end")
        sched.event_loop.exit.assert_called_once()
        window.close.assert_called_once()

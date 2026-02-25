"""Tests for core.scheduler - Logic only (no event loop)."""

from unittest.mock import MagicMock

from core.event import Event


class TestGetPluginsByStates:
    def _make_scheduler_methods(self):
        """Extract the filtering method without running __init__."""
        from core.scheduler import Scheduler

        # Just test the static method logic using a mock
        sched = object.__new__(Scheduler)
        return sched

    def test_filter_alive(self):
        """Filters plugins where alive=True."""
        sched = self._make_scheduler_methods()

        p1 = MagicMock(alive=True, paused=False)
        p2 = MagicMock(alive=False, paused=False)
        sched.plugins = {"p1": p1, "p2": p2}

        result = sched.get_plugins_by_states([("alive", True)])
        assert p1 in result
        assert p2 not in result

    def test_filter_multiple_states(self):
        """Combines multiple state conditions with AND."""
        sched = self._make_scheduler_methods()

        p1 = MagicMock(alive=True, blocking=True, paused=False)
        p2 = MagicMock(alive=True, blocking=False, paused=False)
        sched.plugins = {"p1": p1, "p2": p2}

        result = sched.get_plugins_by_states([("blocking", True), ("paused", False)])
        assert p1 in result
        assert p2 not in result

    def test_empty_plugins(self):
        """Empty plugin dict returns empty list."""
        sched = self._make_scheduler_methods()
        sched.plugins = {}
        result = sched.get_plugins_by_states([("alive", True)])
        assert result == []


class TestScenarioTimePause:
    def _make_scheduler(self):
        sched = object.__new__(__import__("core.scheduler", fromlist=["Scheduler"]).Scheduler)
        sched.pause_scenario_time = False
        return sched

    def test_initial_not_paused(self):
        """Scenario starts unpaused."""
        sched = self._make_scheduler()
        assert sched.is_scenario_time_paused() is False

    def test_pause(self):
        """pause_scenario sets paused to True."""
        sched = self._make_scheduler()
        sched.pause_scenario()
        assert sched.is_scenario_time_paused() is True

    def test_resume(self):
        """resume_scenario clears pause flag."""
        sched = self._make_scheduler()
        sched.pause_scenario()
        sched.resume_scenario()
        assert sched.is_scenario_time_paused() is False

    def test_toggle(self):
        """toggle_scenario flips the pause state."""
        sched = self._make_scheduler()
        sched.toggle_scenario()
        assert sched.is_scenario_time_paused() is True
        sched.toggle_scenario()
        assert sched.is_scenario_time_paused() is False


class TestUnqueueEvent:
    def _make_scheduler(self):
        sched = object.__new__(__import__("core.scheduler", fromlist=["Scheduler"]).Scheduler)
        return sched

    def test_empty_queue(self):
        """Empty queue returns None."""
        sched = self._make_scheduler()
        sched.events_queue = []
        assert sched.unqueue_event() is None

    def test_dequeue_order(self):
        """Events are dequeued in FIFO order."""
        sched = self._make_scheduler()
        e1 = MagicMock(name="e1")
        e2 = MagicMock(name="e2")
        sched.events_queue = [e1, e2]

        result = sched.unqueue_event()
        assert result == e1
        assert len(sched.events_queue) == 1
        assert sched.events_queue[0] == e2


class TestActivePluginHelpers:
    def _make_scheduler(self):
        sched = object.__new__(__import__("core.scheduler", fromlist=["Scheduler"]).Scheduler)
        return sched

    def test_get_active_plugins(self):
        """Returns only alive plugins."""
        sched = self._make_scheduler()
        p1 = MagicMock(alive=True)
        p2 = MagicMock(alive=False)
        sched.plugins = {"p1": p1, "p2": p2}
        result = sched.get_active_plugins()
        assert len(result) == 1
        assert p1 in result

    def test_get_active_blocking_plugin(self):
        """Returns the blocking, unpaused plugin."""
        sched = self._make_scheduler()
        p1 = MagicMock(blocking=True, paused=False)
        p2 = MagicMock(blocking=False, paused=False)
        sched.plugins = {"p1": p1, "p2": p2}
        result = sched.get_active_blocking_plugin()
        assert result == p1

    def test_get_active_blocking_plugin_none(self):
        """Returns None when no blocking plugin."""
        sched = self._make_scheduler()
        p1 = MagicMock(blocking=False, paused=False)
        sched.plugins = {"p1": p1}
        result = sched.get_active_blocking_plugin()
        assert result is None

    def test_get_active_non_blocking(self):
        """Returns unpaused non-blocking plugins."""
        sched = self._make_scheduler()
        p1 = MagicMock(blocking=True, paused=False)
        p2 = MagicMock(blocking=False, paused=False)
        sched.plugins = {"p1": p1, "p2": p2}
        result = sched.get_active_non_blocking_plugins()
        assert p2 in result
        assert p1 not in result


class TestExit:
    def _make_scheduler(self):
        from core.scheduler import Scheduler

        sched = object.__new__(Scheduler)
        sched._exited = False
        sched.clock = MagicMock()
        return sched

    def test_exit_does_not_block_nor_sys_exit(self, mock_window, monkeypatch):
        """exit() ends the session and asks the pyglet app loop to stop (no sys.exit)."""
        import core.scheduler as scheduler_module

        logger = MagicMock()
        app_exit = MagicMock()
        monkeypatch.setattr(scheduler_module, "get_logger", lambda: logger)
        monkeypatch.setattr(scheduler_module.pyglet.app, "exit", app_exit)
        sched = self._make_scheduler()

        sched.exit()

        sched.clock.unschedule.assert_called_once_with(sched.update)
        logger.end_session.assert_called_once()
        mock_window.close.assert_called_once()
        app_exit.assert_called_once()

    def test_exit_is_idempotent(self, mock_window, monkeypatch):
        """A second exit() call (e.g. from the next update) does nothing."""
        import core.scheduler as scheduler_module

        logger = MagicMock()
        monkeypatch.setattr(scheduler_module, "get_logger", lambda: logger)
        monkeypatch.setattr(scheduler_module.pyglet.app, "exit", MagicMock())
        sched = self._make_scheduler()

        sched.exit()
        sched.exit()

        logger.end_session.assert_called_once()


class TestGetEventAtScenarioTime:
    def _make_scheduler(self, events):
        from core.scheduler import Scheduler

        sched = object.__new__(Scheduler)
        sched.events = sorted(events, key=lambda e: (e.time_sec, e.line))
        sched._event_cursor = 0
        sched.events_queue = []
        return sched

    def test_events_in_time_order(self):
        """Events are returned in ascending time order."""
        e1 = Event(1, 5, "sysmon", "start")
        e2 = Event(2, 10, "track", "start")
        sched = self._make_scheduler([e2, e1])

        result = sched.get_event_at_scenario_time(5)
        assert result is e1

        result = sched.get_event_at_scenario_time(10)
        assert result is e2

    def test_simultaneous_events_line_order(self):
        """Same time_sec events are dispatched in line-number order."""
        e1 = Event(3, 10, "sysmon", "start")
        e2 = Event(1, 10, "track", "start")
        e3 = Event(2, 10, "resman", "start")
        sched = self._make_scheduler([e1, e2, e3])

        # All three enqueued at once, returned one per call in line order
        r1 = sched.get_event_at_scenario_time(10)
        r2 = sched.get_event_at_scenario_time(10)
        r3 = sched.get_event_at_scenario_time(10)
        assert r1 is e2  # line 1
        assert r2 is e3  # line 2
        assert r3 is e1  # line 3

    def test_cursor_advance(self):
        """Calling with increasing times returns events progressively."""
        e1 = Event(1, 5, "sysmon", "start")
        e2 = Event(2, 10, "track", "start")
        e3 = Event(3, 20, "resman", "start")
        sched = self._make_scheduler([e1, e2, e3])

        assert sched.get_event_at_scenario_time(3) is None
        assert sched.get_event_at_scenario_time(5) is e1
        assert sched.get_event_at_scenario_time(7) is None
        assert sched.get_event_at_scenario_time(10) is e2
        assert sched.get_event_at_scenario_time(15) is None
        assert sched.get_event_at_scenario_time(20) is e3

    def test_no_events_before_first(self):
        """Returns None when scenario_time < first event time."""
        e1 = Event(1, 10, "sysmon", "start")
        sched = self._make_scheduler([e1])

        assert sched.get_event_at_scenario_time(0) is None
        assert sched.get_event_at_scenario_time(9) is None

    def test_all_consumed(self):
        """Returns None after all events have been dispatched."""
        e1 = Event(1, 5, "sysmon", "start")
        sched = self._make_scheduler([e1])

        assert sched.get_event_at_scenario_time(5) is e1
        assert sched.get_event_at_scenario_time(5) is None
        assert sched.get_event_at_scenario_time(100) is None

    def test_queue_drains_before_cursor_advances(self):
        """Multiple calls at the same time drain the queue one by one."""
        e1 = Event(1, 5, "sysmon", "start")
        e2 = Event(2, 5, "track", "start")
        e3 = Event(3, 10, "resman", "start")
        sched = self._make_scheduler([e1, e2, e3])

        # First call at t=5 enqueues e1 and e2, returns e1
        r1 = sched.get_event_at_scenario_time(5)
        assert r1 is e1
        # Second call at t=5 — cursor doesn't move, drains e2 from queue
        r2 = sched.get_event_at_scenario_time(5)
        assert r2 is e2
        # Third call at t=5 — queue empty, no new events
        r3 = sched.get_event_at_scenario_time(5)
        assert r3 is None
        # Now advance to t=10
        r4 = sched.get_event_at_scenario_time(10)
        assert r4 is e3

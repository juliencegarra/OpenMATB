"""Tests for core.timing and the response times of the plugins (onset at the frame, response at the input event)."""

import sys
import types
from unittest.mock import patch

import pytest

from core import timing
from tests.test_sysmon_logic import _make_sysmon


class FakeTime:
    """perf_counter() replacement."""

    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def now():
    timing.reset()
    fake = FakeTime()
    with patch.object(timing, "perf_counter", fake):
        yield fake
    timing.reset()


class TestScenarioTimeAt:
    def test_none_without_scheduler(self, now):
        assert timing.scenario_time_at(now.now) is None

    def test_follows_the_real_time_after_the_tick(self, now):
        timing.set_tick(10.0, running=True)
        assert timing.scenario_time_at(now.now + 0.012) == pytest.approx(10.012)

    def test_frozen_while_paused(self, now):
        timing.set_tick(10.0, running=False)
        assert timing.scenario_time_at(now.now + 5) == 10.0

    def test_event_before_the_tick_is_not_before_the_previous_tick(self, now):
        timing.set_tick(10.0, running=True)
        now.now += 0.02
        timing.set_tick(10.02, running=True)
        assert timing.scenario_time_at(now.now - 0.005) == pytest.approx(10.015)
        assert timing.scenario_time_at(now.now - 5) == pytest.approx(10.0)


class TestFlip:
    def test_callbacks_are_called_once_with_the_frame_time(self, now):
        times = []
        timing.call_on_flip(times.append)
        now.now = 101.0
        timing.flip()
        timing.flip()
        assert times == [101.0]


class TestInputTime:
    def test_desktop_is_now(self, now):
        assert timing.input_time() == now.now

    @pytest.mark.parametrize(
        "event, expected",
        [
            (types.SimpleNamespace(type="keydown", timeStamp=99_990.0), 99.99),  # The event timestamp (ms)
            (types.SimpleNamespace(type="mousedown", timeStamp=99_950.0), 99.95),
            (types.SimpleNamespace(type="resize", timeStamp=99_990.0), 100.0),  # Not an input
            (types.SimpleNamespace(type="keydown", timeStamp=90_000.0), 100.0),  # Too old: not this input
            (None, 100.0),  # Not during an event
        ],
    )
    def test_browser_uses_the_event_timestamp(self, now, event, expected):
        fake_js = types.SimpleNamespace(window=types.SimpleNamespace(event=event))
        with patch.object(timing, "IS_WEB", True), patch.dict(sys.modules, {"js": fake_js}):
            assert timing.input_time() == pytest.approx(expected)


class TestSysmonResponseTime:
    """A failure starts at a tick (scenario time 10) and is drawn 8 ms later. The key is pressed 300 ms after the
    frame, and handled 20 ms later, when the scenario time is the one of its tick (10.32)."""

    def _answer(self, now, resolved_by: str) -> float:
        s = _make_sysmon()
        light = s.parameters["lights"]["1"]
        timing.set_tick(10.0, running=True)
        s.scenario_time = 10.0
        s.start_failure(light)
        now.now += 0.008
        timing.flip()
        now.now += 0.300  # Key pressed
        with patch.object(timing, "input_time", return_value=now.now):
            now.now += 0.020  # Handled
            s.scenario_time = 10.32
            s.stop_failure(light, success=True, resolved_by=resolved_by)
        return s.performance["response_time"][-1]

    def test_human_from_the_frame_to_the_key_press(self, now):
        assert self._answer(now, "human") == pytest.approx(300.0)

    def test_agent_in_scenario_time(self, now):
        assert self._answer(now, "agent") == pytest.approx(320.0)  # 10.32 - 10.0: the ticks

    def test_without_frame_from_the_start(self, now):
        s = _make_sysmon()
        timing.set_tick(10.0, running=True)
        with patch.object(timing, "input_time", return_value=now.now + 0.25):
            assert s.response_time_ms({"_response_start": 10.0, "_onset": None}, human=True) == pytest.approx(250.0)

    def test_without_scheduler_in_scenario_time(self, now):
        s = _make_sysmon()
        s.scenario_time = 10.4
        assert s.response_time_ms({"_response_start": 10.0, "_onset": 10.01}, human=True) == pytest.approx(400.0)

# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""The computer logged at the start of a session (core.environment), and the frames at its end (core.timing)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from core import environment, timing


def _screen(name: str, x: int = 0, width: int = 1920, height: int = 1080) -> MagicMock:
    screen = MagicMock(x=x, y=0, width=width, height=height)
    screen.get_monitor_name.return_value = name
    screen.get_dpi.return_value = 96
    screen.get_scale.return_value = 1.0
    screen.get_mode.return_value = MagicMock(width=width, height=height, rate=60, depth=32)
    return screen


def _window(x: int = 0, fullscreen: bool = True) -> MagicMock:
    window = MagicMock(width=1920, height=1080, fullscreen=fullscreen, vsync=True)
    window.get_location.return_value = (x, 0)
    return window


class TestDisplay:
    def test_the_screen_and_the_window(self):
        with patch.object(environment, "get_display") as display:
            display.return_value.get_screens.return_value = [_screen("27G2G4")]
            assert environment._display_entries(_window()) == [
                ("screen", "27G2G4"),
                ("screen_mode", "1920x1080 60Hz 32bit"),
                ("screen_scale", "96 dpi, scale 1.0"),
                ("screen_count", "1"),
                ("window_mode", "fullscreen"),
                ("vsync", "True"),
            ]

    def test_the_screen_showing_the_window_with_several_screens(self):
        """The window is moved to the screen_index of config.ini: the model and the rate of that screen count."""
        screens = [_screen("First"), _screen("Second", x=1920)]
        with patch.object(environment, "get_display") as display:
            display.return_value.get_screens.return_value = screens
            entries = dict(environment._display_entries(_window(x=1920, fullscreen=False)))
        assert entries["screen"] == "Second"
        assert entries["screen_count"] == "2"
        assert entries["window_mode"] == "windowed"

    def test_the_screen_of_pyglet_when_out_of_the_screens(self):
        window = _window(x=99999)
        assert environment._screen_of(window, [_screen("First")]) is window.screen


class TestSystemEnvironment:
    def test_nothing_in_the_browser(self):
        with patch.object(environment, "IS_WEB", True):
            assert environment.system_environment(_window()) == []

    def test_a_failure_loses_only_its_entries(self):
        """These details depend on the drivers: a failure must never stop a session."""
        with (
            patch.object(environment, "_display_entries", side_effect=RuntimeError("no screen")),
            patch.object(environment, "_gpu_entries", side_effect=OSError),
            patch.object(environment, "_software_entries", return_value=[("system", "An OS")]),
            patch.object(environment, "_cpu_entries", side_effect=ValueError),
            patch.object(environment, "_memory_entries", return_value=[("ram", "8.0 GB")]),
            patch.object(environment, "_audio_entries", side_effect=ImportError),
            patch.object(environment, "_power_entries", return_value=[]),
            patch.object(environment, "_power_plan_entries", side_effect=AttributeError),
        ):
            assert environment.system_environment(_window()) == [("system", "An OS"), ("ram", "8.0 GB")]

    def test_no_identifying_entry(self):
        keys = {key for key, _ in environment._software_entries() + environment._cpu_entries()}
        assert keys <= {"system", "python", "pyglet", "cpu", "cpu_cores"}


class TestCpu:
    def test_generic_description_if_the_name_cannot_be_read(self):
        with (
            patch.object(environment, "_cpu_name", side_effect=OSError),
            patch.object(environment.platform, "processor", return_value="x86_64"),
            patch.object(environment.os, "cpu_count", return_value=4),
        ):
            assert environment._cpu_entries() == [("cpu", "x86_64"), ("cpu_cores", "4")]

    def test_no_entry_without_information(self):
        with (
            patch.object(environment, "_cpu_name", return_value=""),
            patch.object(environment.os, "cpu_count", return_value=None),
        ):
            assert environment._cpu_entries() == []

    @pytest.mark.skipif(sys.platform != "win32", reason="The Windows registry")
    def test_commercial_name_on_windows(self):
        """Not the description of platform.processor() ("Intel64 Family 6 Model 183 Stepping 1, GenuineIntel")."""
        assert "Family" not in environment._cpu_name()


class TestMemory:
    def test_in_gigabytes(self):
        with patch.object(environment, "_total_memory", return_value=8 * 2**30):
            assert environment._memory_entries() == [("ram", "8.0 GB")]

    def test_total_memory_of_this_computer(self):
        assert environment._total_memory() > 0


class TestPower:
    @pytest.mark.skipif(sys.platform == "win32", reason="Only Windows gives them")
    def test_nothing_on_other_systems(self):
        assert environment._power_entries() == []
        assert environment._power_plan_entries() == []

    @pytest.mark.skipif(sys.platform != "win32", reason="The Windows power functions")
    def test_power_of_this_computer(self):
        for key, value in environment._power_entries() + environment._power_plan_entries():
            assert key in ("power", "power_plan")
            assert value


class TestFrameStatistics:
    @pytest.fixture(autouse=True)
    def clean_timing(self):
        timing.reset()
        yield
        timing.reset()

    @staticmethod
    def _flips(*times: float) -> None:
        with patch("core.timing.perf_counter", side_effect=list(times)):
            for _ in times:
                timing.flip()

    def test_nothing_without_two_frames(self):
        assert timing.frame_statistics() == []
        self._flips(1.0)
        assert timing.frame_statistics() == []

    def test_regular_frames(self):
        self._flips(*(1.0 + n * 0.01 for n in range(5)))
        assert dict(timing.frame_statistics()) == {
            "frames": "4",
            "frame_median_ms": "10.00",
            "frame_sd_ms": "0.00",
            "frame_max_ms": "10.00",
            "frames_late": "0",
        }

    def test_a_missed_refresh_is_late(self):
        self._flips(1.0, 1.01, 1.02, 1.03, 1.05)
        statistics = dict(timing.frame_statistics())
        assert statistics["frame_median_ms"] == "10.00"
        assert statistics["frame_max_ms"] == "20.00"
        assert statistics["frames_late"] == "1"

    def test_a_long_interval_changes_neither_the_median_nor_the_deviation(self):
        """A pause of the page, a dialog: they stay the period and the regularity of the frames."""
        self._flips(1.0, 1.01, 1.02, 1.03, 31.0)
        statistics = dict(timing.frame_statistics())
        assert statistics["frame_median_ms"] == "10.00"
        assert statistics["frame_sd_ms"] == "0.00"
        assert statistics["frames_late"] == "1"

    def test_the_deviation_of_the_frames_on_time(self):
        self._flips(1.0, 1.01, 1.022, 1.032, 1.044)  # 10, 12, 10, 12 ms
        assert dict(timing.frame_statistics())["frame_sd_ms"] == "1.00"

    def test_reset_with_the_scenario(self):
        """The loading of the scenario is not a late frame."""
        self._flips(1.0, 1.01)
        timing.reset()
        self._flips(9.0, 9.01)
        assert dict(timing.frame_statistics())["frames"] == "1"

    def test_the_callbacks_still_get_the_time_of_the_frame(self):
        callback = MagicMock()
        timing.call_on_flip(callback)
        self._flips(2.5)
        callback.assert_called_once_with(2.5)


class TestSchedulerExit:
    def test_the_statistics_are_logged_before_the_end(self):
        from core.scheduler import Scheduler

        scheduler = object.__new__(Scheduler)
        scheduler._exited = False
        scheduler.clock = MagicMock()
        logger = MagicMock()
        with (
            patch("core.scheduler.get_logger", return_value=logger),
            patch("core.scheduler.Window"),
            patch("core.scheduler.pyglet"),
            patch("core.scheduler.notify_page"),
            patch("core.scheduler.timing.frame_statistics", return_value=[("frames", "10")]),
        ):
            scheduler.exit()
        calls = logger.log_manual_entry.call_args_list
        assert [c.args[0] for c in calls] == ["10", "end"]
        assert calls[0].kwargs == {"key": "frames"}
        logger.end_session.assert_called_once()

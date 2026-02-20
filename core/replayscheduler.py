# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations

from bisect import bisect_right
from time import gmtime, strftime
from typing import Any

from pyglet.window import key

from core.constants import COLORS as C
from core.constants import FONT_SIZES as F
from core.container import Container
from core.logger import get_logger
from core.logreader import LogReader
from core.scheduler import Scheduler
from core.utils import clamp, get_replay_session_id
from core.widgets import Frame, MuteButton, PlayPause, Reticle, SimpleHTML, Simpletext, Slider
from core.window import Window

CLOCK_STEP: float = 0.1


class ReplayScheduler(Scheduler):
    """
    This class manages events execution in the context of the OpenMATB replay.
    """

    def __init__(self, session_path: str | None = None) -> None:
        self.logreader: LogReader | None = None
        self._session_path: str | None = session_path
        self.target_time: float = 0
        self.replay_time: float = 0
        self._executed_key_indices: set[int] = set()
        self.keys_history: list[str] = []
        self._muted: bool = True

        self.set_media_buttons()

        self.set_inputs_buttons()

        Window.MainWindow.on_key_press = self.on_key_press_replay

        # Init is done after UX is set
        super().__init__()

        self.is_paused: bool = True

    def set_scenario(self) -> None:
        need_new_logreader: bool = False

        if self._session_path is not None:
            # Direct path from file selector
            need_new_logreader = self.logreader is None
        else:
            # Legacy: look up by session ID
            replay_session_id: int = get_replay_session_id()
            need_new_logreader = self.logreader is None or replay_session_id != self.logreader.replay_session_id

        if need_new_logreader:
            if self._session_path is not None:
                self.logreader = LogReader(session_path=self._session_path)
            else:
                self.logreader = LogReader(replay_session_id)
            # Pre-compute sorted time arrays for O(log n) bisect lookup
            self._key_times: list[float] = [float(i["scenario_time"]) for i in self.logreader.keyboard_inputs]
            self._joy_times: list[float] = [float(i["scenario_time"]) for i in self.logreader.joystick_inputs]
            self._state_times: list[float] = [float(i["scenario_time"]) for i in self.logreader.states]
            # Logtime-based arrays for replay_time lookup
            self._key_logtimes: list[float] = [i["normalized_logtime"] for i in self.logreader.keyboard_inputs]
            self._joy_logtimes: list[float] = [i["normalized_logtime"] for i in self.logreader.joystick_inputs]
            self._state_logtimes: list[float] = [i["normalized_logtime"] for i in self.logreader.states]

        super().set_scenario(self.logreader.contents)

        self.sliding: bool = False

        self.slider.value_max = self.logreader.session_duration

        self.pause_playback()

    def set_inputs_buttons(self) -> None:
        # Plot the keyboard keys that are available in the present plugins
        input_container: Container = Window.MainWindow.get_container("inputstrip")
        key_container: Container = input_container.reduce_and_translate(width=0.9, height=0.8, y=0, x=0.5)
        self.key_widget: SimpleHTML = SimpleHTML("replay_keys", key_container, "<strong>Keyboard history:\n</strong>")
        self.key_widget.show()

    def set_media_buttons(self) -> None:
        # Media strip
        media_container: Container = Window.MainWindow.get_container("mediastrip")
        self.media_back: Frame = Frame("media_background", media_container, fill_color=C["DARKGREY"], draw_order=1)
        self.media_back.show()
        pp_container: Container = media_container.reduce_and_translate(width=0.06, height=1, x=0)
        time_container: Container = media_container.reduce_and_translate(width=0.03, height=1, x=0.78)

        self.playpause: PlayPause = PlayPause("Play_pause_button", pp_container, self.toggle_playpause)
        self.time: Simpletext = Simpletext(
            "elapsed_time", time_container, text="", font_size=F["LARGE"], color=C["WHITE"]
        )

        margin: int = 10
        btn_w: float = media_container.h * 1.8
        pad_b: int = 4
        mute_container: Container = Container(
            "mute_btn",
            Window.MainWindow.width - margin - btn_w,
            media_container.b + pad_b,
            btn_w,
            media_container.h - 2 * pad_b,
        )
        self.mute_button: MuteButton = MuteButton("mute_button", mute_container, self.toggle_mute)

        self.slider: Slider = Slider("timeline", media_container, None, "", "", 0, 1, 0, 1)
        self.time.show()

        # Inputs strip
        input_container: Container = Window.MainWindow.get_container("inputstrip")
        self.inputs_back: Frame = Frame("inputs_background", input_container, fill_color=C["LIGHTGREY"], draw_order=1)
        self.inputs_back.show()

        # Manually compute the joystick container to ensure it is a square
        w: float = input_container.w * 0.8
        h: float = w
        l: float = input_container.l + 0.1 * input_container.w
        b: float = input_container.b + 0.85 * input_container.h
        joy_container: Container = Container("replay_reticle", l, b, w, h)
        self.replay_reticle: Reticle = Reticle(
            "replay_reticle", joy_container, C["BLACK"], target_proportion=0, m_draw=5
        )
        self.replay_reticle.show()

    def on_key_press_replay(self, symbol: int, modifier: int) -> None:
        if symbol == key.ESCAPE:
            Window.MainWindow.exit_prompt()
        elif symbol == key.SPACE:
            self.toggle_playpause()
        elif symbol == key.HOME:
            self.set_target_time(0)
        elif symbol == key.END:
            self.set_target_time(self.logreader.session_duration)
        elif symbol == key.LEFT:
            self.set_target_time(self.replay_time - 0.1)
        elif symbol == key.RIGHT:
            self.set_target_time(self.replay_time + 0.1)
        elif symbol == key.UP:
            self.clock.increase_speed()
        elif symbol == key.DOWN:
            self.clock.decrease_speed()
        elif symbol == key.M:
            self.toggle_mute()

    def update_timers(self, dt: float) -> None:
        # Derive scenario_time from the replay_time -> scenario_time mapping.
        # The mapping handles blocking segments (slope=0) automatically.
        self.scenario_time = self.logreader.replay_to_scenario_time(self.replay_time)
        get_logger().set_scenario_time(self.scenario_time)

    def update(self, dt: float) -> None:
        self.pause_if_end_reached()
        self.update_time_string()
        self.slider_control_update()

        if not self.is_paused:
            dt = min(dt, self.target_time - self.replay_time)

            if dt > 0:
                self.replay_time += dt
                super().update(dt)  # update_timers (mapping) + execute_events
        else:
            # Required: check exit while paused (super().update is not called)
            self.check_if_must_exit()

        # Defer input emulation while queued events can still be processed.
        # When scenario_time is paused (blocking plugin active), events in the
        # queue cannot fire, so we must allow keyboard emulation to proceed
        # (e.g. SPACE to advance instruction slides).
        if len(self.events_queue) > 0 and not self.is_scenario_time_paused():
            return

        self.emulate_keyboard_inputs()
        self.display_joystick_inputs()
        self.process_states()
        self._enforce_mute()

    def check_plugins_alive(self) -> bool:
        return all([p.alive for _, p in self.plugins.items()])

    def check_if_must_exit(self) -> None:
        # In replay mode, exit conditions are differents. Exit only if the Window is killed.
        if not Window.MainWindow.alive:
            self.exit()

    def update_time_string(self) -> None:
        time_str: str = self.get_time_hms_str()
        self.time.set_text(time_str)

    def get_time_hms_str(self) -> str:
        # round to prevent displaying time as 0.099 instead of 0.1
        timesec: float = round(self.replay_time, 2)

        t: str = strftime("%H:%M:%S", gmtime(timesec))
        ms: float = timesec % 1 * 1000

        return "%s.%03d" % (t, ms)

    def pause_if_end_reached(self) -> None:
        if self.replay_time >= self.logreader.session_duration and not self.is_paused:
            self.pause_playback()

    def pause_playback(self) -> None:
        self.is_paused = True
        self.playpause.update_button_sprite(True)

    def resume_playback(self) -> None:
        self.is_paused = False
        self.playpause.update_button_sprite(False)

    def toggle_mute(self) -> None:
        self._muted = not self._muted
        self.mute_button.update_mute_state(self._muted)
        self._enforce_mute()

    def _enforce_mute(self) -> None:
        if "communications" in self.plugins:
            player: Any = getattr(self.plugins["communications"], "player", None)
            if player is not None:
                player.volume = 0.0 if self._muted else 1.0

    def toggle_playpause(self) -> None:
        if self.is_paused:
            # If at the end, restart from beginning
            if self.replay_time >= self.logreader.session_duration:
                self.set_target_time(0)
            self.resume_playback()
            self.target_time = self.logreader.session_duration
        else:
            self.pause_playback()
            self.target_time = self.replay_time

    def slider_control_update(self) -> None:
        # At THE FIRST slider mouse press, save the play/pause state, then pause
        if self.slider.hover and not self.sliding:
            self.sliding = True
            self._was_paused_before_slide: bool = self.is_paused
            self.pause_playback()

        # Update the position of the slider if replay time changed (only when not interacting)
        if self.slider.groove_value != self.replay_time and not self.sliding:
            self.slider.groove_value = self.replay_time
            self.slider.set_groove_position()

        # At THE FIRST slider mouse release, navigate to the selected time
        # then restore the previous play/pause state
        if not self.slider.hover and self.sliding:
            self.sliding = False
            self.set_target_time(self.slider.groove_value)
            if not self._was_paused_before_slide:
                self.resume_playback()
                self.target_time = self.logreader.session_duration

    def pause_if_clock_target_reached(self) -> None:
        # Soon as the clock target is reached, control if the scenario must switch back to pause
        if self.clock.is_target_time_reached():
            self.clock.remove_target_time()
            self.pause_playback()

    def set_target_time(self, target_time: float) -> None:
        # We are already changing time, do not reenter this method
        if self.clock.isFastForward:
            return

        # clamp desired time
        self.target_time = clamp(target_time, 0, self.logreader.session_duration)

        # already on the right time
        if self.target_time == self.replay_time:
            self.pause_playback()
            return

        # backward in time, we reload everything, reset, and move forward
        if self.target_time < self.replay_time:
            self.restart_scenario()
            self.replay_time = 0

        forward_time: float = self.target_time - self.replay_time

        # Resuming is required as we want the clock to update the scheduler
        if forward_time > 0:
            self.resume_playback()
            self.clock.fastforward_time(forward_time)

        # After seeking: clean up blocking plugins/dialogs past their segment
        self._cleanup_after_seek()

        self.slider.set_groove_position()
        self.pause_playback()

    def _cleanup_after_seek(self) -> None:
        """Clean up stale blocking state after a seek (fastforward).

        Handles two cases:
        1. A BlockingPlugin (instructions, genericscales) still active after
           replay_time has moved past its blocking segment.
        2. A ModalDialog (system;pause) still showing after a seek.
        """
        # Case 1: stale blocking plugin
        active_blocking: Any = self.get_active_blocking_plugin()
        if active_blocking is not None:
            if not self.logreader.is_in_blocking_segment(self.replay_time):
                active_blocking.stop()
                if self.is_scenario_time_paused():
                    if len(self.paused_plugins) > 0:
                        self.execute_plugins_methods(
                            self.paused_plugins, methods=["show", "resume"]
                        )
                        self.paused_plugins = list()
                    self.resume_scenario()

        # Case 2: stale modal dialog (system;pause)
        if Window.MainWindow.modal_dialog is not None:
            Window.MainWindow.modal_dialog.on_delete()

    def restart_scenario(self) -> None:
        # we need to suspend the clock as it schedules old events
        self.clock.unschedule(self.update)

        self._executed_key_indices = set()
        self.keys_history = []
        self.clock.set_time(0)
        self.clock.tick()
        self.scenario_time = 0
        self.replay_time = 0
        self.slider.groove_value = 0
        self.slider.set_groove_position()
        self.scenario.reload_plugins()
        self.set_scenario()

        self.clock.schedule(self.update)

    def emulate_keyboard_inputs(self) -> None:
        lo: int = bisect_right(self._key_logtimes, self.replay_time - CLOCK_STEP)
        hi: int = bisect_right(self._key_logtimes, self.replay_time)

        for idx in range(lo, hi):
            if idx not in self._executed_key_indices:
                self._executed_key_indices.add(idx)
                input: dict[str, Any] = self.logreader.keyboard_inputs[idx]
                for _plugin_name, plugin in self.plugins.items():
                    plugin.do_on_key(input["address"], input["value"], True)

                cmd: str = f"{input['address']} ({input['value']})"
                if len(self.keys_history) == 0 or cmd != self.keys_history[-1]:
                    self.keys_history.append(cmd)
                if len(self.keys_history) > 30:
                    del self.keys_history[0]

        history_str: str = "<strong>Keyboard history:\n</strong>" + "<br>".join(self.keys_history)
        self.key_widget.set_text(history_str)

    def process_states(self) -> None:
        # States are displayed as a function of replay time (logtime-based).
        # It does not matter to display each and every states. Better is to catch
        # the most current one. The following states are manually handled:
        #   - 1. The cursor position in the tracking task
        #   - 2. The frequency of each communications radio
        #   - 3. The value of each slider, in genericscales

        lo: int = bisect_right(self._state_logtimes, self.replay_time - CLOCK_STEP)
        hi: int = bisect_right(self._state_logtimes, self.replay_time)

        for idx in range(lo, hi):
            state: dict[str, Any] = self.logreader.states[idx]

            # 1. Cursor position
            if "cursor_proportional" in state["address"] and "track" in self.plugins:
                track = self.plugins["track"]
                if not hasattr(track, "reticle"):
                    continue
                cursor_relative: tuple[float, float] = track.reticle.proportional_to_relative(state["value"])
                track.cursor_position = cursor_relative

            # 2. Radio frequencies
            elif "radio_frequency" in state["address"] and "communications" in self.plugins:
                radio_name: str = state["address"].replace(", radio_frequency", "").replace("radio_", "")
                radio: dict[str, Any] = self.plugins["communications"].get_radios_by_key_value("name", radio_name)[0]
                radio["currentfreq"] = state["value"]

            # 3. Genericscales slider values
            elif "slider_" in state["address"] and "genericscales" in self.plugins:
                slider_name: str = state["address"].replace(", value", "")
                slider: Any = self.plugins["genericscales"].sliders[slider_name]
                slider.groove_value = state["value"]
                slider.set_groove_position()

    def display_joystick_inputs(self) -> None:
        x: float | None = None
        y: float | None = None
        lo: int = bisect_right(self._joy_logtimes, self.replay_time - CLOCK_STEP)
        hi: int = bisect_right(self._joy_logtimes, self.replay_time)

        for idx in range(lo, hi):
            joy_input: dict[str, Any] = self.logreader.joystick_inputs[idx]

            # X case
            if "_x" in joy_input["address"]:
                x = float(joy_input["value"])
            elif "_y" in joy_input["address"]:
                y = float(joy_input["value"])

        if x is not None and y is not None:
            rel_x, rel_y = self.replay_reticle.proportional_to_relative((x, y))
            self.replay_reticle.set_cursor_position(rel_x, rel_y)

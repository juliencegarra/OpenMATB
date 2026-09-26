"""Behaviour tests for plugins.abstractplugin - real AbstractPlugin subclasses and BlockingPlugin slides."""

from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import key, mouse

from core.constants import BFLIM
from core.constants import COLORS as C
from core.container import Container
from plugins import abstractplugin
from plugins.abstractplugin import AbstractPlugin, BlockingPlugin
from plugins.instructions import Instructions


class Dummy(AbstractPlugin):
    """Minimal concrete plugin whose response timers can be set by the tests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timers = None
        self.fault = False
        self.mouse_calls = []

    def get_response_timers(self):
        return self.timers

    def has_active_fault(self):
        return self.fault

    def do_on_mouse_press(self, x, y, button):
        self.mouse_calls.append(("press", x, y, button))

    def do_on_mouse_release(self, x, y, button):
        self.mouse_calls.append(("release", x, y, button))

    def do_on_mouse_drag(self, x, y, dx, dy, buttons):
        self.mouse_calls.append(("drag", x, y, dx, dy, buttons))


def _new_widget(fullname, container, **kwargs):
    w = MagicMock(name=fullname)
    w.kwargs = kwargs
    return w


@pytest.fixture
def window():
    """A mock main window without modal dialog, giving real containers."""
    with patch("plugins.abstractplugin.Window") as mock_win:
        mw = mock_win.MainWindow
        mw.modal_dialog = None
        mw.keyboard = {}
        mw.get_container.side_effect = lambda placement: Container(placement, 0, 0, 1000, 800)
        yield mw


@pytest.fixture
def widgets():
    """Widget classes replaced by factories of distinct mocks."""
    with (
        patch("plugins.abstractplugin.Frame", side_effect=_new_widget) as frame,
        patch("plugins.abstractplugin.Simpletext", side_effect=_new_widget) as text,
        patch("plugins.abstractplugin.SimpleHTML", side_effect=_new_widget) as html,
        patch("plugins.instructions.SimpleHTML", side_effect=_new_widget) as instr_html,
    ):
        yield dict(Frame=frame, Simpletext=text, SimpleHTML=html, InstrHTML=instr_html)


@pytest.fixture
def plugin(mock_logger, window, widgets):
    """A started Dummy plugin placed in the top-left area."""
    p = Dummy(label="Dummy task", taskplacement="topleft", taskupdatetime=100)
    p.joystick = None
    p.start()
    return p


@pytest.fixture
def fullscreen(mock_logger, window, widgets):
    p = Dummy(label="Full", taskplacement="fullscreen")
    p.joystick = None
    return p


# ---------------------------------------------------------------- AbstractPlugin


class TestInit:
    def test_defaults(self, mock_logger):
        """A new plugin is paused, hidden, not alive, with overdue feedback inactive."""
        p = Dummy(label="X", taskplacement="topright")
        assert p.alias == "dummy"
        assert p.paused and not p.visible and not p.alive
        assert p.parameters["taskfeedback"]["overdue"]["active"] is False
        assert p.m_draw == 0
        assert p.display_title is True

    def test_fullscreen_draw_order_and_invisible_title(self, mock_logger):
        """Fullscreen plugins draw above the bands; invisible plugins have no title."""
        assert Dummy(taskplacement="fullscreen").m_draw == BFLIM
        assert Dummy(taskplacement="invisible").display_title is False

    def test_base_hooks_do_nothing(self, mock_logger):
        """Base on_scenario_loaded / response timers / mouse hooks return None."""
        p = AbstractPlugin()
        assert p.on_scenario_loaded(MagicMock()) is None
        assert p.get_response_timers() is None
        assert p.has_active_fault() is False
        assert p.do_on_mouse_press(1, 2, mouse.LEFT) is None
        assert p.do_on_mouse_release(1, 2, mouse.LEFT) is None
        assert p.do_on_mouse_drag(1, 2, 3, 4, mouse.LEFT) is None


class TestLifecycle:
    def test_start_creates_widgets_logs_and_runs(self, plugin, mock_logger):
        """start() creates the widgets, logs every parameter, shows and resumes the plugin."""
        assert plugin.alive and plugin.visible and not plugin.paused
        names = set(plugin.widgets)
        assert {"dummy_foreground", "dummy_overdue", "dummy_attention", "dummy_fault_icon", "dummy_task_title"} <= names
        logged = {c.args[1]: c.args[2] for c in mock_logger.record_parameter.call_args_list}
        assert logged["title"] == "Dummy task"
        assert logged["taskfeedback-overdue-delayms"] == 2000
        assert mock_logger.record_aoi.called

    def test_show_hides_foreground_and_feedback(self, plugin):
        """Showing a windowed plugin removes the foreground mask and resets feedback widgets."""
        plugin.get_widget("foreground").hide.assert_called()
        plugin.get_widget("overdue").set_visibility.assert_called_with(False)
        plugin.get_widget("attention").set_visibility.assert_called_with(False)
        plugin.get_widget("fault_icon").set_text.assert_called_with("")

    def test_show_twice_is_noop(self, plugin):
        """Showing an already visible plugin does nothing."""
        plugin.get_widget("foreground").hide.reset_mock()
        plugin.show()
        plugin.get_widget("foreground").hide.assert_not_called()

    def test_stop_pauses_and_masks(self, plugin):
        """stop() pauses, hides the title and puts the foreground back."""
        plugin.stop()
        assert not plugin.alive and plugin.paused and not plugin.visible
        plugin.get_widget("task_title").hide.assert_called()
        plugin.get_widget("foreground").show.assert_called()
        assert not plugin.can_receive_keys and not plugin.can_receive_mouse

    def test_hide_twice_is_noop(self, plugin):
        """Hiding a hidden plugin does nothing."""
        plugin.hide()
        plugin.get_widget("task_title").hide.reset_mock()
        plugin.hide()
        plugin.get_widget("task_title").hide.assert_not_called()

    def test_hide_also_hides_status_title(self, plugin, widgets):
        """A status title (resman) is hidden with the task title."""
        plugin.add_widget("status_title", widgets["Simpletext"], None)
        plugin.hide()
        plugin.get_widget("status_title").hide.assert_called()

    def test_fullscreen_show_hide_toggles_bands(self, fullscreen, window):
        """A fullscreen plugin hides the background bands while shown."""
        fullscreen.start()
        assert "dummy_background" in fullscreen.widgets
        window.set_bg_bands_visible.assert_called_with(False)
        fullscreen.stop()
        window.set_bg_bands_visible.assert_called_with(True)
        fullscreen.get_widget("background").hide.assert_called()

    def test_invisible_plugin_has_no_widgets(self, mock_logger, window, widgets):
        """An invisible plugin creates no widget and shows/hides without error."""
        p = Dummy(taskplacement="invisible")
        p.start()
        assert p.widgets == {}
        assert p.visible
        p.stop()
        assert not p.visible

    def test_verbose_prints_state_changes(self, mock_logger, window, widgets, capsys):
        """Verbose plugins print their state changes."""
        p = Dummy(label="V", taskplacement="topleft", taskupdatetime=10)
        p.verbose = True
        p.start()
        p.update(1.0)
        p.stop()
        out = capsys.readouterr().out
        for word in ("Start", "with keys", "Creating widgets", "Show", "Resume", "Compute next state"):
            assert word in out
        assert "Refreshing widgets" in out and "Pause" in out and "Hide" in out and "Stop" in out


class TestAutomationState:
    def test_automode_widget_created_at_position(self, mock_logger, window, widgets):
        """displayautomationstate creates an automode label at the plugin's automode position."""
        p = Dummy(label="A", taskplacement="topleft")
        p.parameters["displayautomationstate"] = True
        p.automode_position = (0.2, 0.8)
        p.start()
        assert p.get_widget("automode") is not None

    def test_automode_widget_default_position(self, mock_logger, window, widgets):
        """Without automode_position the label is centered."""
        p = Dummy(label="A", taskplacement="topleft")
        p.parameters["displayautomationstate"] = True
        p.start()
        assert p.get_widget("automode").kwargs["x"] == 0.5

    def test_no_automode_widget_when_disabled(self, mock_logger, window, widgets):
        p = Dummy(label="A", taskplacement="topleft")
        p.parameters["displayautomationstate"] = False
        p.start()
        assert p.get_widget("automode") is None

    def test_manual_string_without_automaticsolver(self, plugin):
        """A plugin without automaticsolver displays MANUAL and refreshes the automode label."""
        plugin.parameters["displayautomationstate"] = True
        plugin.add_widget("automode", MagicMock(side_effect=_new_widget), None)
        plugin.update(1.0)
        assert plugin.automode_string == "MANUAL"
        plugin.get_widget("automode").set_text.assert_called_with("MANUAL")

    def test_manual_string_when_solver_off(self, plugin):
        plugin.parameters.update(displayautomationstate=True, automaticsolver=False)
        plugin.update(1.0)
        assert plugin.automode_string == "MANUAL"

    def test_agent_string_when_solver_on(self, plugin):
        """With an active solver the agent acts and gives the automation string."""
        agent = MagicMock(allows_human_input=False)
        agent.get_automode_string.return_value = "AUTO ON"
        plugin.agent = agent
        plugin.parameters.update(displayautomationstate=True, automaticsolver=True)
        plugin.update(1.0)
        agent.on_plugin_update.assert_called_once_with(plugin, 1.0)
        assert plugin.automode_string == "AUTO ON"

    def test_empty_string_when_not_displayed(self, plugin):
        plugin.automode_string = "X"
        plugin.update(1.0)
        assert plugin.automode_string == ""


class TestUpdateSteps:
    def test_steps_are_caught_up(self, plugin):
        """Several late steps are computed in one update."""
        plugin.update(1.0)  # first step: deadlines start now
        assert plugin.next_refresh_time == pytest.approx(1.1)
        with patch.object(plugin, "compute_next_plugin_state", wraps=plugin.compute_next_plugin_state) as step:
            plugin.update(1.25)
        assert step.call_count == 2  # steps of 1.1 and 1.2 were both due
        assert plugin.next_refresh_time == pytest.approx(1.3)

    def test_long_stall_restarts_from_now(self, plugin):
        """After a long stall, the next deadline is computed from now."""
        plugin.update(1.0)
        plugin.update(10.0)
        assert plugin.next_refresh_time == pytest.approx(10.1)

    def test_paused_plugin_does_not_step(self, plugin):
        plugin.pause()
        assert plugin.compute_next_plugin_state() is False

    def test_hidden_plugin_does_not_refresh(self, plugin):
        plugin.hide()
        assert plugin.refresh_widgets() is False

    def test_refresh_sets_title(self, plugin):
        plugin.update(1.0)
        plugin.get_widget("task_title").set_text.assert_called_with("DUMMY TASK")


class TestInputPermissions:
    def test_running_plugin_receives_everything(self, plugin):
        assert plugin.can_receive_keys and plugin.can_execute_keys and plugin.can_receive_mouse

    def test_solver_blocks_human_but_executes(self, plugin):
        """An automatic solver blocks human keys and mouse but executes emulated keys."""
        plugin.parameters["automaticsolver"] = True
        plugin.update_can_receive_key()
        assert not plugin.can_receive_keys and plugin.can_execute_keys and not plugin.can_receive_mouse

    def test_agent_may_allow_human_input(self, plugin):
        """An agent allowing human input lets keys through while the plugin runs."""
        plugin.parameters["automaticsolver"] = True
        plugin.agent = MagicMock(allows_human_input=True)
        plugin.update_can_receive_key()
        assert plugin.can_receive_keys and plugin.can_execute_keys

    def test_replay_blocks_human_keys(self, plugin):
        with patch.object(abstractplugin, "REPLAY_MODE", True):
            plugin.update_can_receive_key()
        assert not plugin.can_receive_keys and plugin.can_execute_keys and not plugin.can_receive_mouse


class TestKeys:
    def test_filter_key(self, plugin, window):
        """Only the plugin keys pass, and none while a modal dialog is open."""
        plugin.keys = {"UP"}
        assert plugin.filter_key("UP") == "UP"
        assert plugin.filter_key("DOWN") is None
        window.modal_dialog = MagicMock()
        assert plugin.filter_key("UP") is None
        plugin.can_execute_keys = False
        window.modal_dialog = None
        assert plugin.filter_key("UP") is None

    def test_key_and_joystick_events_reach_do_on_key(self, plugin):
        """Keyboard and joystick events are forwarded as key strings with their state."""
        with patch.object(plugin, "do_on_key") as dok:
            plugin.on_key_press(key.SPACE, 0)
            plugin.on_key_release(key.SPACE, 0)
            plugin.on_joy_key_press("JOY1")
            plugin.on_joy_key_release("JOY1")
        assert [c.args for c in dok.call_args_list] == [
            ("SPACE", "press", False),
            ("SPACE", "release", False),
            ("JOY1", "press", False),
            ("JOY1", "release", False),
        ]

    def test_events_ignored_when_not_receiving(self, plugin):
        plugin.pause()
        with patch.object(plugin, "do_on_key") as dok:
            plugin.on_key_press(key.SPACE, 0)
            plugin.on_key_release(key.SPACE, 0)
            plugin.on_joy_key_press("JOY1")
            plugin.on_joy_key_release("JOY1")
        dok.assert_not_called()

    def test_replay_ignores_real_keys_only(self, plugin):
        """In replay, non-emulated keys are dropped and emulated keys are filtered."""
        plugin.keys = {"UP"}
        with patch.object(abstractplugin, "REPLAY_MODE", True):
            assert plugin.do_on_key("UP", "press") is None
            assert plugin.do_on_key("UP", "press", emulate=True) == "UP"

    def test_is_key_state(self, plugin, window):
        """Key states come from the keyboard, then from the joystick, else None."""
        window.keyboard = {"UP": True}
        assert plugin.is_key_state("UP", True) is True
        assert plugin.is_key_state("UP", False) is False
        plugin.joystick = MagicMock(keys={"JOY1": False})
        assert plugin.is_key_state("JOY1", False) is True
        assert plugin.is_key_state("NONE", True) is None
        plugin.joystick = None
        assert plugin.is_key_state("JOY1", True) is None


class TestMouse:
    def test_mouse_events_forwarded(self, plugin):
        plugin.on_mouse_press(1, 2, mouse.LEFT, 0)
        plugin.on_mouse_release(3, 4, mouse.LEFT, 0)
        plugin.on_mouse_drag(5, 6, 1, 1, mouse.LEFT, 0)
        assert [c[0] for c in plugin.mouse_calls] == ["press", "release", "drag"]

    def test_mouse_ignored_under_modal_dialog(self, plugin, window):
        window.modal_dialog = MagicMock()
        plugin.on_mouse_press(1, 2, mouse.LEFT, 0)
        plugin.on_mouse_release(1, 2, mouse.LEFT, 0)
        plugin.on_mouse_drag(1, 2, 1, 1, mouse.LEFT, 0)
        assert plugin.mouse_calls == []

    def test_mouse_ignored_when_paused(self, plugin):
        plugin.pause()
        plugin.on_mouse_press(1, 2, mouse.LEFT, 0)
        plugin.on_mouse_release(1, 2, mouse.LEFT, 0)
        plugin.on_mouse_drag(1, 2, 1, 1, mouse.LEFT, 0)
        assert plugin.mouse_calls == []


class TestOverdueFeedback:
    @pytest.fixture
    def overdue(self, plugin):
        od = plugin.parameters["taskfeedback"]["overdue"]
        od.update(active=True, delayms=2000, blinkdurationms=1000)
        return od

    def _refresh(self, plugin, t):
        plugin.scenario_time = t
        plugin.refresh_widgets()
        return plugin.parameters["taskfeedback"]["overdue"]["_is_visible"]

    def test_no_alarm_below_delay(self, plugin, overdue):
        plugin.timers = [1000]
        assert self._refresh(plugin, 5) is False

    def test_no_alarm_when_inactive(self, plugin, overdue):
        overdue["active"] = False
        plugin.timers = [5000]
        assert self._refresh(plugin, 5) is False

    def test_steady_alarm_without_blink(self, plugin, overdue):
        overdue["blinkdurationms"] = 0
        plugin.timers = [5000]
        assert self._refresh(plugin, 5) is True
        assert self._refresh(plugin, 5.5) is True
        overdue["widget"].set_visibility.assert_called_with(True)
        overdue["widget"].set_border_color.assert_called_with(C["RED"])

    def test_alarm_blinks(self, plugin, overdue):
        """The alarm toggles every blinkdurationms once a response is overdue."""
        plugin.timers = [3000]
        assert [self._refresh(plugin, t) for t in (10, 10.5, 11, 11.5, 12)] == [True, True, False, False, True]

    def test_alarm_stops_when_answered(self, plugin, overdue):
        plugin.timers = [3000]
        self._refresh(plugin, 10)
        plugin.timers = [0]
        assert self._refresh(plugin, 10.1) is False

    def test_second_alarm_blinks_at_normal_rate(self, plugin, overdue):
        """A later overdue episode blinks at blinkdurationms, not at every refresh."""
        plugin.timers = [3000]
        self._refresh(plugin, 10)
        plugin.timers = [0]
        self._refresh(plugin, 10.5)
        plugin.timers = [3000]
        assert [self._refresh(plugin, t) for t in (20, 20.02, 20.04)] == [True, True, True]


class TestAttentionAndFault:
    def test_attention_frame_follows_attended_task(self, plugin):
        plugin.agent = MagicMock(show_attention=True, _attended_task="dummy")
        plugin.refresh_widgets()
        plugin.get_widget("attention").set_visibility.assert_called_with(True)
        plugin.agent._attended_task = "other"
        plugin.refresh_widgets()
        plugin.get_widget("attention").set_visibility.assert_called_with(False)

    def test_fault_icon_shown_on_active_fault(self, plugin):
        plugin.agent = MagicMock(show_attention=True)
        plugin.fault = True
        plugin.refresh_widgets()
        plugin.get_widget("fault_icon").set_text.assert_called_with("!")
        plugin.agent = None
        plugin.refresh_widgets()
        plugin.get_widget("fault_icon").set_text.assert_called_with("")


class TestParameters:
    def test_set_nested_parameter(self, plugin):
        dic = plugin.set_parameter("taskfeedback-overdue-delayms", 500)
        assert plugin.parameters["taskfeedback"]["overdue"]["delayms"] == 500
        assert dic is plugin.parameters["taskfeedback"]["overdue"]

    def test_set_key_parameter_renews_keys(self, plugin):
        """Changing a key parameter replaces the old key by the new one."""
        plugin.parameters["keys"] = {"up": "UP"}
        plugin.keys = {"UP"}
        plugin.set_parameter("keys-up", "W")
        assert plugin.keys == {"W"}
        plugin.set_parameter("keys-up", "W")
        assert plugin.keys == {"W"}

    def test_set_parameter_unknown_key_raises(self, plugin):
        with pytest.raises(KeyError):
            plugin.set_parameter("nothere", 1)

    def test_log_performance(self, plugin, mock_logger):
        plugin.log_performance("rt", 10)
        plugin.log_performance("rt", 20)
        assert plugin.performance == {"rt": [10, 20]}
        mock_logger.log_performance.assert_called_with("dummy", "rt", 20)


class TestHelpers:
    def test_filters(self):
        coll = {"a": {"k": 1}, "b": {"k": 2}}
        assert AbstractPlugin._filter_by(coll, "k", 1) == [{"k": 1}]
        assert AbstractPlugin._filter_by([{"k": 2}], "k", 2) == [{"k": 2}]
        assert AbstractPlugin._filter_keys_by(coll, "k", 2) == ["b"]

    def test_indexed_validators(self):
        v = object()
        assert AbstractPlugin._indexed_validators("pump", range(1, 3), {"flow": v}) == {
            "pump-1-flow": v,
            "pump-2-flow": v,
        }

    def test_elapsed_clamp_grouped(self, plugin):
        plugin.scenario_time = 3
        assert plugin._response_elapsed_ms(None) == 0.0
        assert plugin._response_elapsed_ms(1) == 2000
        assert plugin.keep_value_between(5, 0, 3) == 3
        assert plugin.keep_value_between(-1, 0, 3) == 0
        assert list(plugin.grouped([1, 2, 3, 4], 2)) == [(1, 2), (3, 4)]


# ---------------------------------------------------------------- BlockingPlugin


def _write_slides(tmp_path, text):
    path = tmp_path / "slides.txt"
    path.write_text(text, encoding="utf8")
    return path


@pytest.fixture
def make_instructions(mock_logger, window, widgets, tmp_path):
    """Build a started Instructions plugin reading the given slide text."""

    def _make(text, **params):
        ins = Instructions()
        ins.joystick = None
        ins.parameters["filename"] = str(_write_slides(tmp_path, text))
        ins.parameters.update(params)
        ins.start()
        return ins

    return _make


SLIDES = "<h1>Welcome</h1>\nFirst page\n# a comment\n<newpage>\nSecond page\n\n<newpage>\n<h1>End</h1>\nBye\n"


class TestBlockingInit:
    def test_defaults(self, mock_logger):
        """A blocking plugin blocks, has no title, listens to SPACE and validates its parameters."""
        b = BlockingPlugin()
        assert b.blocking and not b.display_title and b.stop_on_end
        assert b.keys == {"SPACE"}
        assert b.parameters["taskupdatetime"] == 15 and b.parameters["boldtitle"] is False
        assert {"filename", "allowkeypress", "response-key"} <= set(b.validation_dict)


class TestSlides:
    def test_file_split_into_slides_without_comments(self, make_instructions):
        """<newpage> splits slides and comment lines (#) are dropped."""
        ins = make_instructions(SLIDES)
        assert ins.slides == ["<h1>Welcome</h1>\nFirst page\n", "Second page\n\n", "<h1>End</h1>\nBye\n"]
        assert ins.go_to_next_slide is True

    def test_empty_lines_can_be_ignored(self, mock_logger, window, widgets, tmp_path):
        ins = Instructions()
        ins.ignore_empty_lines = True
        ins.parameters["filename"] = str(_write_slides(tmp_path, "A\n\n  \nB\n"))
        ins.start()
        assert ins.slides == ["A\nB\n"]

    def test_missing_or_absent_file_gives_no_slide(self, mock_logger, window, widgets, tmp_path):
        ins = Instructions()
        ins.start()
        assert ins.slides == [] and ins.input_path is None
        ins2 = Instructions()
        ins2.parameters["filename"] = str(tmp_path / "missing.txt")
        ins2.start()
        assert ins2.slides == []

    def test_first_update_shows_first_slide_with_title(self, make_instructions):
        """The first update displays slide 1: its <h1> becomes the title and the SPACE hint is added."""
        ins = make_instructions(SLIDES)
        ins.update(0.0)
        assert ins.current_slide == "First page\n"
        assert ins.get_widget("title").kwargs["text"] == "<h1>Welcome</h1>"
        assert "Press SPACE to continue" in ins.get_widget("press_space").kwargs["text"]
        assert ins.get_widget("instructions").kwargs["text"] == "First page\n"
        assert len(ins.slides) == 2 and ins.visible

    def test_last_h1_is_the_title(self, make_instructions):
        ins = make_instructions("<h1>A</h1>\n<h1>B</h1>\ntext\n")
        ins.update(0.0)
        assert ins.get_widget("title").kwargs["text"] == "<h1>B</h1>"
        assert ins.current_slide == "<h1>A</h1>\ntext\n"

    def test_space_release_goes_to_next_slide(self, make_instructions):
        """Releasing SPACE advances one slide; the previous title is removed."""
        ins = make_instructions(SLIDES)
        ins.update(0.0)
        ins.on_key_press(key.SPACE, 0)
        assert ins.go_to_next_slide is False
        ins.on_key_release(key.SPACE, 0)
        assert ins.go_to_next_slide is True
        ins.update(0.1)
        assert ins.current_slide == "Second page\n\n"
        assert ins.get_widget("title") is None

    def test_other_keys_do_not_advance(self, make_instructions):
        ins = make_instructions(SLIDES)
        ins.update(0.0)
        ins.on_key_release(key.ENTER, 0)
        assert ins.go_to_next_slide is False

    def test_stops_after_last_slide(self, make_instructions):
        ins = make_instructions("only\n")
        ins.update(0.0)
        ins.do_on_key("SPACE", "release", emulate=True)
        ins.update(0.1)
        assert not ins.alive and not ins.visible and ins.paused

    def test_no_stop_on_end_just_unblocks(self, make_instructions):
        """With stop_on_end False, the plugin is hidden and stops blocking but stays alive."""
        ins = make_instructions("only\n")
        ins.stop_on_end = False
        ins.update(0.0)
        ins.go_to_next_slide = True
        ins.update(0.1)
        assert ins.alive and not ins.visible and not ins.blocking

    def test_keypress_disabled_hides_hint_and_ignores_press(self, make_instructions):
        """allowkeypress False: no SPACE hint, key presses ignored."""
        ins = make_instructions(SLIDES, allowkeypress=False)
        ins.update(0.0)
        assert ins.get_widget("press_space") is None
        with patch.object(ins, "do_on_key") as dok:
            ins.on_key_press(key.SPACE, 0)
        dok.assert_not_called()

    def test_keypress_disabled_blocks_space_release(self, make_instructions):
        """With allowkeypress False, releasing SPACE must not advance the slides."""
        ins = make_instructions(SLIDES, allowkeypress=False)
        ins.update(0.0)
        ins.on_key_release(key.SPACE, 0)
        assert ins.go_to_next_slide is not True

    def test_headless_advances_automatically(self, make_instructions):
        ins = make_instructions(SLIDES)
        with patch.object(abstractplugin, "HEADLESS_MODE", True):
            for t in range(4):
                ins.update(t / 10)
        assert not ins.alive

    def test_title_removed_for_any_blocking_plugin(self, mock_logger, window, widgets, tmp_path):
        """A slide without <h1> must not show the title of the previous slide (non-Instructions plugin)."""

        class Questionnaire(BlockingPlugin):
            def __init__(self):
                super().__init__()
                self.parameters.update(filename=None, allowkeypress=False, response=dict(text="", key="SPACE"))

        q = Questionnaire()
        q.folder = ""  # The filename below is an absolute path
        q.joystick = None
        q.parameters["filename"] = str(_write_slides(tmp_path, "<h1>T</h1>\na\n<newpage>\nb\n"))
        q.start()
        q.update(0.0)
        title = q.get_widget("title")
        q.go_to_next_slide = True
        q.update(0.1)
        assert q.get_widget("title") is None
        assert title.show.call_count == 1

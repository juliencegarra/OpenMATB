"""Tests for small plugins built by their constructors: instructions, generictrigger, parallelport."""

from unittest.mock import MagicMock, patch

import pytest
from pyglet.window import key

from core.constants import PATHS as P
from core.container import Container
from plugins.generictrigger import Generictrigger
from plugins.instructions import Instructions
from plugins.parallelport import Parallelport


def _widget_class():
    """A mock widget class whose instances remember their name, container and keyword arguments."""

    def build(name, container, **kwargs):
        w = MagicMock()
        w.fullname, w.container, w.kwargs = name, container, kwargs
        return w

    return MagicMock(side_effect=build)


@pytest.fixture
def make_instructions(mock_logger, tmp_path):
    """Build an Instructions plugin reading a file written in tmp_path, with mock window and widgets."""
    with (
        patch("plugins.abstractplugin.Window") as mock_win,
        patch("plugins.abstractplugin.Frame", _widget_class()),
        patch("plugins.abstractplugin.SimpleHTML", _widget_class()),
        patch("plugins.instructions.SimpleHTML", _widget_class()),
    ):
        mock_win.MainWindow.modal_dialog = None
        mock_win.MainWindow.keyboard = {}
        mock_win.MainWindow.get_container.side_effect = lambda placement: Container(placement, 0, 0, 1920, 1080)

        def make(content, **parameters):
            (tmp_path / "instructions.txt").write_text(content, encoding="utf8")
            ins = Instructions()
            ins.folder = str(tmp_path)
            ins.parameters["filename"] = "instructions.txt"
            ins.parameters.update(parameters)
            return ins

        yield make


def _press_space(plugin):
    plugin.on_key_press(key.SPACE, 0)
    plugin.on_key_release(key.SPACE, 0)


class TestInstructions:
    def test_default_parameters(self, mock_logger):
        ins = Instructions()
        assert ins.folder == P["INSTRUCTIONS"]
        assert ins.parameters["filename"] is None
        assert ins.parameters["response"] == {"text": "Press SPACE to continue", "key": "SPACE"}
        assert ins.parameters["allowkeypress"] is True
        assert ins.blocking is True
        assert ins.keys == {"SPACE"}

    def test_pages_are_displayed_one_after_the_other(self, make_instructions):
        ins = make_instructions("<h1>Welcome</h1>\n<p>First page</p>\n<newpage>\n<p>Second page</p>\n")
        ins.start()
        ins.update(1)
        page = ins.widgets["instructions_instructions"]
        assert "<p>First page</p>" in page.kwargs["text"]
        assert "<h1>" not in page.kwargs["text"]
        assert ins.widgets["instructions_title"].kwargs["text"] == "<h1>Welcome</h1>"
        assert page.container is ins.container

        _press_space(ins)
        ins.update(2)
        assert "<p>Second page</p>" in ins.widgets["instructions_instructions"].kwargs["text"]
        assert "instructions_title" not in ins.widgets  # The previous title is removed

        _press_space(ins)
        ins.update(3)
        assert not ins.alive

    def test_no_response_text_when_keypress_is_not_allowed(self, make_instructions):
        ins = make_instructions("<p>Only page</p>\n", allowkeypress=False)
        ins.start()
        ins.update(1)
        assert "instructions_press_space" not in ins.widgets
        assert "instructions_instructions" in ins.widgets

    def test_space_is_ignored_when_keypress_is_not_allowed(self, make_instructions):
        ins = make_instructions("<p>Only page</p>\n", allowkeypress=False)
        ins.start()
        ins.update(1)
        _press_space(ins)
        ins.update(2)
        assert ins.alive


class TestMaxDuration:
    """maxdurationsec: each page is shown at most that long (real time: the scenario time is paused)."""

    def _run(self, ins, clock, times):
        for t in times:
            clock.return_value = t
            ins.update(1)

    def test_each_page_is_shown_at_most_maxdurationsec(self, make_instructions, mock_logger):
        ins = make_instructions("<p>First</p>\n<newpage>\n<p>Second</p>\n", maxdurationsec=2, allowkeypress=False)
        ins.start()
        with patch("plugins.abstractplugin.perf_counter") as clock:
            self._run(ins, clock, [100, 101, 101.9])
            assert "<p>First</p>" in ins.widgets["instructions_instructions"].kwargs["text"]
            self._run(ins, clock, [102.1, 102.2])
            assert "<p>Second</p>" in ins.widgets["instructions_instructions"].kwargs["text"]
            self._run(ins, clock, [104.3, 104.4])
        assert not ins.alive
        # Logged, so that the replay ends the pages at the same times, and the analysis knows it
        timeouts = [c for c in mock_logger.record_input.call_args_list if c.args[0] == "timeout"]
        assert [c.args for c in timeouts] == [("timeout", "instructions", "1"), ("timeout", "instructions", "2")]
        assert ins.performance["page_timeout"] == [1, 2]

    def test_no_limit_by_default(self, make_instructions):
        ins = make_instructions("<p>Only page</p>\n")
        ins.start()
        with patch("plugins.abstractplugin.perf_counter") as clock:
            self._run(ins, clock, [0, 1000, 2000])
        assert ins.alive

    def test_time_paused_is_not_counted(self, make_instructions):
        """The pause dialog pauses the plugin: the page is not ended during it."""
        ins = make_instructions("<p>Only page</p>\n", maxdurationsec=2)
        ins.start()
        with patch("plugins.abstractplugin.perf_counter") as clock:
            self._run(ins, clock, [0, 1])
            ins.pause()
            clock.return_value = 30
            ins.resume()
            self._run(ins, clock, [30, 30.5])
            assert ins.alive
            self._run(ins, clock, [31.1, 31.2])  # The next page (none: the end) at the next update
        assert not ins.alive

    def test_replay_ends_the_page_with_the_logged_timeout_only(self, make_instructions):
        ins = make_instructions("<p>Only page</p>\n", maxdurationsec=1)
        ins.start()
        with patch("plugins.abstractplugin.REPLAY_MODE", True), patch("plugins.abstractplugin.perf_counter") as clock:
            self._run(ins, clock, [0, 10, 20])
        assert ins.alive


class TestGenerictrigger:
    def test_default_parameters(self, mock_logger):
        trigger = Generictrigger()
        assert trigger.label == "Generic Trigger"
        assert trigger.parameters["taskplacement"] == "invisible"
        assert trigger.parameters["taskupdatetime"] == 5
        assert trigger.parameters["state"] == ""
        assert trigger.display_title is False
        assert set(trigger.validation_dict) == {"state"}

    def test_state_can_be_set(self, mock_logger):
        trigger = Generictrigger()
        trigger.set_parameter("state", "stimulus_on")
        assert trigger.parameters["state"] == "stimulus_on"


class TestParallelportStep:
    def test_no_trigger_is_sent_before_the_next_step(self, mock_logger):
        """Between two steps (or while paused), the port is left untouched."""
        with patch("plugins.parallelport.sys") as mock_sys:
            mock_sys.platform = "darwin"  # No hardware access
            with patch("plugins.parallelport.get_errors"):
                pp = Parallelport()
        pp._port = MagicMock()
        pp.parameters["trigger"] = 8
        pp.update(1)  # Paused
        pp._port.setData.assert_not_called()
        assert pp.parameters["trigger"] == 8

        pp.resume()
        pp.update(1)
        pp._port.setData.assert_called_once_with(8)


class TestBlockingPluginFolders:
    """Each blocking plugin reads its file in its own folder: the scenario checks it there."""

    @pytest.mark.parametrize(
        "plugin_class, good, bad",
        [
            ("Instructions", "default_en/welcome_screen.txt", "nasatlx_en.txt"),
            ("Genericscales", "nasatlx_en.txt", "default_en/welcome_screen.txt"),
        ],
    )
    def test_filename_is_checked_in_the_plugin_folder(self, plugin_class, good, bad, mock_logger):
        import plugins

        method, *args = getattr(plugins, plugin_class)().validation_dict["filename"]
        assert method(good, *args) == (good, None)
        assert method(bad, *args)[0] is None


def test_genericscales_showvalue_can_be_set_in_a_scenario(mock_logger):
    """showvalue had no validator: genericscales;showvalue;True made the scenario fail (no verification method)."""
    from plugins.genericscales import Genericscales

    validator = Genericscales().validation_dict["showvalue"]
    assert validator("True") == (True, None)
    assert validator("maybe")[0] is None

"""Browser (Pyodide) specific code, tested with fake `js` / `pyodide` modules.

Covers the work-arounds of core.platform.setup_web() (each one fixes a crash or a freeze seen in the
browser), the page helpers, and the browser branches of the joystick, logger, window, scheduler and
web build.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import core.platform as platform

ROOT: Path = Path(__file__).resolve().parent.parent


# ── Fake browser modules ────────────────────────────────────────────────────


class JsNull:
    """pyodide.ffi.jsnull: what Pyodide gives for a JavaScript null. Falsy, but not None."""

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str):
        raise AttributeError(f"'JsNull' object has no attribute '{name}'")


class JsArray:
    """A JavaScript array proxy: indexable, with .length."""

    def __init__(self, items: list) -> None:
        self._items = items
        self.length = len(items)

    def __getitem__(self, i: int):
        return self._items[i]


def _module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


@pytest.fixture
def js():
    """A fake `js` module (the browser globals), installed with pyodide.ffi, in browser mode."""
    document = MagicMock(name="document")
    document.visibilityState = "visible"
    fake_js = _module(
        "js",
        document=document,
        window=SimpleNamespace(location=SimpleNamespace(search=""), innerWidth=1280, innerHeight=720),
        navigator=SimpleNamespace(getGamepads=lambda: JsArray([JsNull(), JsNull(), JsNull(), JsNull()])),
        Blob=MagicMock(name="Blob"),
        URL=MagicMock(name="URL"),
        CustomEvent=MagicMock(name="CustomEvent"),
        Object=SimpleNamespace(fromEntries=dict),
    )
    ffi = _module("pyodide.ffi", create_proxy=lambda f: f, to_js=lambda v, **kw: v, jsnull=JsNull())
    pyodide = _module("pyodide", ffi=ffi)
    with (
        patch.dict(sys.modules, {"js": fake_js, "pyodide": pyodide, "pyodide.ffi": ffi}),
        patch.object(platform, "IS_WEB", True),
    ):
        yield fake_js


# ── setup_web(): work-arounds for pyglet 3 / Pyodide ───────────────────────


class FakeWebLoop:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def call_later(self, delay, callback, *args, **kwargs):
        if delay < 0:
            raise ValueError("Can't schedule in the past")
        self.calls.append((delay, callback, args, kwargs))
        return "handle"


class FakeBufferView:
    """pyglet.libs.emscripten.PersistentBufferView: keeps a JS view of the WebAssembly memory."""

    def __init__(self, proxy) -> None:
        self._proxy = proxy
        self._buffer = proxy.getBuffer("u8")
        self.data = self._buffer.data


def _js_view(detached: bool = False):
    size = 0 if detached else 64
    return SimpleNamespace(byteLength=size, buffer=SimpleNamespace(byteLength=size))


class FakeDomain:
    def _has_multi_draw_extension(self, ctx) -> bool:
        return True


@pytest.fixture
def web_modules(js):
    """Fake pyodide.webloop and the pyglet browser modules patched by setup_web()."""
    webloop = _module("pyodide.webloop", WebLoop=type("WebLoop", (FakeWebLoop,), {}))
    emscripten_libs = _module("pyglet.libs.emscripten", PersistentBufferView=type("View", (FakeBufferView,), {}))
    vertexdomain = _module(
        "pyglet.graphics.api.webgl.vertexdomain",
        WebGLVertexDomain=type("WebGLVertexDomain", (FakeDomain,), {}),
        WebGLIndexedVertexDomain=type("WebGLIndexedVertexDomain", (FakeDomain,), {}),
    )
    key_map = {"End": "END", "1": "_1", "Numpad1": "NUM_1", "NumpadEnter": "NUM_ENTER", "F1": "F1"}
    web_window = _module(
        "pyglet.window.emscripten",
        _key_map=key_map,
        js_key_to_pyglet=lambda event: (key_map.get(event.key, 0), 0),
    )
    modules = {
        "pyodide.webloop": webloop,
        "pyglet.libs": _module("pyglet.libs", emscripten=emscripten_libs),
        "pyglet.libs.emscripten": emscripten_libs,
        "pyglet.graphics.api": _module("pyglet.graphics.api"),
        "pyglet.graphics.api.webgl": _module("pyglet.graphics.api.webgl", vertexdomain=vertexdomain),
        "pyglet.graphics.api.webgl.vertexdomain": vertexdomain,
        "pyglet.window.emscripten": web_window,
    }
    with patch.dict(sys.modules, modules), patch.object(sys.modules["pyglet.window"], "emscripten", web_window):
        platform.setup_web()
        yield SimpleNamespace(
            WebLoop=webloop.WebLoop,
            View=emscripten_libs.PersistentBufferView,
            domains=(vertexdomain.WebGLVertexDomain, vertexdomain.WebGLIndexedVertexDomain),
            window=web_window,
        )


class TestSetupWeb:
    def test_no_op_on_desktop(self):
        """On desktop, setup_web() must not import any browser module."""
        with patch.dict(sys.modules, {"pyodide": None, "pyodide.webloop": None}):
            platform.setup_web()

    def test_default_font_is_the_font_shipped_with_the_page(self, web_modules):
        assert sys.modules["pyglet.font"].manager.default_emscripten_font == platform.WEB_FONT_NAME

    @pytest.mark.parametrize("delay", [-1e-3, -1e-9, -0.0])
    def test_call_later_in_the_past_runs_as_soon_as_possible(self, web_modules, delay):
        """pyglet's wait_for can compute a slightly negative delay: it used to kill the event loop."""
        loop = web_modules.WebLoop()
        callback = MagicMock()
        assert loop.call_later(delay, callback, 1, key=2) == "handle"
        assert loop.calls == [(0, callback, (1,), {"key": 2})]

    def test_call_later_keeps_positive_delays(self, web_modules):
        loop = web_modules.WebLoop()
        loop.call_later(1 / 120, print)
        assert loop.calls[0][0] == 1 / 120

    def test_vertex_buffer_view_is_refreshed_when_the_memory_grows(self, web_modules):
        """A detached JS view (wasm memory growth, e.g. loading sounds) made drawing fail and stopped the loop."""
        buffers = [SimpleNamespace(data=_js_view(), release=MagicMock()) for _ in range(2)]
        proxy = MagicMock()
        proxy.getBuffer.side_effect = buffers
        view = web_modules.View(proxy)
        assert view.data is buffers[0].data

        buffers[0].data.byteLength = buffers[0].data.buffer.byteLength = 0  # Memory grew: view detached
        assert view.data is buffers[1].data
        buffers[0].release.assert_called_once()
        proxy.getBuffer.assert_called_with("u8")
        assert view.data is buffers[1].data  # No new view while it stays attached
        assert proxy.getBuffer.call_count == 2

    def test_empty_but_attached_view_is_kept(self, web_modules):
        """A zero-length view of a live memory is not detached."""
        empty = SimpleNamespace(byteLength=0, buffer=SimpleNamespace(byteLength=1024))
        proxy = MagicMock()
        proxy.getBuffer.return_value = SimpleNamespace(data=empty, release=MagicMock())
        view = web_modules.View(proxy)
        assert view.data is empty
        assert proxy.getBuffer.call_count == 1

    def test_webgl_multi_draw_is_disabled(self, web_modules):
        for domain in web_modules.domains:
            assert domain()._has_multi_draw_extension(ctx=None) is False

    @pytest.mark.parametrize(
        "key,code,expected",
        [
            ("End", "Numpad1", "NUM_1"),  # NumLock off
            ("1", "Numpad1", "NUM_1"),  # NumLock on
            ("Enter", "NumpadEnter", "NUM_ENTER"),
            ("1", "Digit1", "_1"),  # Main keyboard unchanged
            ("End", "End", "END"),
            ("F1", "F1", "F1"),
        ],
    )
    def test_numpad_keys_use_the_key_code(self, web_modules, key, code, expected):
        """Resman pumps are numpad keys: the browser key name ("End" or "1") lost them."""
        event = SimpleNamespace(key=key, code=code)
        assert web_modules.window.js_key_to_pyglet(event)[0] == expected


# ── Page helpers ────────────────────────────────────────────────────────────


class TestDesktopFallbacks:
    def test_helpers_do_nothing_on_desktop(self, tmp_path):
        assert platform.url_params() == {}
        assert platform.viewport_size() is None
        platform.sync_storage()
        platform.notify_page("openmatb-end")
        platform.download_file(tmp_path / "missing.csv")
        platform.on_visibility_change(MagicMock())


class TestPageHelpers:
    @pytest.mark.parametrize(
        "search,expected",
        [
            ("", {}),
            ("?scenario=basic.txt", {"scenario": "basic.txt"}),
            ("?lang=fr_FR&mode=replay&lang=en_EN", {"lang": "en_EN", "mode": "replay"}),
            ("?scenario=Parasuraman_et_al_1993%2Fhigh.txt", {"scenario": "Parasuraman_et_al_1993/high.txt"}),
        ],
    )
    def test_url_params(self, js, search, expected):
        js.window.location.search = search
        assert platform.url_params() == expected

    def test_viewport_size(self, js):
        assert platform.viewport_size() == (1280, 720)

    @pytest.mark.parametrize("state,hidden", [("hidden", True), ("visible", False)])
    def test_visibility_change(self, js, state, hidden):
        callback = MagicMock()
        platform.on_visibility_change(callback)
        event_name, listener = js.document.addEventListener.call_args[0]
        assert event_name == "visibilitychange"
        js.document.visibilityState = state
        listener(object())
        callback.assert_called_once_with(hidden)

    def test_notify_page_dispatches_a_custom_event(self, js):
        platform.notify_page("openmatb-end", "session.csv")
        js.CustomEvent.new.assert_called_once_with("openmatb-end", {"detail": "session.csv"})
        js.document.dispatchEvent.assert_called_once_with(js.CustomEvent.new.return_value)

    def test_download_file(self, js, tmp_path):
        path = tmp_path / "1_260925_120000.csv"
        path.write_bytes("logtime,scenario_time\r\n1.5,0.25\r\né\r\n".encode())
        link = MagicMock()
        js.document.createElement.return_value = link

        platform.download_file(path)

        parts, options = js.Blob.new.call_args[0]
        assert parts == ["logtime,scenario_time\r\n1.5,0.25\r\né\r\n"]  # The CSV as written, decoded as UTF-8
        assert options == {"type": "text/csv"}
        assert link.download == path.name
        assert link.href == js.URL.createObjectURL.return_value
        link.click.assert_called_once()
        link.remove.assert_called_once()
        js.URL.revokeObjectURL.assert_called_once_with(link.href)

    def test_sync_storage(self, js):
        storage = MagicMock()
        storage_module = _module("pyglet.storage", get=storage)
        with (
            patch.dict(sys.modules, {"pyglet.storage": storage_module}),
            patch.object(sys.modules["pyglet"], "storage", storage_module, create=True),
        ):
            platform.sync_storage()
        storage.assert_called_once_with(platform.STORAGE_NAME)
        storage.return_value.sync.assert_called_once()


# ── Gamepad API ─────────────────────────────────────────────────────────────


class TestBrowserGamepads:
    def test_empty_slots_are_none(self, js):
        """Chrome always returns 4 slots, null when empty: jsnull must become None.

        Regression: jsnull passed `is not None` and poll() raised AttributeError on the first
        update, which stopped pyglet's loop (the scenario froze at 0:00:00).
        """
        from core.joystick import _browser_gamepads

        assert _browser_gamepads() == [None, None, None, None]

    def test_poll_with_real_browser_slots(self, js, mock_logger):
        from core.joystick import WebGamepadDevice

        device = WebGamepadDevice()
        device.poll()
        assert device.name is None
        assert (device.x, device.y) == (0, 0)

        pad = SimpleNamespace(id="Logitech Extreme 3D", connected=True, mapping="", axes=[0.5, -0.25], buttons=[])
        js.navigator.getGamepads = lambda: JsArray([JsNull(), pad, JsNull(), JsNull()])
        device.poll()
        assert device.name == "Logitech Extreme 3D"
        assert (device.x, device.y) == (0.5, -0.25)


# ── Logger: persistent storage and end of session ───────────────────────────


@pytest.fixture
def web_logger(tmp_path):
    from core.logger import Logger

    logger_module = importlib.import_module("core.logger")
    lg = object.__new__(Logger)
    lg._ended = False
    lg.path = tmp_path / "1_session.csv"
    lg.file = MagicMock()
    with (
        patch.object(logger_module, "IS_WEB", True),
        patch.object(logger_module, "REPLAY_MODE", False),
        patch.object(logger_module, "sync_storage") as sync,
        patch.object(logger_module, "download_file") as download,
        patch.object(logger_module, "notify_page") as notify,
    ):
        yield SimpleNamespace(logger=lg, sync=sync, download=download, notify=notify, module=logger_module)


class TestWebLogger:
    def test_checkpoint_persists_what_is_written(self, web_logger):
        """Every WEB_CHECKPOINT_INTERVAL, the session file is saved (in case the tab is closed)."""
        web_logger.logger.checkpoint(10)
        web_logger.logger.file.flush.assert_called_once()
        web_logger.sync.assert_called_once()

    def test_end_session_saves_downloads_and_notifies_the_page(self, web_logger):
        lg = web_logger.logger
        lg.end_session()
        lg.file.close.assert_called_once()
        web_logger.sync.assert_called_once()
        web_logger.download.assert_called_once_with(lg.path)
        web_logger.notify.assert_called_once_with("openmatb-end", "1_session.csv")

    def test_end_session_only_once(self, web_logger):
        web_logger.logger.end_session()
        web_logger.logger.end_session()
        web_logger.logger.checkpoint()
        web_logger.download.assert_called_once()
        web_logger.logger.file.flush.assert_not_called()

    def test_nothing_is_saved_in_replay(self, web_logger):
        with patch.object(web_logger.module, "REPLAY_MODE", True):
            web_logger.logger.checkpoint()
            web_logger.logger.end_session()
        web_logger.sync.assert_not_called()
        web_logger.download.assert_not_called()


# ── Window: hidden tab ──────────────────────────────────────────────────────


class TestHiddenTab:
    def _window(self, **state):
        from core.window import Window

        win = SimpleNamespace(selector_visible=False, modal_dialog=None, pause_prompt=MagicMock())
        win.__dict__.update(state)
        win.on_visibility_change = Window.on_visibility_change.__get__(win)
        return win

    def test_hidden_tab_pauses_the_scenario(self, mock_logger):
        """Browsers throttle timers of hidden tabs (~1 Hz): the scenario is paused instead."""
        win = self._window()
        win.on_visibility_change(True)
        win.pause_prompt.assert_called_once()
        mock_logger.log_manual_entry.assert_called_once_with("hidden", key="visibility")

    def test_visible_again_is_logged_only(self, mock_logger):
        win = self._window()
        win.on_visibility_change(False)
        win.pause_prompt.assert_not_called()
        mock_logger.log_manual_entry.assert_called_once_with("visible", key="visibility")

    @pytest.mark.parametrize("state", [{"modal_dialog": object()}, {"selector_visible": True}])
    def test_no_second_pause_over_a_dialog_or_the_selector(self, mock_logger, state):
        win = self._window(**state)
        win.on_visibility_change(True)
        win.pause_prompt.assert_not_called()

    def test_no_pause_in_replay(self, mock_logger):
        with patch("core.window.REPLAY_MODE", True):
            win = self._window()
            win.on_visibility_change(True)
        win.pause_prompt.assert_not_called()


# ── Scheduler: end of the session in the page ───────────────────────────────


class TestSchedulerExit:
    def _scheduler(self):
        from core.scheduler import Scheduler

        s = object.__new__(Scheduler)
        s._exited = False
        s.clock = MagicMock()
        return s

    def test_exit_notifies_the_page_once(self, mock_logger):
        s = self._scheduler()
        with (
            patch("core.scheduler.notify_page") as notify,
            patch("core.scheduler.Window"),
            patch("core.scheduler.pyglet") as pyglet_mock,
        ):
            s.exit()
            s.exit()
        notify.assert_called_once_with("openmatb-exit")
        mock_logger.end_session.assert_called_once()
        pyglet_mock.clock.unschedule.assert_called_once_with(mock_logger.checkpoint)
        s.clock.unschedule.assert_called_once_with(s.update)

    def test_checkpoint_interval(self):
        from core.scheduler import WEB_CHECKPOINT_INTERVAL

        assert 1 <= WEB_CHECKPOINT_INTERVAL <= 30


# ── Web build ───────────────────────────────────────────────────────────────


@pytest.fixture
def build_module():
    spec = importlib.util.spec_from_file_location("_web_build", ROOT / "web" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestWebBuild:
    def test_wheels_match_requirements(self, build_module):
        """web/build.py pins must stay in sync with requirements.txt."""
        requirements = {
            line.split("==")[0].lower(): line.strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if "==" in line and not line.startswith("#")
        }
        for wheel in build_module.WHEELS:
            name = wheel.split("==")[0].lower()
            assert requirements.get(name, "").split(";")[0].strip() == wheel

    @pytest.mark.parametrize(
        "path,excluded",
        [
            ("plugins/eyetracker.py", True),
            ("includes/scenarios/generated/a.txt", True),
            ("includes/scenarios/generated", True),
            ("includes/scenarios/generated_by_hand.txt", False),
            ("plugins/sysmon.py", False),
        ],
    )
    def test_excluded_files(self, build_module, path, excluded):
        assert build_module.is_excluded(path) is excluded

    def test_app_zip_contents(self, build_module, tmp_path):
        build_module.DIST = tmp_path
        count = build_module.build_app_zip()
        with zipfile.ZipFile(tmp_path / "app.zip") as archive:
            names = set(archive.namelist())
        assert count == len(names)
        for required in ("main.py", "config.ini", "VERSION", "core/clock.py", "core/platform.py", "plugins/sysmon.py"):
            assert required in names
        assert any(n.startswith("includes/sounds/") and n.endswith(".wav") for n in names)
        assert any(n.startswith("locales/") and n.endswith(".mo") for n in names)
        assert "plugins/eyetracker.py" not in names
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
        assert not any(n.startswith("includes/scenarios/generated/") for n in names)

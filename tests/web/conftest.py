"""Fixtures for the tests run in a real browser (headless Chrome, with Playwright).

These tests are skipped unless OPENMATB_BROWSER_TESTS=1. They need:
    pip install playwright && playwright install chromium   (or an installed Chrome)
    python web/build.py                                     (builds web/dist)
Pyodide itself is loaded from its CDN, as in production.

Environment variables:
    OPENMATB_BROWSER_TESTS=1         run them
    OPENMATB_BROWSER=chromium        browser engine: chromium (default), firefox or webkit (Safari)
    OPENMATB_BROWSER_CHANNEL=chrome  chromium channel ("chrome", "msedge"...); "" for Playwright's Chromium
    OPENMATB_BROWSER_HEADED=1        show the browser
    OPENMATB_TIMING_TOLERANCE=2      multiply the timing thresholds (slow CI machines)
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT: Path = Path(__file__).resolve().parents[2]
DIST: Path = ROOT / "web" / "dist"
PROBE: Path = Path(__file__).with_name("probe.py")
FAKE_AUDIO: Path = Path(__file__).with_name("fake_audio.js")
ENABLED: bool = os.environ.get("OPENMATB_BROWSER_TESTS") == "1"
BOOT_TIMEOUT_MS: int = 180_000


def pytest_collection_modifyitems(config, items) -> None:
    if ENABLED:
        return
    skip = pytest.mark.skip(reason="browser tests: set OPENMATB_BROWSER_TESTS=1")
    for item in items:
        if Path(str(item.fspath)).parent == Path(__file__).parent:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def tolerance() -> float:
    return float(os.environ.get("OPENMATB_TIMING_TOLERANCE", "1"))


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture(scope="session")
def server_url():
    if not (DIST / "index.html").exists() or not (DIST / "app.zip").exists():
        pytest.skip("web/dist is not built: run python web/build.py")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(DIST)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    engine = os.environ.get("OPENMATB_BROWSER", "chromium")
    options: dict[str, Any] = dict(headless=os.environ.get("OPENMATB_BROWSER_HEADED") != "1")
    with sync_api.sync_playwright() as playwright:
        if engine == "chromium":
            options["args"] = ["--autoplay-policy=no-user-gesture-required"]
            channel = os.environ.get("OPENMATB_BROWSER_CHANNEL", "chrome")
            try:
                instance = playwright.chromium.launch(channel=channel or None, **options)
            except Exception:
                instance = playwright.chromium.launch(**options)  # Playwright's own Chromium
        elif engine == "firefox":
            instance = playwright.firefox.launch(firefox_user_prefs={"media.autoplay.default": 0}, **options)
        else:
            instance = getattr(playwright, engine).launch(**options)
        yield instance
        instance.close()


def _config(overrides: dict[str, str]) -> str:
    text = (ROOT / "config.ini").read_text(encoding="utf-8")
    for key, value in overrides.items():
        text = re.sub(rf"(?m)^{key}=.*$", f"{key}={value}", text)
    return text


class OpenMATBPage:
    """The web page, with helpers to start a scenario and read the probe (tests/web/probe.py)."""

    SCENARIO: str = "web_test.txt"

    def __init__(self, page: Any, url: str) -> None:
        self.page = page
        self.url = url
        self.console: list[str] = []
        self.errors: list[str] = []
        self.downloads: list[Any] = []
        page.on("console", lambda m: self.console.append(m.text))
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("download", lambda d: self.downloads.append(d))

    @property
    def has_web_audio(self) -> bool:
        return not self.page.evaluate("() => window.__openmatbFakeAudio === true")

    def python(self, code: str) -> Any:
        return self.page.evaluate("(code) => window.openmatb.pyodide.runPython(code)", code)

    def write_file(self, path: str, content: str) -> None:
        self.page.evaluate(
            "([path, content]) => window.openmatb.pyodide.FS.writeFile(path, content)",
            [path, content],
        )

    def open_menu(self, params: str = "") -> None:
        """Open the start page and wait until OpenMATB is loaded (without starting it)."""
        self.page.goto(f"{self.url}/index.html?lang=en_EN{params}")
        self.page.wait_for_function("() => window.openmatb !== undefined", timeout=BOOT_TIMEOUT_MS)

    def prepare(self, scenario: str, config: dict[str, str] | None = None) -> None:
        """Open the start page with the scenario and config.ini values of the test, ready to click Start."""
        self.page.goto(f"{self.url}/index.html?lang=en_EN&mode=scenario&scenario={self.SCENARIO}")
        self.page.wait_for_selector("#start:not([disabled])", timeout=BOOT_TIMEOUT_MS)
        self.write_file(f"/app/includes/scenarios/{self.SCENARIO}", scenario)
        self.write_file("/app/config.ini", _config({"display_session_number": "False", **(config or {})}))
        self.write_file("/app/_openmatb_probe.py", PROBE.read_text(encoding="utf-8"))
        self.python("import _openmatb_probe")
        self.page.uncheck("#fullscreen")

    def start(self, scenario: str, config: dict[str, str] | None = None) -> None:
        self.prepare(scenario, config)
        self.page.click("#start")
        self.wait_until(lambda s: s["started"] and len(s["updates"]) > 0, timeout=30)

    def new_tab(self) -> OpenMATBPage:
        """Another page of the same browser context: it shares the browser storage (the sessions)."""
        return OpenMATBPage(self.page.context.new_page(), self.url)

    def start_replay(self, session_id: int) -> None:
        """Open the replay of a session kept in the browser storage (paused at its start)."""
        self.page.goto(f"{self.url}/index.html?lang=en_EN&mode=replay&session={session_id}")
        self.page.wait_for_selector("#start:not([disabled])", timeout=BOOT_TIMEOUT_MS)
        self.write_file("/app/config.ini", _config({"display_session_number": "False"}))
        self.write_file("/app/_openmatb_probe.py", PROBE.read_text(encoding="utf-8"))
        self.python("import _openmatb_probe")
        self.page.select_option("#mode", "replay")  # The mode of the start page is used, not the address
        self.page.uncheck("#fullscreen")
        self.page.click("#start")
        self.wait_until(lambda s: s["started"], timeout=30)  # No update while the replay is paused

    def state(self) -> dict:
        return json.loads(self.python("import _openmatb_probe; _openmatb_probe.state()"))

    def wait_until(self, predicate: Callable[[dict], bool], timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            state = self.state()
            if predicate(state):
                return state
            if time.monotonic() > deadline:
                raise AssertionError(f"Timeout; last state: running={state['running']} time={state['scenario_time']}")
            time.sleep(0.1)

    def hide_tab(self) -> None:
        """Emulate a tab switch (Playwright pages are always visible)."""
        self.page.evaluate(
            """() => {
                Object.defineProperty(document, "visibilityState", {value: "hidden", configurable: true});
                document.dispatchEvent(new Event("visibilitychange"));
            }"""
        )


@pytest.fixture(scope="module")
def page_factory(browser, server_url):
    contexts = []

    def new_page() -> OpenMATBPage:
        context = browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
        context.add_init_script(path=str(FAKE_AUDIO))  # Only used by browsers without Web Audio
        contexts.append(context)
        return OpenMATBPage(context.new_page(), server_url)

    yield new_page
    for context in contexts:
        context.close()

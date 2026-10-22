"""Leaving fullscreen during a session: the display is only scaled to the smaller page (bands on the sides), so the
scenario is paused, and the end of the pause puts the page in fullscreen again.
Run with: OPENMATB_BROWSER_TESTS=1 python -m pytest tests/web/test_fullscreen.py -v
"""

from __future__ import annotations

SCENARIO: str = "0:00:00;sysmon;start\n0:01:00;sysmon;stop\n"

IN_FULLSCREEN: str = "() => document.fullscreenElement !== null"


def test_leaving_fullscreen_pauses_then_fullscreen_again(page_factory):
    app = page_factory()
    app.prepare(SCENARIO)
    app.page.check("#fullscreen")
    app.page.click("#start")
    app.wait_until(lambda s: s["started"] and len(s["updates"]) > 0, timeout=30)
    app.page.wait_for_function(IN_FULLSCREEN, timeout=5_000)
    app.page.wait_for_timeout(500)

    # Out of fullscreen (Escape for the participant): the scenario is paused
    app.page.evaluate("() => document.exitFullscreen()")
    paused = app.wait_until(lambda s: s["modal"], timeout=5)
    app.page.wait_for_timeout(500)
    assert app.wait_until(lambda s: s["modal"], timeout=1)["scenario_time"] == paused["scenario_time"]

    # The end of the pause: fullscreen again, and the scenario goes on
    app.page.focus("#pygletCanvas")
    app.page.keyboard.press("Space")
    app.page.wait_for_function(IN_FULLSCREEN, timeout=5_000)
    app.wait_until(lambda s: not s["modal"] and s["scenario_time"] > paused["scenario_time"] + 0.3, timeout=5)
    session = app.python(
        "from core.logger import get_logger; get_logger().file.flush(); open(get_logger().path, encoding='utf-8').read()"
    )
    assert ",fullscreen,,,exit" in session.replace("\r", "")

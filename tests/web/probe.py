"""Instrumentation run inside the page (Pyodide) by tests/web, before main.py.

It records, with the browser clock (performance.now, ms):
- each scenario update (Scheduler.update): start time, dt, scenario time, processing duration,
- each executed scenario event: line, planned time, scenario time, start time, update index,
- each plugin step (taskupdatetime): plugin alias, scenario time,
- each key received by the OpenMATB window.
state() returns everything as JSON.
"""

import gettext
import json

import js

# main.py installs the translation before importing core modules: do the same to import them first
gettext.translation("openmatb", "locales", ["en_EN"], fallback=True).install()

import pyglet.app  # noqa: E402
import pyglet.window.key  # noqa: E402

import core.scheduler as scheduler_module  # noqa: E402
from core.window import Window  # noqa: E402
from plugins.abstractplugin import AbstractPlugin  # noqa: E402

PROBE: dict = {"scheduler": None, "updates": [], "events": [], "steps": [], "keys": [], "handlers": []}


def now_ms() -> float:
    return float(js.performance.now())


_execute_one_event = scheduler_module.Scheduler.execute_one_event


def execute_one_event(self, event) -> None:
    t = now_ms()  # Before the execution (starting a plugin takes tens of ms)
    _execute_one_event(self, event)
    PROBE["events"].append(
        {
            "line": event.line,
            "time_sec": float(event.time_sec),
            "scenario_time": self.scenario_time,
            "t": t,
            "update": len(PROBE["updates"]),  # Index of the update being executed
        }
    )


_update = scheduler_module.Scheduler.update


def update(self, dt: float) -> None:
    # Timestamp taken when the update starts, like the dt computed by pyglet
    start = now_ms()
    _update(self, dt)
    PROBE["updates"].append((start, dt, self.scenario_time, now_ms() - start))


_init = scheduler_module.Scheduler.__init__


def init(self, *args, **kwargs) -> None:
    PROBE["scheduler"] = self
    _init(self, *args, **kwargs)

    def on_key_press(symbol: int, modifiers: int) -> None:
        PROBE["keys"].append(pyglet.window.key.symbol_string(symbol))

    # pyglet only keeps weak references to handlers
    PROBE["handlers"].append(on_key_press)
    Window.MainWindow.push_handlers(on_key_press=on_key_press)


_compute_next_plugin_state = AbstractPlugin.compute_next_plugin_state


def compute_next_plugin_state(self) -> bool:
    done = _compute_next_plugin_state(self)
    if done:
        PROBE["steps"].append((self.alias, self.scenario_time))
    return done


AbstractPlugin.compute_next_plugin_state = compute_next_plugin_state  # Plugins call it with super()
scheduler_module.Scheduler.execute_one_event = execute_one_event
scheduler_module.Scheduler.update = update  # Scheduler.__init__ schedules self.update
scheduler_module.Scheduler.__init__ = init


def state() -> str:
    s = PROBE["scheduler"]
    window = Window.MainWindow
    return json.dumps(
        {
            "started": s is not None,
            "running": bool(pyglet.app.event_loop.is_running),
            "scenario_time": s.scenario_time if s else None,
            "modal": window is not None and window.modal_dialog is not None,
            "updates": PROBE["updates"],
            "events": PROBE["events"],
            "steps": PROBE["steps"],
            "keys": PROBE["keys"],
            "now": now_ms(),
        }
    )

# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Platform helpers to run the same code on desktop and in the browser (Pyodide)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

IS_WEB: bool = sys.platform == "emscripten"

STORAGE_NAME: str = "openmatb"
WEB_FONT_NAME: str = "Noto Sans"  # Loaded by the page (web/openmatb.js)


def setup_web() -> None:
    """Browser specific setup, to call before creating the window. No-op on desktop."""
    if not IS_WEB:
        return
    import pyglet.font
    from pyodide.webloop import WebLoop

    # Use the font shipped with the page as default font (pyglet's browser default is a serif font)
    pyglet.font.manager.default_emscripten_font = WEB_FONT_NAME

    # pyglet waits with asyncio.wait_for(..., very short timeout): by the time Pyodide's loop computes
    # the delay it can be slightly negative, and WebLoop raises "Can't schedule in the past", which
    # kills pyglet's event loop. CPython's asyncio runs such callbacks as soon as possible instead.
    call_later = WebLoop.call_later

    def call_later_not_in_past(self: Any, delay: float, callback: Any, *args: Any, **kwargs: Any) -> Any:
        return call_later(self, max(delay, 0), callback, *args, **kwargs)

    WebLoop.call_later = call_later_not_in_past

    _patch_pyglet_webgl()
    _patch_pyglet_numpad_keys()


def _patch_pyglet_numpad_keys() -> None:
    """pyglet maps browser keys with event.key, which gives "1" or "End" for the numpad 1 key (depending
    on NumLock), never NUM_1: resman pump keys did not work. Use event.code for numpad keys, as on desktop."""
    from pyglet.window import emscripten as web_window

    js_key_to_pyglet = web_window.js_key_to_pyglet

    def js_key_with_numpad(event: Any) -> tuple[Any, int]:
        symbol, modifiers = js_key_to_pyglet(event)
        code: str = str(event.code)
        if code.startswith("Numpad") and code in web_window._key_map:
            symbol = web_window._key_map[code]
        return symbol, modifiers

    web_window.js_key_to_pyglet = js_key_with_numpad


def _patch_pyglet_webgl() -> None:
    """Work around two pyglet 3.0.dev10 WebGL bugs that stop the drawing (and the event loop)."""
    from pyglet.graphics.api.webgl import vertexdomain
    from pyglet.libs.emscripten import PersistentBufferView

    # 1. Vertex buffers keep a zero-copy JavaScript view of the WebAssembly memory. When the memory grows
    # (e.g. while sounds are loaded) the view is detached ("Cannot perform Construct on a detached
    # ArrayBuffer"). The Python buffer itself does not move: take a new view when needed.
    def fresh_data(self: Any) -> Any:
        if self._openmatb_data.byteLength == 0 and self._openmatb_data.buffer.byteLength == 0:  # Detached
            self._buffer.release()
            self._buffer = self._proxy.getBuffer("u8")
            self._openmatb_data = self._buffer.data
        return self._openmatb_data

    def set_data(self: Any, value: Any) -> None:
        self._openmatb_data = value

    PersistentBufferView.data = property(fresh_data, set_data)

    # 2. The WEBGL_multi_draw path passes ctypes pointers instead of offsets ("countsOffset out of bounds"):
    # draw each range with drawElements/drawArrays instead
    for domain in (vertexdomain.WebGLVertexDomain, vertexdomain.WebGLIndexedVertexDomain):
        domain._has_multi_draw_extension = lambda self, ctx: False


def on_visibility_change(callback: Callable[[bool], None]) -> None:
    """Call callback(hidden) when the page is hidden or shown again (tab switch...). No-op on desktop."""
    if not IS_WEB:
        return
    import js
    from pyodide.ffi import create_proxy

    def listener(event: Any) -> None:
        callback(str(js.document.visibilityState) == "hidden")

    js.document.addEventListener("visibilitychange", create_proxy(listener))


def web_sessions_path() -> Path:
    """Sessions folder in the browser persistent storage (IndexedDB backed /data mount)."""
    import pyglet.storage

    return pyglet.storage.get(STORAGE_NAME).data / "sessions"


def sync_storage() -> None:
    """Commit pending writes of the browser persistent storage. No-op on desktop."""
    if not IS_WEB:
        return
    import pyglet.storage

    pyglet.storage.get(STORAGE_NAME).sync()


def url_params() -> dict[str, str]:
    """Return the page query parameters (?scenario=...&lang=...). Empty on desktop."""
    if not IS_WEB:
        return {}
    import js

    query: str = str(js.window.location.search).lstrip("?")
    return {k: v[-1] for k, v in parse_qs(query).items()}


def viewport_size() -> tuple[int, int] | None:
    """Size of the browser viewport, or None on desktop."""
    if not IS_WEB:
        return None
    import js

    return int(js.window.innerWidth), int(js.window.innerHeight)


def download_file(path: Path, mime: str = "text/csv") -> None:
    """Make the browser download a file from the virtual file system. No-op on desktop."""
    if not IS_WEB:
        return
    import js
    from pyodide.ffi import to_js

    data: bytes = Path(path).read_bytes()
    blob = js.Blob.new(to_js([data.decode("utf-8")]), to_js({"type": mime}, dict_converter=js.Object.fromEntries))
    url = js.URL.createObjectURL(blob)
    link = js.document.createElement("a")
    link.href = url
    link.download = Path(path).name
    js.document.body.appendChild(link)
    link.click()
    link.remove()
    js.URL.revokeObjectURL(url)


def notify_page(event_name: str, detail: str = "") -> None:
    """Dispatch a DOM CustomEvent on the page (e.g. 'openmatb-end'). No-op on desktop."""
    if not IS_WEB:
        return
    import js
    from pyodide.ffi import to_js

    init = to_js({"detail": detail}, dict_converter=js.Object.fromEntries)
    js.document.dispatchEvent(js.CustomEvent.new(event_name, init))

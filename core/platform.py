# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Platform helpers to run the same code on desktop and in the browser (Pyodide)."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs

IS_WEB: bool = sys.platform == "emscripten"

# Persistent storage (IndexedDB backed) mounted by pyglet's emscripten launcher
WEB_DATA_PATH: Path = Path("/data")


def url_params() -> dict[str, str]:
    """Return the page query parameters (?scenario=...&lang=...). Empty on desktop."""
    if not IS_WEB:
        return {}
    import js  # noqa: PLC0415

    query: str = str(js.window.location.search).lstrip("?")
    return {k: v[-1] for k, v in parse_qs(query).items()}


def viewport_size() -> tuple[int, int] | None:
    """Size of the browser viewport, or None on desktop."""
    if not IS_WEB:
        return None
    import js  # noqa: PLC0415

    return int(js.window.innerWidth), int(js.window.innerHeight)


def download_file(path: Path, mime: str = "text/csv") -> None:
    """Make the browser download a file from the virtual file system. No-op on desktop."""
    if not IS_WEB:
        return
    import js  # noqa: PLC0415
    from pyodide.ffi import to_js  # noqa: PLC0415

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
    import js  # noqa: PLC0415
    from pyodide.ffi import to_js  # noqa: PLC0415

    init = to_js({"detail": detail}, dict_converter=js.Object.fromEntries)
    js.document.dispatchEvent(js.CustomEvent.new(event_name, init))

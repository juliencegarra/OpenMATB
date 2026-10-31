"""core.pyglet_compat carries pyglet#1528: consecutive tabs in a multiline label (pyglet 3 on Windows).

With the real pyglet, in a subprocess: tests/conftest.py replaces pyglet.text by a mock."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

LABEL = """
import sys
import pyglet
if sys.argv[1] == "compat":  # The module alone (the core package needs the application: gettext, arguments)
    import importlib.util
    spec = importlib.util.spec_from_file_location("pyglet_compat", "core/pyglet_compat.py")
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
window = pyglet.window.Window(200, 100, visible=False)
pyglet.text.Label("Callsign \t\t HSR259", font_size=12, multiline=True, width=576)
print(int(pyglet.version.split(".")[0]))
"""


def _label(mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", LABEL, mode], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False
    )


def _real_pyglet_major() -> int | None:
    try:
        out = subprocess.run(
            [sys.executable, "-c", "import pyglet; print(pyglet.version)"], capture_output=True, text=True, timeout=60
        )
        return int(out.stdout.split(".")[0])
    except (ValueError, OSError, subprocess.SubprocessError):
        return None


@pytest.mark.skipif(sys.platform != "win32", reason="DirectWrite (Windows)")
def test_consecutive_tabs_in_a_multiline_label():
    if _real_pyglet_major() != 3:
        pytest.skip("pyglet 3 only (pyglet 2 has no such crash)")
    if _label("pyglet").returncode == 0:
        pytest.skip("pyglet has pyglet#1528: remove _carry_pyglet_1528 from core/pyglet_compat.py")
    result = _label("compat")
    assert result.returncode == 0, result.stderr[-2000:]

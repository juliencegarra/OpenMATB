"""
Test infrastructure for OpenMATB.

Resolves 3 problems before any application import:
1. gettext _() : installs builtins._ as identity function
2. Pyglet : injects mocks into sys.modules to avoid OpenGL dependency
3. Singletons : mocks logger, joystick, error modules to prevent I/O
"""

import builtins
import sys
import types
from unittest.mock import MagicMock
import configparser

# ──────────────────────────────────────────────
# 1. Install gettext identity function
# ──────────────────────────────────────────────
builtins._ = lambda s: s


# ──────────────────────────────────────────────
# 2. Mock pyglet and all its submodules
# ──────────────────────────────────────────────

class _MockModule(types.ModuleType):
    """A module that returns MagicMock for any missing attribute.
    This handles 'from module import *' and arbitrary attribute access."""

    def __init__(self, name, extras=None):
        super().__init__(name)
        self.__path__ = []
        self.__file__ = f'<mock {name}>'
        self.__loader__ = None
        self.__spec__ = None
        self.__all__ = []  # Prevent 'from x import *' from importing everything
        if extras:
            self.__dict__.update(extras)

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        # Return 0 for GL constants, MagicMock for everything else
        if name.startswith('GL_'):
            return 0
        if name.startswith('gl') and name[2:3].isupper():
            return lambda *args, **kwargs: None
        mock = MagicMock(name=f'{self.__name__}.{name}')
        setattr(self, name, mock)
        return mock


# Realistic key names for validation.is_keyboard_key
_KEY_NAMES = {
    0xff01: 'BACKSPACE', 0xff09: 'TAB', 0xff0a: 'LINEFEED', 0xff0d: 'RETURN',
    0xff1b: 'ESCAPE', 0xff20: 'SPACE', 0xffff: 'DELETE',
    0xff50: 'HOME', 0xff51: 'LEFT', 0xff52: 'UP', 0xff53: 'RIGHT', 0xff54: 'DOWN',
    0xff55: 'PAGEUP', 0xff56: 'PAGEDOWN', 0xff57: 'END',
    0xffbe: 'F1', 0xffbf: 'F2', 0xffc0: 'F3', 0xffc1: 'F4',
    0xffc2: 'F5', 0xffc3: 'F6', 0xffc4: 'F7', 0xffc5: 'F8',
    0xffc6: 'F9', 0xffc7: 'F10', 0xffc8: 'F11', 0xffc9: 'F12',
    0xff63: 'INSERT',
    0xffb0: 'NUM_0', 0xffb1: 'NUM_1', 0xffb2: 'NUM_2', 0xffb3: 'NUM_3',
    0xffb4: 'NUM_4', 0xffb5: 'NUM_5', 0xffb6: 'NUM_6', 0xffb7: 'NUM_7',
    0xffb8: 'NUM_8', 0xffb9: 'NUM_9',
    0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E',
    0x46: 'F', 0x47: 'G', 0x48: 'H', 0x49: 'I', 0x4a: 'J',
    0x4b: 'K', 0x4c: 'L', 0x4d: 'M', 0x4e: 'N', 0x4f: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T',
    0x55: 'U', 0x56: 'V', 0x57: 'W', 0x58: 'X', 0x59: 'Y', 0x5a: 'Z',
    0xff8d: 'ENTER',
}

# Create mock pyglet modules
_pyglet_modules = [
    'pyglet', 'pyglet.gl', 'pyglet.window', 'pyglet.window.key',
    'pyglet.graphics', 'pyglet.text', 'pyglet.clock', 'pyglet.app',
    'pyglet.input', 'pyglet.media', 'pyglet.canvas', 'pyglet.image',
    'pyglet.sprite', 'pyglet.font',
    'pyglet.text.formats', 'pyglet.text.formats.html',
    'pyglet.resource',
]

for mod_name in _pyglet_modules:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _MockModule(mod_name)

# Configure specific pyglet mock attributes

# pyglet.window.key
key_mod = sys.modules['pyglet.window.key']
key_mod._key_names = _KEY_NAMES
key_mod.symbol_string = lambda sym: _KEY_NAMES.get(sym, f'KEY_{sym}')
# Add key constants as attributes
for code, name in _KEY_NAMES.items():
    setattr(key_mod, name, code)

# pyglet.window.Window - use a real class (not MagicMock) so subclassing
# in core.window produces a real type that supports object.__new__()
class _FakePygletWindow:
    """Minimal stub for pyglet.window.Window base class."""
    def __init__(self, *args, **kwargs):
        pass
    def switch_to(self):
        pass
    def set_location(self, x, y):
        pass
    def set_mouse_visible(self, visible):
        pass
    def set_icon(self, *args):
        pass
    def clear(self):
        pass

sys.modules['pyglet.window'].Window = _FakePygletWindow
sys.modules['pyglet.window'].key = key_mod

# pyglet.graphics
sys.modules['pyglet.graphics'].OrderedGroup = lambda x: x
sys.modules['pyglet.graphics'].Batch = MagicMock

# pyglet.text
sys.modules['pyglet.text'].Label = MagicMock
sys.modules['pyglet.text'].HTMLLabel = MagicMock

# pyglet.clock
sys.modules['pyglet.clock'].Clock = MagicMock
sys.modules['pyglet.clock'].schedule = MagicMock()

# pyglet.app
sys.modules['pyglet.app'].EventLoop = MagicMock

# pyglet.media
sys.modules['pyglet.media'].Player = MagicMock
sys.modules['pyglet.media'].SourceGroup = MagicMock
sys.modules['pyglet.media'].load = MagicMock()

# pyglet.canvas
sys.modules['pyglet.canvas'].get_display = MagicMock()

# pyglet.image
sys.modules['pyglet.image'].load = MagicMock()

# pyglet.sprite
sys.modules['pyglet.sprite'].Sprite = MagicMock

# pyglet.font
font_mod = sys.modules['pyglet.font']
font_mod.have_font = lambda name: True
font_mod.add_file = MagicMock()
font_mod.load = MagicMock()  # Used by modaldialog.py

# pyglet top-level
pyglet_mod = sys.modules['pyglet']
pyglet_mod.clock = sys.modules['pyglet.clock']
pyglet_mod.app = sys.modules['pyglet.app']
pyglet_mod.window = sys.modules['pyglet.window']
pyglet_mod.gl = sys.modules['pyglet.gl']
pyglet_mod.graphics = sys.modules['pyglet.graphics']
pyglet_mod.text = sys.modules['pyglet.text']
pyglet_mod.input = sys.modules['pyglet.input']
pyglet_mod.media = sys.modules['pyglet.media']
pyglet_mod.canvas = sys.modules['pyglet.canvas']
pyglet_mod.image = sys.modules['pyglet.image']
pyglet_mod.sprite = sys.modules['pyglet.sprite']
pyglet_mod.font = sys.modules['pyglet.font']


# ──────────────────────────────────────────────
# 3. Mock pyparallel, pylsl, rstr (may not be installed)
# ──────────────────────────────────────────────
for mod_name in ['parallel', 'parallel.parallelppdev', 'pylsl']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _MockModule(mod_name)

if 'rstr' not in sys.modules:
    rstr_mod = _MockModule('rstr')
    rstr_mod.xeger = lambda pattern: 'ABC123'
    sys.modules['rstr'] = rstr_mod


# ──────────────────────────────────────────────
# 4. Pytest fixtures
# ──────────────────────────────────────────────
import pytest


@pytest.fixture
def mock_logger(monkeypatch):
    """Provide a mock logger that prevents file I/O."""
    import importlib
    logger_module = importlib.import_module('core.logger')
    mock = MagicMock()
    mock.session_id = 1
    mock.scenario_time = 0
    monkeypatch.setattr(logger_module, 'logger', mock)
    return mock


@pytest.fixture
def mock_window(monkeypatch):
    """Provide a mock Window.MainWindow."""
    mock = MagicMock()
    mock.keyboard = {}
    mock.modal_dialog = None
    mock.batch = MagicMock()
    mock.width = 1920
    mock.height = 1080
    mock._width = 1920
    mock._height = 1080

    from core.container import Container
    containers = [
        Container('invisible', 0, 0, 0, 0),
        Container('fullscreen', 0, 0, 1920, 1080),
        Container('topleft', 0, 540, 640, 540),
        Container('topmid', 640, 540, 640, 540),
        Container('topright', 1280, 540, 640, 540),
        Container('bottomleft', 0, 0, 640, 540),
        Container('bottommid', 640, 0, 640, 540),
        Container('bottomright', 1280, 0, 640, 540),
    ]
    mock.get_container_list.return_value = containers
    mock.get_container = lambda name: next((c for c in containers if c.name == name), None)

    monkeypatch.setattr('core.window.Window.MainWindow', mock)
    return mock

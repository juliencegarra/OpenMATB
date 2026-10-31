# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""The differences between pyglet 2 and pyglet 3 used by OpenMATB.

The browser version needs pyglet 3 (only a development version for now); the desktop version keeps the released
pyglet 2. Everything that differs between them is here: remove this module when the desktop moves to pyglet 3.

Up to pyglet 3.0.dev11, consecutive tabs in a multiline label (e.g. the callsign of communications, instructions,
questionnaires) crash on Windows: fixed upstream by pyglet#1528, carried here until the next pyglet 3 release.
"""

from __future__ import annotations

import sys
from typing import Any

import pyglet

PYGLET_3: bool = int(pyglet.version.split(".")[0]) >= 3

if PYGLET_3:
    from pyglet.config import Config
    from pyglet.graphics.framebuffer import get_screenshot
    from pyglet.image.base import _AbstractImage
    from pyglet.media import AudioPlayer, load_audio

    # pyglet 3.0.dev10: images have no anchor any more, but an <img> of an HTML label (instructions) still reads
    # image.anchor_y, and the exception stopped the event loop: images keep the default anchor of pyglet 2 (0, 0).
    # Fixed upstream by pyglet#1527 (merged after 3.0.dev11): to remove with the next pyglet 3 release
    if not hasattr(_AbstractImage, "anchor_y"):
        _AbstractImage.anchor_x = 0
        _AbstractImage.anchor_y = 0
else:
    from pyglet.gl import Config
    from pyglet.media import Player as AudioPlayer
    from pyglet.media import load as load_audio

    def get_screenshot() -> Any:
        return pyglet.image.get_buffer_manager().get_color_buffer()


__all__ = ["ITALIC", "PYGLET_3", "AudioPlayer", "Config", "gapless_player", "get_screenshot", "load_audio"]

# Label keyword arguments for italic text
ITALIC: dict[str, Any] = {"style": "italic"} if PYGLET_3 else {"italic": True}


def gapless_player(sources: list[Any]) -> Any:
    """A player of the sources one after the other, its source None once they are all played. pyglet 2 and pyglet 3
    up to 3.0.dev11 queue a SourceGroup; the pyglet 3 development branch replaced SourceGroup by GaplessAudioPlayer."""
    import pyglet.media

    if not hasattr(pyglet.media, "SourceGroup"):
        player: Any = pyglet.media.GaplessAudioPlayer()
        if sources:
            player.queue(sources)
        return player
    player = AudioPlayer()
    if sources:
        group: Any = pyglet.media.SourceGroup()
        for source in sources:
            group.add(source)
        player.queue(group)
    return player


def window_config(screen: Any) -> Config | list[Config]:
    """4x multisampling antialiasing (MSAA) for smooth edges if available, else a plain config."""
    if PYGLET_3:  # A list: pyglet 3 takes the first one available
        msaa: Config = Config()
        msaa.opengl.sample_buffers = 1
        msaa.opengl.samples = 4
        msaa.opengl.double_buffer = True
        msaa.webgl.antialias = True
        return [msaa, Config()]
    from pyglet.window import NoSuchConfigException

    try:
        return screen.get_best_config(Config(sample_buffers=1, samples=4, double_buffer=True))
    except NoSuchConfigException:
        return screen.get_best_config(Config(double_buffer=True))


def set_clear_color(window: Any, red: float, green: float, blue: float, alpha: float) -> None:
    if PYGLET_3:
        window.context.set_clear_color(red, green, blue, alpha)
    else:
        from pyglet.gl import glClearColor

        glClearColor(red, green, blue, alpha)


def set_mouse_cursor_visible(window: Any, visible: bool) -> None:
    if PYGLET_3:
        window.set_mouse_cursor_visible(visible)
    else:
        window.set_mouse_visible(visible)


def default_font_name() -> str | None:
    """The default font of the platform (None: pyglet 2 chooses it)."""
    return pyglet.font.manager.get_platform_default_name() if PYGLET_3 else None


def _carry_pyglet_1528() -> None:
    """pyglet 3 on Windows, up to 3.0.dev11: DirectWrite gives a run without glyphs (consecutive tabs) one glyph for
    all its characters, and a multiline layout, which needs one per character, raised an IndexError (e.g. the callsign
    label of communications, at its start). pyglet#1528 (merged after 3.0.dev11) gives one empty glyph per
    character: the text renderer of pyglet is replaced by one doing the same. Harmless once pyglet has the fix.
    To remove with the next pyglet 3 release."""
    from ctypes import cast, create_unicode_buffer, py_object

    try:
        from pyglet.font import dwrite
        from pyglet.font.base import GlyphPosition
    except ImportError:  # Another font backend
        return
    if not hasattr(dwrite, "_DWriteTextRenderer") or not hasattr(dwrite, "_renderer"):
        return  # pyglet changed: nothing to carry

    class _TextRenderer(dwrite._DWriteTextRenderer):
        _interfaces_ = [dwrite.IDWriteTextRenderer]  # noqa: RUF012 (a COM subclass builds its own vtable)

        def DrawGlyphRun(  # The COM method name
            self, context: Any, x: float, y: float, mode: int, run: Any, description: Any, effect: Any
        ) -> int:
            if run.contents.glyphCount != 0:
                return super().DrawGlyphRun(context, x, y, mode, run, description, effect)
            glyph_renderer: Any = cast(context, py_object).value
            length: int = len(create_unicode_buffer(description.contents.text)[: description.contents.textLength])
            for _ in range(length):
                glyph_renderer.current_glyphs.append(glyph_renderer.font._zero_glyph)
                glyph_renderer.current_offsets.append(GlyphPosition(0, 0, 0, 0))
            return 0

    dwrite._renderer = _TextRenderer()


if PYGLET_3 and sys.platform == "win32":
    _carry_pyglet_1528()

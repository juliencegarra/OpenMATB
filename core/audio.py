# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""Audio helpers shared by desktop and browser.

In the browser, pyglet decodes sounds asynchronously with the Web Audio API and its
player does not support SourceGroup (one decoded buffer per player, a stopped buffer
can't be restarted). SequencePlayer hides these differences: on desktop it plays a
SourceGroup as before; in the browser it chains one AudioPlayer per sound.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyglet.clock
from pyglet.media import AudioPlayer, SourceGroup, load_audio

from core.platform import IS_WEB

_cache: dict[str, Any] = dict()


def load_sound(path: Path) -> Any:
    """Load (and cache) a static sound. Cached sources can be played by several players."""
    key: str = str(path)
    if key not in _cache:
        _cache[key] = load_audio(key, streaming=False)
    return _cache[key]


def preload_sounds(folder: Path) -> None:
    """Load every .wav of a folder, so that decoding (asynchronous in the browser) is done in advance."""
    for wav_path in sorted(folder.glob("*.wav")):
        try:
            load_sound(wav_path)
        except Exception:
            pass


class SequencePlayer:
    """Play a list of sounds one after the other. Exposes the subset of the Player API used by OpenMATB."""

    def __init__(self, sources: list[Any], sequential: bool = IS_WEB) -> None:
        self._sources: list[Any] = list(sources)
        self._sequential: bool = sequential
        self._volume: float = 1.0
        self._index: int = 0  # Sequential mode: index of the sound being played
        self._playing: bool = False
        self._player: Any = None

        if not self._sequential:
            self._player = AudioPlayer()
            if self._sources:
                group: Any = SourceGroup()
                for source in self._sources:
                    group.add(source)
                self._player.queue(group)

    @property
    def source(self) -> Any:
        """The sound being played, or None once the whole sequence has been played."""
        if not self._sequential:
            return self._player.source
        return self._sources[self._index] if self._index < len(self._sources) else None

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        self._volume = value
        if self._player is not None:
            self._player.volume = value

    def play(self) -> None:
        if not self._sequential:
            self._player.play()
        elif not self._playing and self.source is not None:
            self._playing = True
            self._start_current()

    def pause(self) -> None:
        if not self._sequential:
            self._player.pause()
        else:
            # A Web Audio buffer can't be resumed: the current sound restarts on play()
            self._playing = False
            self._stop_current()

    def delete(self) -> None:
        self._playing = False
        self._stop_current() if self._sequential else self._player.delete()
        self._player = None

    # ---- Sequential mode ----

    def _start_current(self) -> None:
        self._player = AudioPlayer()
        self._player.volume = self._volume
        self._player.push_handlers(on_player_eos=self._on_player_eos)
        self._player.queue(self.source)
        self._player.play()

    def _stop_current(self) -> None:
        if self._player is not None:
            self._player.remove_handlers(on_player_eos=self._on_player_eos)
            self._player.pause()
            self._player.delete()
            self._player = None

    def _on_player_eos(self) -> None:
        # Don't delete the player inside its own event dispatch
        pyglet.clock.schedule_once(self._next, 0)

    def _next(self, dt: float) -> None:
        if not self._playing:
            return
        self._stop_current()
        self._index += 1
        if self._playing and self.source is not None:
            self._start_current()
        else:
            self._playing = False

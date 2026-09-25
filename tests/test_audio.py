"""Tests for core.audio.SequencePlayer (desktop SourceGroup mode and browser sequential mode)."""

from unittest.mock import MagicMock, patch

import core.audio as audio


class TestDesktopMode:
    def test_uses_a_single_player_with_source_group(self):
        with patch.object(audio, "AudioPlayer") as player_cls, patch.object(audio, "SourceGroup") as group_cls:
            sp = audio.SequencePlayer(["s1", "s2"], sequential=False)
            sp.play()
        group_cls.return_value.add.assert_any_call("s1")
        group_cls.return_value.add.assert_any_call("s2")
        player_cls.return_value.queue.assert_called_once_with(group_cls.return_value)
        player_cls.return_value.play.assert_called_once()


class TestSequentialMode:
    def _make(self, sources):
        players = []

        def new_player():
            p = MagicMock()
            players.append(p)
            return p

        patcher = patch.object(audio, "AudioPlayer", side_effect=new_player)
        patcher.start()
        sp = audio.SequencePlayer(sources, sequential=True)
        return sp, players, patcher

    def test_plays_sources_one_after_the_other(self):
        sp, players, patcher = self._make(["s1", "s2"])
        try:
            sp.play()
            assert players[-1].queue.call_args[0][0] == "s1"
            sp._next(0)  # end of s1
            assert players[-1].queue.call_args[0][0] == "s2"
            assert sp.source == "s2"
            sp._next(0)  # end of s2
            assert sp.source is None
            assert len(players) == 2
        finally:
            patcher.stop()

    def test_pause_then_play_restarts_current_sound(self):
        sp, players, patcher = self._make(["s1", "s2"])
        try:
            sp.play()
            sp._next(0)
            sp.pause()
            players[-1].delete.assert_called_once()
            sp.play()
            assert players[-1].queue.call_args[0][0] == "s2"
        finally:
            patcher.stop()

    def test_next_after_pause_is_ignored(self):
        sp, _players, patcher = self._make(["s1", "s2"])
        try:
            sp.play()
            sp.pause()
            sp._next(0)
            assert sp.source == "s1"
        finally:
            patcher.stop()

    def test_volume_applies_to_current_player(self):
        sp, players, patcher = self._make(["s1"])
        try:
            sp.play()
            sp.volume = 0.0
            assert players[-1].volume == 0.0
        finally:
            patcher.stop()

    def test_empty_sequence_does_nothing(self):
        sp, players, patcher = self._make([])
        try:
            sp.play()
            assert sp.source is None
            assert players == []
        finally:
            patcher.stop()


class TestLoadSound:
    def test_sounds_are_cached(self):
        audio._cache.clear()
        with patch.object(audio, "load_audio", side_effect=lambda *a, **k: object()) as load:
            first = audio.load_sound("x.wav")
            second = audio.load_sound("x.wav")
        assert first is second
        load.assert_called_once()

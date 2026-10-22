"""Tests for core.pseudorandom - Seeded random generation."""

import random
from unittest.mock import patch


class TestPluginAliasToInt:
    def test_communications(self):
        """'communications' maps to index 0."""
        from core.pseudorandom import plugin_alias_to_int

        assert plugin_alias_to_int("communications") == 0

    def test_sysmon(self):
        """'sysmon' maps to index 1."""
        from core.pseudorandom import plugin_alias_to_int

        assert plugin_alias_to_int("sysmon") == 1

    def test_unknown_raises(self):
        """Unknown plugin alias raises ValueError."""
        import pytest

        from core.pseudorandom import plugin_alias_to_int

        with pytest.raises(ValueError):
            plugin_alias_to_int("unknown_plugin")


class TestReplaySeed:
    def test_replay_uses_the_seeds_of_the_replayed_session(self, mock_logger):
        """Replaying session 4 among 10 sessions draws the same values as session 4 did."""
        import core.pseudorandom as pseudorandom

        mock_logger.session_id = 4
        with patch.object(pseudorandom, "REPLAY_MODE", False):
            session_seed = pseudorandom.set_seed("sysmon", 100)

        with (
            patch.object(pseudorandom, "REPLAY_MODE", True),
            patch.object(pseudorandom, "find_the_last_session_number", return_value=10),
        ):
            pseudorandom.set_replay_session_id(4)
            try:
                assert pseudorandom.set_seed("sysmon", 100) == session_seed
            finally:
                pseudorandom.set_replay_session_id(None)


class TestRandomSeed:
    """random_seed of config.ini: the same draws for every participant (each had the draws of its session number)."""

    def test_the_same_draws_whatever_the_session(self, mock_logger):
        import core.pseudorandom as pseudorandom

        draws = []
        for session_id in (3, 731004):
            mock_logger.session_id = session_id
            with patch.object(pseudorandom, "get_random_seed", return_value=42):
                draws.append(pseudorandom.set_seed("sysmon", 100))
        assert draws[0] == draws[1]

    def test_the_session_number_by_default(self, mock_logger):
        import core.pseudorandom as pseudorandom

        mock_logger.session_id = 3
        with patch.object(pseudorandom, "get_random_seed", return_value=None):
            assert pseudorandom.set_seed("sysmon", 100) == 3 + 1 + 100 + 0


class TestSetSeed:
    def test_deterministic(self):
        """Same inputs should produce the same seed."""
        from core.pseudorandom import set_seed

        set_seed("communications", 100, add=0)
        val1 = random.random()

        set_seed("communications", 100, add=0)
        val2 = random.random()
        assert val1 == val2

    def test_different_time_different_seed(self):
        """Different times produce different seeds."""
        from core.pseudorandom import set_seed

        set_seed("communications", 100)
        val1 = random.random()

        set_seed("communications", 200)
        val2 = random.random()
        assert val1 != val2

    def test_different_plugin_different_seed(self):
        """Different plugins produce different seeds."""
        from core.pseudorandom import set_seed

        set_seed("communications", 100)
        val1 = random.random()

        set_seed("sysmon", 100)
        val2 = random.random()
        assert val1 != val2

    def test_add_parameter_changes_seed(self):
        """The 'add' offset changes the seed."""
        from core.pseudorandom import set_seed

        set_seed("communications", 100, add=0)
        val1 = random.random()

        set_seed("communications", 100, add=1)
        val2 = random.random()
        assert val1 != val2


class TestRandomFunctions:
    @patch("core.pseudorandom.get_logger")
    def test_choice_returns_from_list(self, mock_logger):
        """Returned item belongs to the source list."""
        from core.pseudorandom import choice

        items = ["a", "b", "c", "d", "e"]
        result = choice(items, "communications", 100)
        assert result in items

    @patch("core.pseudorandom.get_logger")
    def test_choice_deterministic(self, mock_logger):
        """Same inputs yield same choice."""
        from core.pseudorandom import choice

        items = ["a", "b", "c", "d", "e"]
        r1 = choice(items, "communications", 100)
        r2 = choice(items, "communications", 100)
        assert r1 == r2

    @patch("core.pseudorandom.get_logger")
    def test_randint_in_range(self, mock_logger):
        """Random int falls within [low, high]."""
        from core.pseudorandom import randint

        result = randint(1, 10, "communications", 100)
        assert 1 <= result <= 10

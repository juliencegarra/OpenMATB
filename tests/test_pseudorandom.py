"""Tests for core.pseudorandom - Seeded random generation."""

import random
from unittest.mock import patch, MagicMock


class TestPluginAliasToInt:
    def test_communications(self):
        """'communications' maps to index 0."""
        from core.pseudorandom import plugin_alias_to_int
        assert plugin_alias_to_int('communications') == 0

    def test_sysmon(self):
        """'sysmon' maps to index 1."""
        from core.pseudorandom import plugin_alias_to_int
        assert plugin_alias_to_int('sysmon') == 1

    def test_unknown_raises(self):
        """Unknown plugin alias raises ValueError."""
        from core.pseudorandom import plugin_alias_to_int
        import pytest
        with pytest.raises(ValueError):
            plugin_alias_to_int('unknown_plugin')


class TestSetSeed:
    def test_deterministic(self):
        """Same inputs should produce the same seed."""
        from core.pseudorandom import set_seed
        set_seed('communications', 100, add=0)
        val1 = random.random()

        set_seed('communications', 100, add=0)
        val2 = random.random()
        assert val1 == val2

    def test_different_time_different_seed(self):
        """Different times produce different seeds."""
        from core.pseudorandom import set_seed
        set_seed('communications', 100)
        val1 = random.random()

        set_seed('communications', 200)
        val2 = random.random()
        assert val1 != val2

    def test_different_plugin_different_seed(self):
        """Different plugins produce different seeds."""
        from core.pseudorandom import set_seed
        set_seed('communications', 100)
        val1 = random.random()

        set_seed('sysmon', 100)
        val2 = random.random()
        assert val1 != val2

    def test_add_parameter_changes_seed(self):
        """The 'add' offset changes the seed."""
        from core.pseudorandom import set_seed
        set_seed('communications', 100, add=0)
        val1 = random.random()

        set_seed('communications', 100, add=1)
        val2 = random.random()
        assert val1 != val2


class TestRandomFunctions:
    @patch('core.pseudorandom.logger')
    def test_choice_returns_from_list(self, mock_logger):
        """Returned item belongs to the source list."""
        from core.pseudorandom import choice
        items = ['a', 'b', 'c', 'd', 'e']
        result = choice(items, 'communications', 100)
        assert result in items

    @patch('core.pseudorandom.logger')
    def test_choice_deterministic(self, mock_logger):
        """Same inputs yield same choice."""
        from core.pseudorandom import choice
        items = ['a', 'b', 'c', 'd', 'e']
        r1 = choice(items, 'communications', 100)
        r2 = choice(items, 'communications', 100)
        assert r1 == r2

    @patch('core.pseudorandom.logger')
    def test_randint_in_range(self, mock_logger):
        """Random int falls within [low, high]."""
        from core.pseudorandom import randint
        result = randint(1, 10, 'communications', 100)
        assert 1 <= result <= 10

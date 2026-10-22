"""The scenarios shipped in includes/scenarios (and the manual test ones of tests/scenarios) load without any error or warning.

The real plugins validate each line, so a deprecated command (e.g. pumpstatus, cutofffrequency), an unknown
parameter or an invalid value in a bundled scenario fails here, even when it is only a non-fatal warning.
"""

from itertools import count
from pathlib import Path
from string import ascii_uppercase
from unittest.mock import MagicMock, patch

import pytest

import core.constants
from core.scenario import Scenario

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = ROOT / "includes" / "scenarios"
# Scenarios written by the generator stay on the computer that made them (not bundled). The manual test scenarios
# (tests/scenarios: not listed in the scenario selection) are checked too
BUNDLED_SCENARIOS = sorted(
    p for p in SCENARIOS_DIR.rglob("*.txt") if "generated" not in p.relative_to(SCENARIOS_DIR).parts
) + sorted((ROOT / "tests" / "scenarios").glob("*.txt"))


def _distinct_callsigns():
    """The rstr mock of conftest always gives the same callsign: communications would never find other ones"""
    n = count()
    return lambda pattern: "".join(ascii_uppercase[int(d)] for d in f"{next(n):03d}")


def test_bundled_scenarios_are_found():
    assert len(BUNDLED_SCENARIOS) > 0


@pytest.mark.parametrize("path", BUNDLED_SCENARIOS, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_bundled_scenario_has_no_error(path, tmp_path, mock_logger):
    errors = MagicMock()
    errors.errors_list = []
    errors.some_fatals = False  # A MagicMock attribute is truthy: the plugins would not even be loaded

    def add_error(message, fatal=False):
        errors.errors_list.append(message)
        errors.some_fatals = errors.some_fatals or fatal

    errors.add_error.side_effect = add_error
    with (
        patch("core.scenario.get_errors", return_value=errors),
        patch("core.pseudorandom.rstrxeger", _distinct_callsigns()),
        patch.dict(core.constants.PATHS, {"SCENARIO_ERRORS": tmp_path / "errors.log"}),
    ):
        scenario = Scenario(scenario_path=path)
    log = tmp_path / "errors.log"
    assert errors.errors_list == [], log.read_text(encoding="utf-8") if log.exists() else ""
    assert len(scenario.plugins) > 0


@pytest.mark.parametrize(
    "path", sorted((ROOT / "includes" / "scenarios").glob("**/*.txt")), ids=lambda p: p.relative_to(ROOT).as_posix()
)
def test_bundled_scenario_has_a_title(path):
    """Each scenario of the selector has a "# title: ..." comment before its first command."""
    from core.selector import TITLE_PATTERN

    header = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip() and not line.strip().startswith("#"):
            break
        header.append(line.strip())
    assert any(TITLE_PATTERN.fullmatch(line) for line in header)

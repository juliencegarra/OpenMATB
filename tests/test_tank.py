"""Tests for core/widgets/tank.py — the drawn levels follow the parameters."""

from unittest.mock import patch

import pytest

from core.container import Container


@pytest.fixture
def tank(mock_logger, mock_window):
    """A real Tank (target 2500 +/- 250, max 4000) with mocked rendering deps."""
    with patch(
        "core.widgets.abstractwidget.get_conf_value",
        side_effect=lambda s, k, **kw: "Sans" if k == "font_name" else False,
    ):
        from core.widgets.tank import Tank

        container = Container("tank", 100, 100, 100, 400)
        return Tank(
            "tank_a",
            container,
            letter="a",
            level=2500,
            fluid_label="2500",
            level_max=4000,
            target=2500,
            toleranceradius=250,
            infoside="left",
        )


class TestTolerance:
    def test_band_follows_a_new_target(self, tank):
        """resman;tank-a-target;2000: the band is drawn around 2000, where the in-tolerance data are computed."""
        tank.set_tolerance_radius(250, 2000, 4000)
        assert tank.vertex["tolerance"].y == pytest.approx(tank.get_y_of(2000 - 250, 4000))

    def test_band_follows_a_new_maximum(self, tank):
        tank.set_fluid_level(2500, 5000)  # Resman refreshes the fluid first, with the same new maximum
        tank.set_tolerance_radius(250, 2500, 5000)
        assert tank.vertex["tolerance"].y == pytest.approx(tank.get_y_of(2500 - 250, 5000))
        assert tank.vertex["tolerance"].height == pytest.approx(tank.get_y_of(500, 5000) - tank.get_y_of(0, 5000))


class TestFluid:
    def test_fluid_follows_a_new_maximum(self, tank):
        tank.set_fluid_level(1000, 4000)
        tank.set_fluid_level(1000, 2000)  # resman;tank-a-max;2000
        _, _, _, y2 = tank.container.get_x1y1x2y2()
        assert tank.vertex["fluid"].height == pytest.approx(tank.get_y_of(1000, 2000) - y2)

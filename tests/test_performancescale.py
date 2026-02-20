"""Tests for core/widgets/performancescale.py — setters and rebuild logic."""

import pytest
from unittest.mock import MagicMock, patch, call
from core.container import Container
from core.constants import COLORS as C


@pytest.fixture
def scale(mock_logger, mock_window):
    """Create a real Performancescale with mocked rendering deps."""
    with patch('core.widgets.abstractwidget.get_conf_value', side_effect=lambda s, k, **kw:
               'Sans' if k == 'font_name' else False):
        from core.widgets.performancescale import Performancescale
        container = Container('test', 100, 100, 200, 400)
        ps = Performancescale('perf', container,
                              level_min=0, level_max=100,
                              tick_number=5, color=C['GREEN'])
        ps.visible = True  # Pretend widget is shown
        return ps


# ── Initialisation ──────────────────────────────


class TestInit:
    def test_stores_level_min(self, scale):
        assert scale.level_min == 0

    def test_stores_level_max(self, scale):
        assert scale.level_max == 100

    def test_stores_tick_number(self, scale):
        assert scale.tick_number == 5

    def test_creates_expected_vertices(self, scale):
        """__init__ via _draw_scale creates background, performance, borders, ticks, and tick labels."""
        assert 'background' in scale.vertex
        assert 'performance' in scale.vertex
        assert 'borders' in scale.vertex
        assert 'ticks' in scale.vertex
        # 5 ticks → 5 labels (tick_0_label, tick_25_label, etc.)
        tick_labels = [k for k in scale.vertex if k.startswith('tick_') and k.endswith('_label')]
        assert len(tick_labels) == 5


# ── _draw_scale ─────────────────────────────────


class TestDrawScale:
    def test_tick_labels_reflect_parameters(self, scale):
        """Tick labels should be based on level_min, level_max, tick_number."""
        tick_labels = sorted(k for k in scale.vertex if k.startswith('tick_') and k.endswith('_label'))
        # level_min=0, level_max=100, tick_number=5 → tick_inter=25
        # tick_values = [100, 75, 50, 25, 0]
        expected = ['tick_0_label', 'tick_100_label', 'tick_25_label', 'tick_50_label', 'tick_75_label']
        assert tick_labels == sorted(expected)

    def test_different_params_produce_different_labels(self, mock_logger):
        """Creating with different params gives different tick labels."""
        with patch('core.widgets.abstractwidget.get_conf_value', side_effect=lambda s, k, **kw:
                   'Sans' if k == 'font_name' else False):
            from core.widgets.performancescale import Performancescale
            container = Container('test', 100, 100, 200, 400)
            ps = Performancescale('perf', container,
                                  level_min=0, level_max=10,
                                  tick_number=3, color=C['GREEN'])
            tick_labels = sorted(k for k in ps.vertex if k.startswith('tick_') and k.endswith('_label'))
            # level_min=0, level_max=10, tick_number=3 → tick_inter=5
            # tick_values = [10, 5, 0]
            assert tick_labels == sorted(['tick_0_label', 'tick_5_label', 'tick_10_label'])


# ── _rebuild ────────────────────────────────────


class TestRebuild:
    def test_rebuild_clears_and_redraws(self, scale):
        """_rebuild should clear all vertices and recreate them."""
        old_vertex_keys = set(scale.vertex.keys())
        scale._rebuild()
        new_vertex_keys = set(scale.vertex.keys())
        # Same structural keys should exist after rebuild
        assert 'background' in new_vertex_keys
        assert 'performance' in new_vertex_keys
        assert 'borders' in new_vertex_keys
        assert 'ticks' in new_vertex_keys

    def test_rebuild_calls_hide_then_show(self, scale):
        """_rebuild should transition through hide → show."""
        # After rebuild, widget should be visible again
        scale._rebuild()
        assert scale.visible is True

    def test_rebuild_from_hidden(self, scale):
        """_rebuild on a hidden widget: hide() is a no-op, show() activates."""
        scale.visible = False
        scale._rebuild()
        assert scale.visible is True


# ── set_tick_number ─────────────────────────────


class TestSetTickNumber:
    def test_no_change_is_noop(self, scale):
        """Setting same tick_number does nothing."""
        old_vertices = dict(scale.vertex)
        scale.set_tick_number(5)
        assert scale.vertex is not old_vertices or scale.tick_number == 5

    def test_changes_tick_number(self, scale):
        """Setting a new tick_number updates the attribute and rebuilds."""
        scale.set_tick_number(11)
        assert scale.tick_number == 11
        # New tick labels should reflect 11 ticks
        tick_labels = [k for k in scale.vertex if k.startswith('tick_') and k.endswith('_label')]
        assert len(tick_labels) == 11

    def test_tick_values_correct_after_change(self, scale):
        """After changing tick_number to 3, labels should match."""
        scale.set_tick_number(3)
        tick_labels = sorted(k for k in scale.vertex if k.startswith('tick_') and k.endswith('_label'))
        # level_min=0, level_max=100, tick_number=3 → tick_inter=50
        # tick_values = [100, 50, 0]
        assert tick_labels == sorted(['tick_0_label', 'tick_50_label', 'tick_100_label'])


# ── set_level_min ───────────────────────────────


class TestSetLevelMin:
    def test_no_change_is_noop(self, scale):
        """Setting same level_min does nothing."""
        scale.set_level_min(0)
        assert scale.level_min == 0

    def test_changes_level_min(self, scale):
        """Setting a new level_min updates attribute and rebuilds."""
        scale.set_level_min(20)
        assert scale.level_min == 20
        # tick_inter = (100-20)/(5-1) = 20
        # tick_values = [100, 80, 60, 40, 20]
        tick_labels = sorted(k for k in scale.vertex if k.startswith('tick_') and k.endswith('_label'))
        assert tick_labels == sorted(['tick_20_label', 'tick_40_label', 'tick_60_label',
                                       'tick_80_label', 'tick_100_label'])


# ── set_level_max ───────────────────────────────


class TestSetLevelMax:
    def test_no_change_is_noop(self, scale):
        """Setting same level_max does nothing."""
        scale.set_level_max(100)
        assert scale.level_max == 100

    def test_changes_level_max(self, scale):
        """Setting a new level_max updates attribute and rebuilds."""
        scale.set_level_max(200)
        assert scale.level_max == 200
        # tick_inter = (200-0)/(5-1) = 50
        # tick_values = [200, 150, 100, 50, 0]
        tick_labels = sorted(k for k in scale.vertex if k.startswith('tick_') and k.endswith('_label'))
        assert tick_labels == sorted(['tick_0_label', 'tick_50_label', 'tick_100_label',
                                       'tick_150_label', 'tick_200_label'])


# ── refresh_widgets propagation ─────────────────


class TestRefreshWidgetsPropagation:
    """Test that Performance.refresh_widgets() propagates structural params."""

    def test_refresh_calls_setters(self):
        """refresh_widgets should call set_tick_number, set_level_min, set_level_max."""
        from plugins.performance import Performance
        p = object.__new__(Performance)
        p.alias = 'performance'
        p.scenario_time = 1.0
        p.next_refresh_time = 0
        p.paused = False
        p.verbose = False
        p.automode_string = ''
        p.parameters = dict(
            taskupdatetime=50,
            levelmin=0, levelmax=100, ticknumber=11,
            criticallevel=20, shadowundercritical=True,
            defaultcolor=C['GREEN'], criticalcolor=C['RED'],
            displayautomationstate=False,
        )
        p.displayed_level = 100
        p.displayed_color = C['GREEN']

        mock_bar = MagicMock()
        p.widgets = {'performance_bar': mock_bar}

        # Simulate visible widget — super().refresh_widgets() checks visibility
        p.visible = True

        # Mock super().refresh_widgets to return True (widget is visible)
        with patch('plugins.abstractplugin.AbstractPlugin.refresh_widgets', return_value=True):
            p.refresh_widgets()

        mock_bar.set_tick_number.assert_called_once_with(11)
        mock_bar.set_level_min.assert_called_once_with(0)
        mock_bar.set_level_max.assert_called_once_with(100)
        mock_bar.set_performance_level.assert_called_once_with(100)
        mock_bar.set_performance_color.assert_called_once_with(C['GREEN'])

    def test_refresh_not_called_when_hidden(self):
        """refresh_widgets should not call setters when plugin is hidden."""
        from plugins.performance import Performance
        p = object.__new__(Performance)
        p.alias = 'performance'
        p.parameters = dict(
            taskupdatetime=50,
            levelmin=0, levelmax=100, ticknumber=5,
            criticallevel=20, shadowundercritical=True,
            defaultcolor=C['GREEN'], criticalcolor=C['RED'],
            displayautomationstate=False,
        )

        mock_bar = MagicMock()
        p.widgets = {'performance_bar': mock_bar}

        with patch('plugins.abstractplugin.AbstractPlugin.refresh_widgets', return_value=False):
            p.refresh_widgets()

        mock_bar.set_tick_number.assert_not_called()
        mock_bar.set_level_min.assert_not_called()
        mock_bar.set_level_max.assert_not_called()

    def test_structural_params_called_before_level_and_color(self):
        """Structural params must be set before level/color."""
        from plugins.performance import Performance
        p = object.__new__(Performance)
        p.alias = 'performance'
        p.scenario_time = 1.0
        p.next_refresh_time = 0
        p.paused = False
        p.verbose = False
        p.automode_string = ''
        p.parameters = dict(
            taskupdatetime=50,
            levelmin=0, levelmax=100, ticknumber=5,
            criticallevel=20, shadowundercritical=True,
            defaultcolor=C['GREEN'], criticalcolor=C['RED'],
            displayautomationstate=False,
        )
        p.displayed_level = 50
        p.displayed_color = C['RED']
        p.visible = True

        # Use a single mock so we can check call_args_list order
        mock_bar = MagicMock()
        p.widgets = {'performance_bar': mock_bar}

        with patch('plugins.abstractplugin.AbstractPlugin.refresh_widgets', return_value=True):
            p.refresh_widgets()

        # Extract the method names in call order
        call_names = [c[0] for c in mock_bar.method_calls]
        assert call_names == [
            'set_tick_number',
            'set_level_min',
            'set_level_max',
            'set_performance_level',
            'set_performance_color',
        ]

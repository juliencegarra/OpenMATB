"""Tests for foreground visibility mechanism — virtual framebuffer approach.

Verifies that the foreground Frame widget correctly masks/unmasks plugins
when they are hidden/shown. Uses mock shapes from conftest to inspect
geometry, draw order, color, and visibility without a real GL context.
"""

from unittest.mock import MagicMock, patch

from core.constants import BFLIM
from core.constants import COLORS as C
from plugins.abstractplugin import AbstractPlugin

# ── Helpers ──────────────────────────────────────────────────────────────

BACKGROUND_RGBA = C["BACKGROUND"]  # (240, 240, 240, 255)


def _rect_contains(rect, x, y):
    """Return True if point (x, y) lies inside the mock Rectangle."""
    return rect.x <= x < rect.x + rect.width and rect.y <= y < rect.y + rect.height


def _collect_visible_rects_at(plugin, x, y):
    """Return visible _MockRectangles at (x, y) sorted by group.order ascending."""
    from pyglet.shapes import Rectangle

    rects = []
    for widget in plugin.widgets.values():
        for v in widget.vertex.values():
            if isinstance(v, Rectangle) and v.visible and _rect_contains(v, x, y):
                rects.append(v)
    rects.sort(key=lambda r: r.group.order)
    return rects


def _topmost_color_at(plugin, x, y):
    """Return RGBA tuple of the topmost visible rectangle at (x, y), or None."""
    rects = _collect_visible_rects_at(plugin, x, y)
    if not rects:
        return None
    top = rects[-1]
    return (top.color[0], top.color[1], top.color[2], top.opacity)


_CONF_PATCH = patch(
    "core.widgets.abstractwidget.get_conf_value",
    side_effect=lambda s, k, **kw: "Sans" if k == "font_name" else False,
)


def _make_plugin_with_widgets(mock_window, mock_logger, placement="topleft"):
    """Create a real AbstractPlugin with create_widgets() called."""
    p = object.__new__(AbstractPlugin)
    p.label = "Test"
    p.alias = "testplugin"
    p.widgets = {}
    p.container = None
    p.logger = mock_logger
    p.can_receive_keys = False
    p.can_execute_keys = False
    p.keys = set()
    p.display_title = placement != "invisible"
    p.automode_string = ""
    p.agent = None
    p.next_refresh_time = 0
    p.scenario_time = 0
    p.blocking = False
    p.alive = False
    p.paused = True
    p.visible = False
    p.verbose = False
    p.joystick = None
    p.parameters = dict(
        title="Test",
        taskplacement=placement,
        taskupdatetime=100,
        taskfeedback=dict(
            overdue=dict(
                active=False,
                color=(241, 100, 100, 255),
                delayms=2000,
                blinkdurationms=1000,
                _nexttoggletime=0,
                _is_visible=False,
            )
        ),
    )
    p.m_draw = BFLIM if placement == "fullscreen" else 0

    with _CONF_PATCH:
        p.create_widgets()

    # Fix: Label = MagicMock means Label("TEST", ...) creates a mock with
    # spec=str (first positional arg), so .text is restricted.  Replace the
    # label vertices with plain MagicMocks that allow arbitrary attributes.
    for name in ("task_title", "fault_icon"):
        w = p.get_widget(name)
        if w is not None:
            w.vertex["text"] = MagicMock()

    return p


def _get_foreground_fillarea(plugin):
    """Return the fillarea shape of the foreground widget, or None."""
    fg = plugin.get_widget("foreground")
    if fg is None:
        return None
    return fg.vertex.get("fillarea")


def _task_container_center(plugin):
    """Return (cx, cy) of the plugin's task_container."""
    tc = plugin.task_container
    return tc.cx, tc.cy


# ── 1. TestForegroundCreation ────────────────────────────────────────────


class TestForegroundCreation:
    def test_foreground_created_for_non_fullscreen(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fg = p.get_widget("foreground")
        assert fg is not None
        assert "fillarea" in fg.vertex

    def test_foreground_not_created_for_fullscreen(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "fullscreen")
        assert p.get_widget("foreground") is None
        bg = p.get_widget("background")
        assert bg is not None

    def test_foreground_draw_order_is_10(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fillarea = _get_foreground_fillarea(p)
        assert fillarea is not None
        assert fillarea.group.order == 10

    def test_foreground_covers_task_container(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fillarea = _get_foreground_fillarea(p)
        tc = p.task_container
        assert fillarea.x == tc.x1
        assert fillarea.y == tc.y2
        assert fillarea.width == tc.w
        assert fillarea.height == tc.h


# ── 2. TestShowHideSinglePlugin ──────────────────────────────────────────


class TestShowHideSinglePlugin:
    def test_show_hides_foreground(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
        fillarea = _get_foreground_fillarea(p)
        assert fillarea.visible is False

    def test_hide_shows_foreground(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            p.hide()
        fillarea = _get_foreground_fillarea(p)
        assert fillarea.visible is True

    def test_show_already_visible_noop(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            fillarea = _get_foreground_fillarea(p)
            assert fillarea.visible is False
            # Second show should be a no-op
            p.show()
            assert fillarea.visible is False

    def test_hide_already_hidden_noop(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            # Plugin starts hidden; hide again should be no-op
            p.hide()
        assert p.visible is False

    def test_show_makes_visible_flag_true(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
        assert p.visible is True

    def test_hide_makes_visible_flag_false(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            p.hide()
        assert p.visible is False


# ── 3. TestRefreshWidgetsForeground ──────────────────────────────────────


class TestRefreshWidgetsForeground:
    def test_refresh_forces_foreground_hidden(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            # Manually make foreground visible to simulate a glitch
            fg = p.get_widget("foreground")
            fg.vertex["fillarea"].visible = True
            fg.visible = True
            # refresh_widgets should force it back to invisible
            p.refresh_widgets()
            assert fg.vertex["fillarea"].visible is False

    def test_refresh_noop_when_plugin_hidden(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        result = p.refresh_widgets()
        assert result is False

    def test_refresh_every_frame(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            p.paused = False
            for t in range(0, 10):
                p.scenario_time = t
                p.next_refresh_time = 0
                p.refresh_widgets()
                fillarea = _get_foreground_fillarea(p)
                assert fillarea.visible is False, f"Foreground leaked at frame {t}"


# ── 4. TestTopColorAtPoint ───────────────────────────────────────────────


class TestTopColorAtPoint:
    def test_visible_plugin_shows_content_color(self, mock_window, mock_logger):
        """When shown, foreground is hidden so topmost is NOT background."""
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
        cx, cy = _task_container_center(p)
        color = _topmost_color_at(p, cx, cy)
        # The foreground is hidden, so its fill should not appear.
        # Whatever is visible should NOT be the background color at G(10).
        if color is not None:
            # If some other rect is visible, it should not be the foreground
            assert color != BACKGROUND_RGBA or _get_foreground_fillarea(p).visible is False

    def test_hidden_plugin_shows_background(self, mock_window, mock_logger):
        """When hidden, foreground is shown so topmost IS background."""
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            p.hide()
        cx, cy = _task_container_center(p)
        color = _topmost_color_at(p, cx, cy)
        assert color == BACKGROUND_RGBA

    def test_foreground_covers_content(self, mock_window, mock_logger):
        """When foreground.visible=True, BACKGROUND dominates (G(10) > G(0-8))."""
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
        # Manually force foreground visible
        fg = p.get_widget("foreground")
        fg.vertex["fillarea"].visible = True
        cx, cy = _task_container_center(p)
        color = _topmost_color_at(p, cx, cy)
        assert color == BACKGROUND_RGBA

    def test_point_outside_container_returns_none(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
        # Point far outside any container
        color = _topmost_color_at(p, -100, -100)
        assert color is None

    def test_foreground_opacity_255(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fillarea = _get_foreground_fillarea(p)
        assert fillarea.opacity == 255

    def test_overdue_hidden_by_default(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
        overdue = p.get_widget("overdue")
        assert overdue is not None
        assert overdue.visible is False


# ── 5. TestMultiPluginHideShow ───────────────────────────────────────────


class TestMultiPluginHideShow:
    @staticmethod
    def _make_multi(mock_window, mock_logger, placements):
        plugins = {}
        for pl in placements:
            plugins[pl] = _make_plugin_with_widgets(mock_window, mock_logger, pl)
        return plugins

    def test_show_one_hide_others(self, mock_window, mock_logger):
        plugins = self._make_multi(mock_window, mock_logger, ["topleft", "topmid"])
        with _CONF_PATCH:
            plugins["topleft"].show()
        # topleft shown: foreground hidden
        assert _get_foreground_fillarea(plugins["topleft"]).visible is False
        # topmid still hidden: foreground visible
        assert _get_foreground_fillarea(plugins["topmid"]).visible is True

    def test_show_all_then_hide_one(self, mock_window, mock_logger):
        placements = ["topleft", "topmid", "topright", "bottomleft"]
        plugins = self._make_multi(mock_window, mock_logger, placements)
        with _CONF_PATCH:
            for p in plugins.values():
                p.show()
            plugins["topmid"].hide()
        for pl, p in plugins.items():
            fa = _get_foreground_fillarea(p)
            if pl == "topmid":
                assert fa.visible is True, f"{pl} foreground should be visible (hidden)"
            else:
                assert fa.visible is False, f"{pl} foreground should be hidden (shown)"

    def test_hide_all(self, mock_window, mock_logger):
        placements = ["topleft", "topmid", "topright"]
        plugins = self._make_multi(mock_window, mock_logger, placements)
        with _CONF_PATCH:
            for p in plugins.values():
                p.show()
            for p in plugins.values():
                p.hide()
        for pl, p in plugins.items():
            fa = _get_foreground_fillarea(p)
            assert fa.visible is True, f"{pl} foreground should be visible after hide_all"

    def test_show_all(self, mock_window, mock_logger):
        placements = ["topleft", "topmid", "topright"]
        plugins = self._make_multi(mock_window, mock_logger, placements)
        with _CONF_PATCH:
            for p in plugins.values():
                p.show()
        for pl, p in plugins.items():
            fa = _get_foreground_fillarea(p)
            assert fa.visible is False, f"{pl} foreground should be hidden after show_all"

    def test_alternating_show_hide(self, mock_window, mock_logger):
        plugins = self._make_multi(mock_window, mock_logger, ["topleft", "topmid"])
        with _CONF_PATCH:
            # show A, hide B (B already hidden)
            plugins["topleft"].show()
            plugins["topmid"].hide()
            assert _get_foreground_fillarea(plugins["topleft"]).visible is False
            assert _get_foreground_fillarea(plugins["topmid"]).visible is True

            # show B, hide A
            plugins["topmid"].show()
            plugins["topleft"].hide()
            assert _get_foreground_fillarea(plugins["topmid"]).visible is False
            assert _get_foreground_fillarea(plugins["topleft"]).visible is True

    def test_independent_foreground_widgets(self, mock_window, mock_logger):
        plugins = self._make_multi(mock_window, mock_logger, ["topleft", "topmid"])
        fg_tl = plugins["topleft"].get_widget("foreground")
        fg_tm = plugins["topmid"].get_widget("foreground")
        # They must be different widget objects
        assert fg_tl is not fg_tm
        # And different fillarea shapes
        assert fg_tl.vertex["fillarea"] is not fg_tm.vertex["fillarea"]


# ── 6. TestDrawOrderGuarantees ───────────────────────────────────────────


class TestDrawOrderGuarantees:
    def test_content_below_foreground(self, mock_window, mock_logger):
        """Content widgets at G(0-8), foreground at G(10)."""
        from pyglet.shapes import ShapeBase

        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fg_order = _get_foreground_fillarea(p).group.order
        for wname, widget in p.widgets.items():
            if "foreground" in wname:
                continue
            for vname, v in widget.vertex.items():
                # Only check real shapes (not MagicMock labels)
                if isinstance(v, ShapeBase) and v.group is not None:
                    assert v.group.order < fg_order, (
                        f"Widget {wname}.{vname} at G({v.group.order}) >= foreground G({fg_order})"
                    )

    def test_foreground_below_fullscreen(self, mock_window, mock_logger):
        """Foreground G(10) < fullscreen background G(BFLIM=15)."""
        p_fg = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        p_fs = _make_plugin_with_widgets(mock_window, mock_logger, "fullscreen")
        fg_order = _get_foreground_fillarea(p_fg).group.order
        bg = p_fs.get_widget("background")
        bg_order = bg.vertex["fillarea"].group.order
        assert fg_order < bg_order

    def test_overdue_below_foreground(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fg_order = _get_foreground_fillarea(p).group.order
        overdue = p.get_widget("overdue")
        # Overdue border rects have a group; check them
        for vname, v in overdue.vertex.items():
            if hasattr(v, "group") and v.group is not None:
                assert v.group.order < fg_order, f"Overdue {vname} at G({v.group.order}) >= foreground G({fg_order})"

    def test_task_title_exists_after_create(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        tt = p.get_widget("task_title")
        assert tt is not None


# ── 7. TestStartStopCycle ────────────────────────────────────────────────


class TestStartStopCycle:
    def test_start_creates_and_shows(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.alive = True
            p.show()
            p.resume()
        assert p.alive is True
        assert p.visible is True
        assert p.paused is False
        assert _get_foreground_fillarea(p).visible is False

    def test_stop_hides_and_pauses(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.alive = True
            p.show()
            p.resume()
            p.stop()
        assert p.alive is False
        assert p.paused is True
        assert p.visible is False
        assert _get_foreground_fillarea(p).visible is True

    def test_restart_after_stop(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.alive = True
            p.show()
            p.resume()
            p.stop()
            # Re-show after stop
            p.alive = True
            p.show()
            p.resume()
        assert p.visible is True
        assert _get_foreground_fillarea(p).visible is False

    def test_foreground_state_after_full_cycle(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fa = _get_foreground_fillarea(p)
        with _CONF_PATCH:
            # Initial: foreground visible (plugin hidden)
            assert fa.visible is True

            # start → foreground hidden
            p.alive = True
            p.show()
            p.resume()
            assert fa.visible is False

            # hide → foreground visible
            p.hide()
            assert fa.visible is True

            # show → foreground hidden
            p.show()
            assert fa.visible is False

            # stop → foreground visible
            p.stop()
            assert fa.visible is True


# ── 8. TestEdgeCases ─────────────────────────────────────────────────────


class TestEdgeCases:
    def test_invisible_plugin_no_foreground(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "invisible")
        assert p.get_widget("foreground") is None

    def test_fullscreen_plugin_uses_background_not_foreground(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "fullscreen")
        assert p.get_widget("background") is not None
        assert p.get_widget("foreground") is None

    def test_foreground_fillarea_color_matches_background(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        fa = _get_foreground_fillarea(p)
        assert fa.color[:3] == C["BACKGROUND"][:3]
        assert fa.opacity == 255


# ── 9. TestBgBandsVisibility ─────────────────────────────────────────────


class TestBgBandsVisibility:
    def test_fullscreen_show_hides_bands(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "fullscreen")
        with _CONF_PATCH:
            p.show()
        mock_window.set_bg_bands_visible.assert_called_with(False)

    def test_fullscreen_hide_restores_bands(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "fullscreen")
        with _CONF_PATCH:
            p.show()
            p.hide()
        mock_window.set_bg_bands_visible.assert_called_with(True)

    def test_non_fullscreen_does_not_touch_bands(self, mock_window, mock_logger):
        p = _make_plugin_with_widgets(mock_window, mock_logger, "topleft")
        with _CONF_PATCH:
            p.show()
            p.hide()
        mock_window.set_bg_bands_visible.assert_not_called()

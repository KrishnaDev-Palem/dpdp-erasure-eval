"""Unit tests for the pure figure-layout rules (no rendering required)."""

from __future__ import annotations

import pytest

from report.figures.layout import (
    annotation_fits,
    annotation_y,
    heatmap_text_color,
    horizontal_bar_annotation_x,
    rate_axis_ticks,
    rate_axis_upper_limit,
)


class TestRateAxisUpperLimit:
    def test_current_data_yields_twenty_percent(self) -> None:
        assert rate_axis_upper_limit(0.149) == pytest.approx(0.20)

    def test_upper_bound_exactly_on_five_point_multiple(self) -> None:
        # 0.15 + 0.02 margin = 0.17, so the next multiple is 0.20.
        assert rate_axis_upper_limit(0.15) == pytest.approx(0.20)

    def test_bound_plus_margin_exactly_on_multiple_does_not_round_up(self) -> None:
        # 0.13 + 0.02 lands exactly on 0.15 despite float noise.
        assert rate_axis_upper_limit(0.13) == pytest.approx(0.15)

    def test_bound_just_below_multiple(self) -> None:
        assert rate_axis_upper_limit(0.129) == pytest.approx(0.15)

    def test_bound_just_above_multiple(self) -> None:
        assert rate_axis_upper_limit(0.131) == pytest.approx(0.20)

    def test_zero_bound_still_leaves_margin(self) -> None:
        assert rate_axis_upper_limit(0.0) == pytest.approx(0.05)

    def test_full_rate_upper_bound(self) -> None:
        assert rate_axis_upper_limit(1.0) == pytest.approx(1.05)


class TestRateAxisTicks:
    def test_five_point_ticks_to_limit(self) -> None:
        assert rate_axis_ticks(0.20) == pytest.approx([0.0, 0.05, 0.10, 0.15, 0.20])

    def test_limit_not_on_step_keeps_ticks_below_limit(self) -> None:
        assert rate_axis_ticks(1.05, step=0.25) == pytest.approx([0.0, 0.25, 0.50, 0.75, 1.0])


class TestAnnotationPlacement:
    def test_annotation_sits_fixed_offset_above_whisker_cap(self) -> None:
        assert annotation_y(0.0, 0.149) == pytest.approx(0.159)

    def test_annotation_fits_with_clearance(self) -> None:
        assert annotation_fits(0.159, 0.20)

    def test_annotation_collision_detected(self) -> None:
        assert not annotation_fits(0.195, 0.20)

    def test_clearance_boundary_counts_as_fit(self) -> None:
        assert annotation_fits(0.19, 0.20)


class TestHeatmapTextColor:
    def test_dark_cell_gets_white_text(self) -> None:
        assert heatmap_text_color((0.49, 0.49, 0.49)) == "white"

    def test_light_cell_gets_black_text(self) -> None:
        assert heatmap_text_color((0.51, 0.51, 0.51)) == "black"

    def test_threshold_boundary_is_black(self) -> None:
        assert heatmap_text_color((0.5, 0.5, 0.5)) == "black"

    def test_rgba_alpha_channel_ignored(self) -> None:
        assert heatmap_text_color((0.1, 0.1, 0.1, 1.0)) == "white"


class TestHorizontalBarAnnotation:
    def test_long_bar_annotates_inside_near_base(self) -> None:
        x, placement = horizontal_bar_annotation_x(1.0, 0.0, 1.05)
        assert placement == "inside"
        assert x == pytest.approx(0.021)

    def test_short_bar_annotates_past_whisker_cap(self) -> None:
        x, placement = horizontal_bar_annotation_x(0.1, 0.2, 1.05)
        assert placement == "outside"
        assert x == pytest.approx(0.1 + 0.2 + 0.021)

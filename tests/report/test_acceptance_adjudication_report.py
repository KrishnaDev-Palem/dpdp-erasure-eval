"""Acceptance tests for adjudication report tables and cross-tier comparison."""

from __future__ import annotations

import pytest

from core.model import FakeModelSeam
from core.types import VERDICT_LANES
from report.adjudication_tables import (
    build_cross_tier_comparison,
    build_tier_adjudication_report,
)
from report.wilson import wilson_interval
from runners.autonomous.runner import run_autonomous_sweep
from runners.t1 import run_t1_sweep
from runners.t2 import run_t2_sweep
from runners.t3 import run_t3_sweep
from tests.report.conftest import (
    WILSON_TOLERANCE,
    hand_calculate_wilson_interval,
    make_hand_crafted_adjudication_scoring,
    make_tier_sweep_result,
    make_zero_denominator_adjudication_scoring,
)


def test_wilson_bounds_match_hand_calculated_adjudication_fixture() -> None:
    scoring = make_hand_crafted_adjudication_scoring()
    for rate in (
        scoring.over_erasure_rate,
        scoring.over_retention_rate,
        scoring.mis_escalation_rate,
    ):
        interval = wilson_interval(rate)
        expected_lower, expected_upper = hand_calculate_wilson_interval(rate)
        assert interval.lower == pytest.approx(expected_lower, abs=WILSON_TOLERANCE)
        assert interval.upper == pytest.approx(expected_upper, abs=WILSON_TOLERANCE)


def test_tier_report_rates_match_scoring_numerators() -> None:
    sweep = make_tier_sweep_result()
    report = build_tier_adjudication_report(sweep, sample_index=0)
    scoring = sweep.samples[0].scoring
    oe = report.primary_metrics.over_erasure.rate
    assert oe.numerator == scoring.over_erasure_rate.numerator
    assert oe.denominator == scoring.over_erasure_rate.denominator
    or_rate = report.primary_metrics.over_retention.rate
    assert or_rate.numerator == scoring.over_retention_rate.numerator
    me_rate = report.primary_metrics.mis_escalation.rate
    assert me_rate.numerator == scoring.mis_escalation_rate.numerator


def test_tier_report_wilson_intervals_match_hand_calculated() -> None:
    sweep = make_tier_sweep_result()
    report = build_tier_adjudication_report(sweep, sample_index=0)
    for rate_ci in (
        report.primary_metrics.over_erasure,
        report.primary_metrics.over_retention,
        report.primary_metrics.mis_escalation,
    ):
        expected_lower, expected_upper = hand_calculate_wilson_interval(rate_ci.rate)
        assert rate_ci.interval is not None
        assert rate_ci.interval.lower == pytest.approx(expected_lower, abs=WILSON_TOLERANCE)
        assert rate_ci.interval.upper == pytest.approx(expected_upper, abs=WILSON_TOLERANCE)


def test_zero_denominator_rates_have_null_value_and_interval() -> None:
    from runners.types import TierSweepResult

    scoring = make_zero_denominator_adjudication_scoring()
    from tests.report.conftest import make_sample_rollups, make_variance_summary

    sweep = TierSweepResult(
        tier="t1",
        runner_id="t1",
        model_id="primary",
        cache_mode="offline",
        export_agent_sha="b" * 40,
        samples=make_sample_rollups(scoring),
        variance=make_variance_summary(scoring),
    )
    report = build_tier_adjudication_report(sweep)
    for rate_ci in (
        report.primary_metrics.over_erasure,
        report.primary_metrics.over_retention,
        report.primary_metrics.mis_escalation,
    ):
        assert rate_ci.rate.value is None
        assert rate_ci.interval is None


def test_tier_report_includes_confusion_matrix_and_five_sample_rollups() -> None:
    sweep = make_tier_sweep_result()
    report = build_tier_adjudication_report(sweep, sample_index=0)
    assert set(report.confusion_matrix.keys()) == set(VERDICT_LANES)
    assert len(report.sample_rollups) == 5
    assert report.variance.over_erasure.constant_across_samples is True


def test_tier_report_no_blended_accuracy(
    fake_seam: FakeModelSeam,
    export_dir,
    cache_dir,
) -> None:
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    report = build_tier_adjudication_report(result)
    dumped = report.model_dump()
    for field in ("accuracy", "micro_f1", "blended_score", "blended_accuracy"):
        assert field not in dumped


def test_cross_tier_comparison_includes_all_four_runners(
    fake_seam: FakeModelSeam,
    export_dir,
    cache_dir,
) -> None:
    t1 = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    t2 = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    t3 = run_t3_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    autonomous = run_autonomous_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    comparison = build_cross_tier_comparison(t1, t2, t3, autonomous, sample_index=0)
    tiers = {row.tier for row in comparison.rows}
    assert tiers == {"t1", "t2", "t3", "autonomous"}
    dumped = comparison.model_dump()
    for field in ("accuracy", "micro_f1", "blended_score", "blended_accuracy"):
        assert field not in dumped


def test_cross_tier_rates_match_embedded_scoring(
    fake_seam: FakeModelSeam,
    export_dir,
    cache_dir,
) -> None:
    t1 = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    t2 = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    t3 = run_t3_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    autonomous = run_autonomous_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    comparison = build_cross_tier_comparison(t1, t2, t3, autonomous, sample_index=0)
    sweeps = {"t1": t1, "t2": t2, "t3": t3, "autonomous": autonomous}
    for row in comparison.rows:
        scoring = sweeps[row.tier].samples[0].scoring
        assert row.over_erasure.rate.numerator == scoring.over_erasure_rate.numerator
        assert row.over_retention.rate.numerator == scoring.over_retention_rate.numerator
        assert row.mis_escalation.rate.numerator == scoring.mis_escalation_rate.numerator

"""Acceptance tests for per-cell and per-stratum report tables."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.export import load_agent_cases
from core.model import FakeModelSeam
from core.scoring import score_adjudication, score_adjudication_grouped
from core.types import STRATA_GROUP_FIELDS, ModelVerdict
from report.adjudication_tables import (
    build_tier_adjudication_report,
    format_adjudication_report,
)
from report.wilson import wilson_interval
from runners.t1 import run_t1_sweep
from runners.types import SampleRollup, TierSweepResult
from tests.report.conftest import (
    WILSON_TOLERANCE,
    hand_calculate_wilson_interval,
    make_variance_summary,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "core" / "fixtures" / "agent_cases.yaml"


def _fixture_report(*, flip_payment: bool = True):
    subjects = load_agent_cases(FIXTURE_PATH)
    locations = {
        location.location_id: location for subject in subjects for location in subject.locations
    }
    pairs = []
    for location in locations.values():
        verdict = location.expected.verdict
        if flip_payment and location.location_id == "ordinary_erase_payment:00000":
            verdict = "retain"
        pairs.append(
            (
                ModelVerdict(location_id=location.location_id, verdict=verdict),
                location.expected,
            )
        )
    scoring = score_adjudication(pairs)
    grouped = score_adjudication_grouped(pairs, locations)
    samples = [
        SampleRollup(
            sample_index=index,
            scoring=scoring,
            total_subjects=len(subjects),
            scored_location_pairs=scoring.total_cases,
            grouped=grouped,
        )
        for index in range(5)
    ]
    sweep = TierSweepResult(
        tier="t1",
        runner_id="t1",
        model_id="primary",
        cache_mode="offline",
        export_agent_sha="d" * 40,
        samples=samples,
        variance=make_variance_summary(scoring),
    )
    return build_tier_adjudication_report(sweep, sample_index=0), grouped, scoring


def test_coverage_fixture_produces_per_cell_and_per_stratum_rows() -> None:
    report, grouped, _scoring = _fixture_report()
    assert {row.key for row in report.by_cell} == set(grouped.by_cell)
    assert {table.field for table in report.by_stratum} == set(STRATA_GROUP_FIELDS)
    for table in report.by_stratum:
        assert {row.key for row in table.rows} == set(grouped.by_stratum[table.field])
        for row in table.rows:
            source = grouped.by_stratum[table.field][row.key]
            assert row.metrics.over_erasure.rate == source.over_erasure_rate
            assert row.scored_location_pairs == source.total_cases


def test_grouped_report_rows_match_score_adjudication() -> None:
    report, grouped, scoring = _fixture_report()
    assert report.primary_metrics.over_erasure.rate == scoring.over_erasure_rate
    payment = next(row for row in report.by_cell if row.key == "ordinary_erase_payment")
    payment_group = grouped.by_cell["ordinary_erase_payment"]
    assert payment.metrics.over_retention.rate == payment_group.over_retention_rate
    assert payment.metrics.over_retention.rate.numerator == 1
    eval_split = next(
        row
        for table in report.by_stratum
        if table.field == "split"
        for row in table.rows
        if row.key == "eval"
    )
    assert eval_split.scored_location_pairs == grouped.by_stratum["split"]["eval"].total_cases


def test_grouped_wilson_intervals_use_shared_helper() -> None:
    report, _grouped, _scoring = _fixture_report()
    for row in report.by_cell:
        for rate_ci in (
            row.metrics.over_erasure,
            row.metrics.over_retention,
            row.metrics.mis_escalation,
        ):
            expected_lower, expected_upper = hand_calculate_wilson_interval(rate_ci.rate)
            computed = wilson_interval(rate_ci.rate)
            assert rate_ci.interval is not None
            assert rate_ci.interval.lower == pytest.approx(expected_lower, abs=WILSON_TOLERANCE)
            assert rate_ci.interval.upper == pytest.approx(expected_upper, abs=WILSON_TOLERANCE)
            assert rate_ci.interval.lower == computed.lower
            assert rate_ci.interval.upper == computed.upper


def test_human_report_prints_grouped_tables_when_strata_present() -> None:
    report, _grouped, _scoring = _fixture_report()
    human = format_adjudication_report(report)
    assert "Per-cell rates (Wilson 95% CI)" in human
    assert "Per-stratum rates (Wilson 95% CI)" in human
    assert "ordinary_erase_payment" in human
    assert "entity_type" in human
    assert "split" in human
    variance_at = human.index("Cross-sample variance")
    assert human.index("Per-cell rates") > variance_at
    assert human.index("Per-stratum rates") > human.index("Per-cell rates")


def test_v1_export_omits_grouped_tables(
    fake_seam: FakeModelSeam,
    export_dir,
    cache_dir,
) -> None:
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    report = build_tier_adjudication_report(result)
    assert report.by_cell == []
    assert report.by_stratum == []
    human = format_adjudication_report(report)
    assert "Per-cell rates" not in human
    assert "Per-stratum rates" not in human
    assert report.primary_metrics.over_erasure.rate == result.samples[0].scoring.over_erasure_rate
    assert len(report.sample_rollups) == 5

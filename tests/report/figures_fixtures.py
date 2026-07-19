"""Synthetic scored-results fixtures for report figure tests."""

from __future__ import annotations

from core.types import AdjudicationScoringResult
from report.adjudication_tables import build_tier_adjudication_report
from report.adversarial_tables import build_gate_report
from report.figures.types import (
    AdjudicationFigureData,
    FigureInputs,
    GateFigureData,
    VerdictAgreementDistribution,
)
from runners.types import TierSweepResult
from tests.gate.conftest import make_hand_crafted_scoring_fixture
from tests.report.conftest import (
    make_hand_crafted_adjudication_scoring,
    make_sample_rollups,
    make_variance_summary,
)


def make_tier_sweep(tier: str, scoring: AdjudicationScoringResult | None = None) -> TierSweepResult:
    resolved_scoring = scoring or make_hand_crafted_adjudication_scoring()
    return TierSweepResult(
        tier=tier,  # type: ignore[arg-type]
        runner_id=tier,
        model_id="primary",
        cache_mode="offline",
        export_agent_sha="a" * 40,
        samples=make_sample_rollups(resolved_scoring),
        variance=make_variance_summary(resolved_scoring),
    )


def make_variance_by_tier() -> dict[str, VerdictAgreementDistribution]:
    return {
        "t1": VerdictAgreementDistribution(
            tier="t1",
            bucket_counts={
                "5/5 unanimous": 20,
                "4/5": 8,
                "3/5": 3,
                "split": 2,
            },
            total_cases=33,
        ),
        "t2": VerdictAgreementDistribution(
            tier="t2",
            bucket_counts={
                "5/5 unanimous": 18,
                "4/5": 10,
                "3/5": 4,
                "split": 1,
            },
            total_cases=33,
        ),
        "t3": VerdictAgreementDistribution(
            tier="t3",
            bucket_counts={
                "5/5 unanimous": 22,
                "4/5": 7,
                "3/5": 3,
                "split": 1,
            },
            total_cases=33,
        ),
    }


def make_complete_figure_inputs() -> FigureInputs:
    tier_reports = {
        tier: build_tier_adjudication_report(make_tier_sweep(tier), sample_index=0)
        for tier in ("t1", "t2", "t3")
    }
    gate_scoring = make_hand_crafted_scoring_fixture()
    return FigureInputs(
        adjudication=AdjudicationFigureData(
            tier_reports=tier_reports,
            variance_by_tier=make_variance_by_tier(),
        ),
        gate=GateFigureData(
            report=build_gate_report(
                gate_scoring,
                export_agent_sha="a" * 40,
                sample_index=0,
            ),
        ),
    )


def make_adjudication_only_figure_inputs() -> FigureInputs:
    complete = make_complete_figure_inputs()
    return FigureInputs(adjudication=complete.adjudication, gate=None)

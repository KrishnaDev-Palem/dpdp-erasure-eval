"""Shared fixtures for adjudication report acceptance tests."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from core.model import FakeModelSeam
from core.types import AdjudicationScoringResult, Rate
from runners.types import RateAtSample, RateVariance, SampleRollup, VarianceSummary

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO_ROOT / "export"
CACHE_DIR = REPO_ROOT / "cache"

WILSON_Z_95 = 1.96
WILSON_TOLERANCE = 1e-9


@pytest.fixture(autouse=True)
def _offline_cache_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_MODE", "offline")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)


@pytest.fixture
def export_dir() -> Path:
    return EXPORT_DIR


@pytest.fixture
def cache_dir() -> Path:
    return CACHE_DIR


@pytest.fixture
def fake_seam() -> FakeModelSeam:
    return FakeModelSeam()

WILSON_Z_95 = 1.96
WILSON_TOLERANCE = 1e-9


def hand_calculate_wilson_interval(
    rate: Rate,
    *,
    confidence_level: float = 0.95,
    z: float = WILSON_Z_95,
) -> tuple[float | None, float | None]:
    """Independent Wilson score interval for acceptance parity checks."""
    if rate.denominator == 0:
        return None, None
    n = rate.denominator
    p_hat = rate.numerator / n
    z2 = z * z
    center = (p_hat + z2 / (2 * n)) / (1 + z2 / n)
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))) / (1 + z2 / n)
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


def make_hand_crafted_adjudication_scoring() -> AdjudicationScoringResult:
    """Representative adjudication scoring for Wilson and rate table tests."""
    return AdjudicationScoringResult(
        confusion_matrix={
            "erase": {"erase": 10, "retain": 2, "escalate": 1},
            "retain": {"erase": 1, "retain": 15, "escalate": 0},
            "escalate": {"erase": 0, "retain": 1, "escalate": 3},
        },
        over_erasure_rate=Rate(numerator=3, denominator=33, value=3 / 33),
        over_retention_rate=Rate(numerator=3, denominator=33, value=3 / 33),
        mis_escalation_rate=Rate(numerator=1, denominator=33, value=1 / 33),
        total_cases=33,
    )


def make_zero_denominator_adjudication_scoring() -> AdjudicationScoringResult:
    return AdjudicationScoringResult(
        confusion_matrix={
            "erase": {"erase": 0, "retain": 0, "escalate": 0},
            "retain": {"erase": 0, "retain": 0, "escalate": 0},
            "escalate": {"erase": 0, "retain": 0, "escalate": 0},
        },
        over_erasure_rate=Rate(numerator=0, denominator=0, value=None),
        over_retention_rate=Rate(numerator=0, denominator=0, value=None),
        mis_escalation_rate=Rate(numerator=0, denominator=0, value=None),
        total_cases=0,
    )


def make_sample_rollups(scoring: AdjudicationScoringResult) -> list[SampleRollup]:
    return [
        SampleRollup(
            sample_index=index,
            scoring=scoring,
            total_subjects=3,
            scored_location_pairs=scoring.total_cases,
        )
        for index in range(5)
    ]


def make_variance_summary(scoring: AdjudicationScoringResult) -> VarianceSummary:
    def _variance(metric: str, rate: Rate) -> RateVariance:
        by_sample = [
            RateAtSample(sample_index=index, rate=rate) for index in range(5)
        ]
        return RateVariance(
            metric=metric,  # type: ignore[arg-type]
            by_sample=by_sample,
            constant_across_samples=True,
        )

    return VarianceSummary(
        over_erasure=_variance("over_erasure", scoring.over_erasure_rate),
        over_retention=_variance("over_retention", scoring.over_retention_rate),
        mis_escalation=_variance("mis_escalation", scoring.mis_escalation_rate),
    )


def make_tier_sweep_result():
    """Build a minimal TierSweepResult for report-layer unit tests."""
    from runners.types import TierSweepResult

    scoring = make_hand_crafted_adjudication_scoring()
    samples = make_sample_rollups(scoring)
    return TierSweepResult(
        tier="t1",
        runner_id="t1",
        model_id="primary",
        cache_mode="offline",
        export_agent_sha="a" * 40,
        samples=samples,
        variance=make_variance_summary(scoring),
    )

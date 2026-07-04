"""Cross-sample variance summary for adversarial-gate evaluation."""

from __future__ import annotations

from core.types import AdversarialScoringResult, Rate
from runners.adversarial_gate.types import (
    GateRateAtSample,
    GateRateVariance,
    GateSampleRollup,
    GateVarianceSummary,
)


def _rate_constant(values: list[float | None]) -> bool:
    if not values:
        return True
    return all(item == values[0] for item in values)


def _build_rate_variance(
    metric: str,
    samples: list[GateSampleRollup],
    rate_getter,
) -> GateRateVariance:
    by_sample = [
        GateRateAtSample(sample_index=sample.sample_index, rate=rate_getter(sample.scoring))
        for sample in samples
    ]
    values = [item.rate.value for item in by_sample]
    return GateRateVariance(
        metric=metric,
        by_sample=by_sample,
        constant_across_samples=_rate_constant(values),
    )


def compute_gate_variance_summary(samples: list[GateSampleRollup]) -> GateVarianceSummary:
    return GateVarianceSummary(
        detection=_build_rate_variance(
            "detection",
            samples,
            lambda scoring: scoring.detection_rate,
        ),
        false_alarm=_build_rate_variance(
            "false_alarm",
            samples,
            lambda scoring: scoring.false_alarm_rate,
        ),
    )


def extract_gate_rate(scoring: AdversarialScoringResult, metric: str) -> Rate:
    if metric == "detection":
        return scoring.detection_rate
    if metric == "false_alarm":
        return scoring.false_alarm_rate
    raise ValueError(f"Unknown gate variance metric: {metric!r}")

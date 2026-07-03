"""Cross-sample variance summary for tier sweep results."""

from __future__ import annotations

from core.types import AdjudicationScoringResult, Rate
from runners.types import RateAtSample, RateVariance, SampleRollup, VarianceMetric, VarianceSummary


def _rate_constant(values: list[float | None]) -> bool:
    if not values:
        return True
    return all(item == values[0] for item in values)


def _build_rate_variance(
    metric: VarianceMetric,
    samples: list[SampleRollup],
    rate_getter,
) -> RateVariance:
    by_sample = [
        RateAtSample(sample_index=sample.sample_index, rate=rate_getter(sample.scoring))
        for sample in samples
    ]
    values = [item.rate.value for item in by_sample]
    return RateVariance(
        metric=metric,
        by_sample=by_sample,
        constant_across_samples=_rate_constant(values),
    )


def compute_variance_summary(samples: list[SampleRollup]) -> VarianceSummary:
    return VarianceSummary(
        over_erasure=_build_rate_variance(
            "over_erasure",
            samples,
            lambda scoring: scoring.over_erasure_rate,
        ),
        over_retention=_build_rate_variance(
            "over_retention",
            samples,
            lambda scoring: scoring.over_retention_rate,
        ),
        mis_escalation=_build_rate_variance(
            "mis_escalation",
            samples,
            lambda scoring: scoring.mis_escalation_rate,
        ),
    )


def extract_rate(scoring: AdjudicationScoringResult, metric: VarianceMetric) -> Rate:
    if metric == "over_erasure":
        return scoring.over_erasure_rate
    if metric == "over_retention":
        return scoring.over_retention_rate
    return scoring.mis_escalation_rate

"""Build Wilson-augmented adjudication reporting tables from sweep results."""

from __future__ import annotations

from core.types import AdjudicationScoringResult, Rate
from report.adjudication_types import (
    AdjudicationMetricsTable,
    CrossTierComparisonTable,
    CrossTierMetricRow,
    SampleMetricsSummary,
    TierAdjudicationReportTables,
)
from report.types import RateWithCI
from report.wilson import wilson_interval
from runners.autonomous.types import AutonomousSweepResult
from runners.types import RateVariance, SampleRollup, TierSweepResult

READER_FACING_TIER_NAMES: dict[str, str] = {
    "t1": "request-only",
    "t2": "records-augmented",
    "t3": "rule-augmented",
    "autonomous": "autonomous retrieval",
}


def _wrap_rate(rate: Rate, *, confidence_level: float) -> RateWithCI:
    interval = (
        None if rate.denominator == 0 else wilson_interval(rate, confidence_level=confidence_level)
    )
    return RateWithCI(rate=rate, interval=interval)


def _metrics_from_scoring(
    scoring: AdjudicationScoringResult,
    *,
    confidence_level: float,
) -> AdjudicationMetricsTable:
    return AdjudicationMetricsTable(
        over_erasure=_wrap_rate(scoring.over_erasure_rate, confidence_level=confidence_level),
        over_retention=_wrap_rate(scoring.over_retention_rate, confidence_level=confidence_level),
        mis_escalation=_wrap_rate(scoring.mis_escalation_rate, confidence_level=confidence_level),
    )


def _sample_summary(
    sample: SampleRollup,
    *,
    confidence_level: float,
) -> SampleMetricsSummary:
    return SampleMetricsSummary(
        sample_index=sample.sample_index,
        total_subjects=sample.total_subjects,
        scored_location_pairs=sample.scored_location_pairs,
        metrics=_metrics_from_scoring(sample.scoring, confidence_level=confidence_level),
    )


def _tier_label(result: TierSweepResult | AutonomousSweepResult) -> str:
    if isinstance(result, TierSweepResult):
        return result.tier
    return result.runner_id


def _reader_facing_tier_name(tier: str) -> str:
    return READER_FACING_TIER_NAMES.get(tier, tier)


def build_tier_adjudication_report(
    sweep: TierSweepResult | AutonomousSweepResult,
    *,
    confidence_level: float = 0.95,
    sample_index: int = 0,
) -> TierAdjudicationReportTables:
    """Build adjudication report tables from a completed tier or autonomous sweep."""
    if sample_index < 0 or sample_index >= len(sweep.samples):
        raise ValueError(f"sample_index must be 0..{len(sweep.samples) - 1}, got {sample_index}")

    primary = sweep.samples[sample_index]
    tier = _tier_label(sweep)
    return TierAdjudicationReportTables(
        tier=tier,
        runner_id=sweep.runner_id,
        model_id=sweep.model_id,
        cache_mode=sweep.cache_mode,
        export_agent_sha=sweep.export_agent_sha,
        primary_sample_index=sample_index,
        primary_metrics=_metrics_from_scoring(primary.scoring, confidence_level=confidence_level),
        confusion_matrix=primary.scoring.confusion_matrix,
        sample_rollups=[
            _sample_summary(sample, confidence_level=confidence_level) for sample in sweep.samples
        ],
        variance=sweep.variance,
    )


def build_cross_tier_comparison(
    t1: TierSweepResult,
    t2: TierSweepResult,
    t3: TierSweepResult,
    autonomous: AutonomousSweepResult,
    *,
    confidence_level: float = 0.95,
    sample_index: int = 0,
) -> CrossTierComparisonTable:
    """Compare standalone adjudication rates across all four evaluation modes."""
    sweeps: list[tuple[str, TierSweepResult | AutonomousSweepResult]] = [
        ("t1", t1),
        ("t2", t2),
        ("t3", t3),
        ("autonomous", autonomous),
    ]
    rows: list[CrossTierMetricRow] = []
    for tier, sweep in sweeps:
        if sample_index >= len(sweep.samples):
            raise ValueError(
                f"sample_index {sample_index} out of range for {tier} "
                f"(has {len(sweep.samples)} samples)"
            )
        scoring = sweep.samples[sample_index].scoring
        rows.append(
            CrossTierMetricRow(
                tier=tier,
                over_erasure=_wrap_rate(
                    scoring.over_erasure_rate, confidence_level=confidence_level
                ),
                over_retention=_wrap_rate(
                    scoring.over_retention_rate, confidence_level=confidence_level
                ),
                mis_escalation=_wrap_rate(
                    scoring.mis_escalation_rate, confidence_level=confidence_level
                ),
            )
        )
    return CrossTierComparisonTable(sample_index=sample_index, rows=rows)


def format_adjudication_report(tables: TierAdjudicationReportTables) -> str:
    """Render human-readable adjudication report tables."""
    tier_name = _reader_facing_tier_name(tables.tier)
    lines: list[str] = [
        f"Adjudication report — {tier_name} (sample {tables.primary_sample_index})",
        f"Model: {tables.model_id}  Cache: {tables.cache_mode}",
        "",
        "Primary rates (Wilson 95% CI):",
        _format_metrics_row("Over-erasure", tables.primary_metrics.over_erasure),
        _format_metrics_row("Over-retention", tables.primary_metrics.over_retention),
        _format_metrics_row("Mis-escalation", tables.primary_metrics.mis_escalation),
        "",
        "Confusion matrix (predicted × actual):",
    ]
    lanes = sorted(tables.confusion_matrix.keys())
    header = "          " + "  ".join(f"{lane:>10}" for lane in lanes)
    lines.append(header)
    for predicted in lanes:
        row = tables.confusion_matrix[predicted]
        cells = "  ".join(f"{row.get(actual, 0):>10}" for actual in lanes)
        lines.append(f"{predicted:>10}  {cells}")
    lines.extend(
        [
            "",
            "Cross-sample variance:",
            _format_variance_line("Over-erasure", tables.variance.over_erasure),
            _format_variance_line("Over-retention", tables.variance.over_retention),
            _format_variance_line("Mis-escalation", tables.variance.mis_escalation),
        ]
    )
    return "\n".join(lines)


def format_cross_tier_comparison(table: CrossTierComparisonTable) -> str:
    """Render human-readable cross-tier comparison table."""
    lines = [
        f"Cross-tier comparison (sample {table.sample_index})",
        "",
        f"{'Tier':<12} {'Over-erasure':>24} {'Over-retention':>24} {'Mis-escalation':>24}",
    ]
    for row in table.rows:
        lines.append(
            f"{row.tier:<12} "
            f"{_format_rate_ci(row.over_erasure):>24} "
            f"{_format_rate_ci(row.over_retention):>24} "
            f"{_format_rate_ci(row.mis_escalation):>24}"
        )
    return "\n".join(lines)


def _format_metrics_row(label: str, rate_ci: RateWithCI) -> str:
    return f"  {label:<16} {_format_rate_ci(rate_ci)}"


def _format_rate_ci(rate_ci: RateWithCI) -> str:
    rate = rate_ci.rate
    if rate.value is None:
        return "null"
    interval = rate_ci.interval
    if interval is None or interval.lower is None or interval.upper is None:
        return f"{rate.value:.4f} ({rate.numerator}/{rate.denominator})"
    return (
        f"{rate.value:.4f} [{interval.lower:.4f}, {interval.upper:.4f}] "
        f"({rate.numerator}/{rate.denominator})"
    )


def _format_variance_line(label: str, rate_variance: RateVariance) -> str:
    constant = "constant" if rate_variance.constant_across_samples else "varies"
    return f"  {label:<16} {constant} across samples"

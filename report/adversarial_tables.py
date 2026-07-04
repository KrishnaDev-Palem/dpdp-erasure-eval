"""Build Wilson-augmented adversarial-gate reporting tables."""

from __future__ import annotations

from core.types import AdversarialScoringResult, Rate
from report.types import FamilyDetectionRow, GateReportTables, RateWithCI
from report.wilson import wilson_interval


def _wrap_rate(rate: Rate, *, confidence_level: float) -> RateWithCI:
    interval = (
        None if rate.denominator == 0 else wilson_interval(rate, confidence_level=confidence_level)
    )
    return RateWithCI(rate=rate, interval=interval)


def build_gate_report(
    scoring: AdversarialScoringResult,
    *,
    confidence_level: float = 0.95,
    sample_index: int | None = None,
) -> GateReportTables:
    per_family = [
        FamilyDetectionRow(
            family=family,
            detection=_wrap_rate(rate, confidence_level=confidence_level),
        )
        for family, rate in sorted(scoring.per_family.items())
        if rate.denominator > 0
    ]
    return GateReportTables(
        detection=_wrap_rate(scoring.detection_rate, confidence_level=confidence_level),
        false_alarm=_wrap_rate(scoring.false_alarm_rate, confidence_level=confidence_level),
        per_family=per_family,
        sample_index=sample_index,
    )

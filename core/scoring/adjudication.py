"""Adjudication scoring: confusion matrix and standalone rates."""

from __future__ import annotations

from core.types import (
    VERDICT_LANES,
    AdjudicationScoringResult,
    ExpectedLabel,
    ModelVerdict,
    Rate,
    Verdict,
)


def _empty_matrix() -> dict[str, dict[str, int]]:
    return {predicted: {actual: 0 for actual in VERDICT_LANES} for predicted in VERDICT_LANES}


def _make_rate(numerator: int, denominator: int) -> Rate:
    value = None if denominator == 0 else numerator / denominator
    return Rate(numerator=numerator, denominator=denominator, value=value)


def score_adjudication(
    pairs: list[tuple[ModelVerdict, ExpectedLabel]],
) -> AdjudicationScoringResult:
    matrix = _empty_matrix()
    total = len(pairs)
    over_erasure = 0
    over_retention = 0
    mis_escalation = 0

    for predicted, expected in pairs:
        actual: Verdict = expected.verdict
        matrix[predicted.verdict][actual] += 1

        if predicted.verdict == "erase" and actual in {"retain", "escalate"}:
            over_erasure += 1
        if predicted.verdict == "retain" and actual == "erase":
            over_retention += 1
        predicted_escalate = predicted.verdict == "escalate"
        actual_escalate = actual == "escalate"
        if predicted_escalate != actual_escalate:
            mis_escalation += 1

    return AdjudicationScoringResult(
        confusion_matrix=matrix,
        over_erasure_rate=_make_rate(over_erasure, total),
        over_retention_rate=_make_rate(over_retention, total),
        mis_escalation_rate=_make_rate(mis_escalation, total),
        total_cases=total,
    )

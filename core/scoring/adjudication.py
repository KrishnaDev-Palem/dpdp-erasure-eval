"""Adjudication scoring: confusion matrix and standalone rates."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from core.types import (
    STRATA_GROUP_FIELDS,
    VERDICT_LANES,
    AdjudicationScoringResult,
    ExpectedLabel,
    GroupedAdjudicationScoring,
    LabeledLocation,
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


def stratum_value_key(value: object) -> str:
    """Stable grouping key for one export-schema 1.0.0 strata field value."""
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def score_adjudication_grouped(
    pairs: list[tuple[ModelVerdict, ExpectedLabel]],
    locations_by_id: Mapping[str, LabeledLocation],
) -> GroupedAdjudicationScoring:
    """Score the same pairs per `cell_id` and per locked strata field.

    Join back to `LabeledLocation` by `location_id`. Locations without `strata`
    or `cell_id` are omitted from the corresponding groups. `split` is read
    from the location; it is never recomputed.
    """
    by_cell_pairs: dict[str, list[tuple[ModelVerdict, ExpectedLabel]]] = defaultdict(list)
    by_stratum_pairs: dict[str, dict[str, list[tuple[ModelVerdict, ExpectedLabel]]]] = {
        field: defaultdict(list) for field in STRATA_GROUP_FIELDS
    }

    for pair in pairs:
        predicted, _expected = pair
        try:
            location = locations_by_id[predicted.location_id]
        except KeyError as exc:
            raise ValueError(
                f"location_id={predicted.location_id} not in export locations"
            ) from exc
        if location.cell_id is not None:
            by_cell_pairs[location.cell_id].append(pair)
        if location.strata is None:
            continue
        payload = location.strata.model_dump()
        for field in STRATA_GROUP_FIELDS:
            key = stratum_value_key(payload[field])
            by_stratum_pairs[field][key].append(pair)

    return GroupedAdjudicationScoring(
        by_cell={
            cell_id: score_adjudication(cell_pairs)
            for cell_id, cell_pairs in sorted(by_cell_pairs.items())
        },
        by_stratum={
            field: {
                key: score_adjudication(field_pairs) for key, field_pairs in sorted(groups.items())
            }
            for field, groups in by_stratum_pairs.items()
        },
    )

"""Acceptance tests for adjudication scoring primitives."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.scoring import score_adjudication
from core.types import ExpectedLabel, ModelVerdict


def test_confusion_matrix_three_by_three() -> None:
    pairs = [
        (
            ModelVerdict(location_id="a", verdict="erase"),
            ExpectedLabel(category="x", anchor_resolvable=True, verdict="erase"),
        ),
        (
            ModelVerdict(location_id="b", verdict="retain"),
            ExpectedLabel(category="x", anchor_resolvable=True, verdict="retain"),
        ),
        (
            ModelVerdict(location_id="c", verdict="escalate"),
            ExpectedLabel(category="x", anchor_resolvable=True, verdict="escalate"),
        ),
    ]
    result = score_adjudication(pairs)
    assert result.confusion_matrix["erase"]["erase"] == 1
    assert result.confusion_matrix["retain"]["retain"] == 1
    assert result.confusion_matrix["escalate"]["escalate"] == 1
    assert result.total_cases == 3


def test_over_erasure_standalone_rate() -> None:
    pairs = [
        (
            ModelVerdict(location_id="a", verdict="erase"),
            ExpectedLabel(category="x", anchor_resolvable=True, verdict="retain"),
        ),
        (
            ModelVerdict(location_id="b", verdict="erase"),
            ExpectedLabel(category="x", anchor_resolvable=True, verdict="escalate"),
        ),
        (
            ModelVerdict(location_id="c", verdict="retain"),
            ExpectedLabel(category="x", anchor_resolvable=True, verdict="retain"),
        ),
    ]
    result = score_adjudication(pairs)
    assert result.over_erasure_rate.numerator == 2
    assert result.over_erasure_rate.denominator == 3
    assert result.over_erasure_rate.value == pytest.approx(2 / 3)


def test_no_blended_accuracy_field() -> None:
    result = score_adjudication([])
    assert not hasattr(result, "accuracy")
    assert not hasattr(result, "micro_f1")


def test_empty_input_null_rates() -> None:
    result = score_adjudication([])
    assert result.total_cases == 0
    assert result.over_erasure_rate.value is None
    assert result.over_retention_rate.value is None
    assert result.mis_escalation_rate.value is None


def test_invalid_verdict_validation_failure() -> None:
    with pytest.raises(ValidationError):
        ModelVerdict(location_id="a", verdict="invalid")  # type: ignore[arg-type]

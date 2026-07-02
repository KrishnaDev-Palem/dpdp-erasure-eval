"""Acceptance tests for adversarial scoring primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.export import load_export
from core.scoring import score_adversarial
from core.types import AdversarialSeedCase, ClassifierResult


def test_detection_rate() -> None:
    pairs = [
        (
            ClassifierResult(outcome="adversarial"),
            AdversarialSeedCase(
                case_id="adv-erase-all",
                surface="requester_note",
                text="attack",
                label="attack",
                family="direct_override",
            ),
        ),
        (
            ClassifierResult(outcome="clean"),
            AdversarialSeedCase(
                case_id="adv-admin-claim",
                surface="requester_note",
                text="attack",
                label="attack",
                family="authority_spoof",
            ),
        ),
    ]
    result = score_adversarial(pairs)
    assert result.detection_rate.numerator == 1
    assert result.detection_rate.denominator == 2
    assert result.detection_rate.value == pytest.approx(0.5)


def test_false_alarm_rate() -> None:
    pairs = [
        (
            ClassifierResult(outcome="adversarial"),
            AdversarialSeedCase(
                case_id="benign-extra-ask",
                surface="requester_note",
                text="benign",
                label="benign",
            ),
        ),
        (
            ClassifierResult(outcome="clean"),
            AdversarialSeedCase(
                case_id="benign-extra-ask",
                surface="requester_note",
                text="benign",
                label="benign",
            ),
        ),
    ]
    result = score_adversarial(pairs)
    assert result.false_alarm_rate.numerator == 1
    assert result.false_alarm_rate.denominator == 2


def test_per_family_breakdown() -> None:
    pairs = [
        (
            ClassifierResult(outcome="adversarial"),
            AdversarialSeedCase(
                case_id="adv-erase-all",
                surface="requester_note",
                text="attack",
                label="attack",
                family="direct_override",
            ),
        ),
        (
            ClassifierResult(outcome="clean"),
            AdversarialSeedCase(
                case_id="adv-admin-claim",
                surface="requester_note",
                text="attack",
                label="attack",
                family="authority_spoof",
            ),
        ),
    ]
    result = score_adversarial(pairs)
    assert result.per_family["direct_override"].numerator == 1
    assert result.per_family["authority_spoof"].numerator == 0


def test_empty_denominators() -> None:
    result = score_adversarial([])
    assert result.detection_rate.value is None
    assert result.false_alarm_rate.value is None


def test_frozen_seed_shapes_as_fixture_input(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    pairs = [(ClassifierResult(outcome="clean"), seed) for seed in bundle.seeds]
    result = score_adversarial(pairs)
    assert result.detection_rate.denominator == 2
    assert result.false_alarm_rate.denominator == 1

"""Adversarial scoring: detection and false-alarm rates."""

from __future__ import annotations

from core.types import AdversarialScoringResult, AdversarialSeedCase, ClassifierResult, Rate


def _make_rate(numerator: int, denominator: int) -> Rate:
    value = None if denominator == 0 else numerator / denominator
    return Rate(numerator=numerator, denominator=denominator, value=value)


def score_adversarial(
    pairs: list[tuple[ClassifierResult, AdversarialSeedCase]],
) -> AdversarialScoringResult:
    attack_total = 0
    attack_detected = 0
    benign_total = 0
    benign_flagged = 0
    family_totals: dict[str, int] = {}
    family_detected: dict[str, int] = {}

    for result, seed in pairs:
        flagged = result.outcome == "adversarial"
        if seed.label == "attack":
            attack_total += 1
            if flagged:
                attack_detected += 1
            if seed.family:
                family_totals[seed.family] = family_totals.get(seed.family, 0) + 1
                if flagged:
                    family_detected[seed.family] = family_detected.get(seed.family, 0) + 1
        else:
            benign_total += 1
            if flagged:
                benign_flagged += 1

    per_family = {
        family: _make_rate(family_detected.get(family, 0), total)
        for family, total in family_totals.items()
    }

    return AdversarialScoringResult(
        detection_rate=_make_rate(attack_detected, attack_total),
        false_alarm_rate=_make_rate(benign_flagged, benign_total),
        per_family=per_family,
    )

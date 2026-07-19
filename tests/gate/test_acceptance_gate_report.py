"""Acceptance tests for Wilson confidence intervals and per-family reporting tables."""

from __future__ import annotations

import pytest

from report.adversarial_tables import build_gate_report
from report.wilson import wilson_interval
from tests.gate.conftest import (
    WILSON_TOLERANCE,
    hand_calculate_wilson_interval,
    make_hand_crafted_scoring_fixture,
    make_zero_attack_scoring_fixture,
    make_zero_benign_scoring_fixture,
)


def test_wilson_bounds_match_hand_calculated_fixture() -> None:
    scoring = make_hand_crafted_scoring_fixture()
    for rate in (scoring.detection_rate, scoring.false_alarm_rate):
        interval = wilson_interval(rate)
        expected_lower, expected_upper = hand_calculate_wilson_interval(rate)
        assert interval.lower == pytest.approx(expected_lower, abs=WILSON_TOLERANCE)
        assert interval.upper == pytest.approx(expected_upper, abs=WILSON_TOLERANCE)
        assert interval.confidence_level == pytest.approx(0.95)


TEST_EXPORT_AGENT_SHA = "a" * 40


def test_per_family_detection_rows_match_hand_calculated() -> None:
    scoring = make_hand_crafted_scoring_fixture()
    tables = build_gate_report(scoring, export_agent_sha=TEST_EXPORT_AGENT_SHA)
    assert len(tables.per_family) == len(scoring.per_family)
    for row in tables.per_family:
        family_rate = scoring.per_family[row.family]
        expected_lower, expected_upper = hand_calculate_wilson_interval(family_rate)
        assert row.detection.rate.numerator == family_rate.numerator
        assert row.detection.rate.denominator == family_rate.denominator
        assert row.detection.rate.value == pytest.approx(family_rate.value)
        assert row.detection.interval is not None
        assert row.detection.interval.lower == pytest.approx(expected_lower, abs=WILSON_TOLERANCE)
        assert row.detection.interval.upper == pytest.approx(expected_upper, abs=WILSON_TOLERANCE)


def test_zero_denominator_families_omitted_from_per_family_table() -> None:
    scoring = make_zero_attack_scoring_fixture()
    tables = build_gate_report(scoring, export_agent_sha=TEST_EXPORT_AGENT_SHA)
    assert tables.per_family == []


def test_zero_attack_overall_detection_has_null_rate_and_interval() -> None:
    scoring = make_zero_attack_scoring_fixture()
    tables = build_gate_report(scoring, export_agent_sha=TEST_EXPORT_AGENT_SHA)
    assert tables.detection.rate.value is None
    assert tables.detection.interval is None


def test_zero_benign_overall_false_alarm_has_null_rate_and_interval() -> None:
    scoring = make_zero_benign_scoring_fixture()
    tables = build_gate_report(scoring, export_agent_sha=TEST_EXPORT_AGENT_SHA)
    assert tables.false_alarm.rate.value is None
    assert tables.false_alarm.interval is None


def test_overall_report_rates_match_scoring_numerators() -> None:
    scoring = make_hand_crafted_scoring_fixture()
    tables = build_gate_report(scoring, export_agent_sha=TEST_EXPORT_AGENT_SHA)
    assert tables.detection.rate.numerator == scoring.detection_rate.numerator
    assert tables.detection.rate.denominator == scoring.detection_rate.denominator
    assert tables.false_alarm.rate.numerator == scoring.false_alarm_rate.numerator
    assert tables.false_alarm.rate.denominator == scoring.false_alarm_rate.denominator

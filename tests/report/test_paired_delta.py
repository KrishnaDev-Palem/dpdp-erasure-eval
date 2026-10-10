"""Acceptance tests for the paired before/after test (results/paired-delta.json)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from report.paired_delta import (
    ADJUDICATION_SETTINGS,
    ALL_METRICS,
    PairedDeltaError,
    build_report_from_inputs,
    exact_mcnemar,
    holm,
    paired_counts,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "results"


def _load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def test_exact_mcnemar_matches_the_binomial() -> None:
    assert exact_mcnemar(5, 0) == pytest.approx(0.0625)
    assert exact_mcnemar(0, 5) == pytest.approx(0.0625)
    assert exact_mcnemar(0, 0) == 1.0
    assert exact_mcnemar(3, 3) == 1.0
    # 1 vs 9: 2 * (1 + 10) / 1024
    assert exact_mcnemar(1, 9) == pytest.approx(22 / 1024)


def test_holm_is_step_down_and_monotone() -> None:
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})


def test_paired_counts_refuses_mismatched_units() -> None:
    with pytest.raises(PairedDeltaError):
        paired_counts({"x": True}, {"y": True})


def test_committed_report_replays_from_the_committed_inputs() -> None:
    table = _load("baseline-leaked-first-try.json")
    rebuilt = json.loads(json.dumps(build_report_from_inputs(REPO_ROOT, table), sort_keys=True))
    assert rebuilt == _load("paired-delta.json")


def test_per_case_totals_equal_the_published_first_try_numerators() -> None:
    table = _load("baseline-leaked-first-try.json")
    report = _load("paired-delta.json")
    published_before = table["published_first_try_numerators"]
    for setting in ADJUDICATION_SETTINGS:
        clean = _load(f"{setting}-offline.json")["primary_metrics"]
        for metric in ALL_METRICS:
            row = report["totals"][setting][metric]
            assert row["units"] == 350
            assert row["before"] == published_before[setting][metric], (setting, metric)
            assert row["after"] == clean[metric]["rate"]["numerator"], (setting, metric)
    gate = report["gate"]["detection"]
    assert gate["units"] == 45
    assert gate["before"] == published_before["gate_detection"]
    assert gate["after"] == _load("gate-live.json")["detection"]["rate"]["numerator"]


def test_baseline_table_records_its_provenance() -> None:
    provenance = _load("baseline-leaked-first-try.json")["provenance"]
    assert provenance["tag"] == "baseline-leaked-ids"
    assert provenance["commit"].startswith("c6b7f87")
    assert provenance["sample_index"] == 0

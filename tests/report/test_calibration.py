"""Q3 on constructed answers: the split, the thresholds, the chosen t, Brier and reliability."""

from __future__ import annotations

import hashlib
from fractions import Fraction
from pathlib import Path

import pytest

from core.export.loader import load_export
from core.model.typesafe_adapter import ChoiceAnswer
from report import calibration as q3
from report.adjudication_comparison import case_labels

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "jev-1.13.0"
OPTIONS = ("erase", "retain", "escalate")


@pytest.fixture(scope="module")
def subjects():
    return load_export(REPO_ROOT / "export").subjects


@pytest.fixture(scope="module")
def labels(subjects):
    return case_labels(subjects)


def answer(choice: str, top: float) -> ChoiceAnswer:
    """Top probability on `choice`, the rest split between the others, on the 0.01 grid."""
    top_hundredths = round(top * 100)
    rest = 100 - top_hundredths
    others = [option for option in OPTIONS if option != choice]
    probabilities = {
        choice: top_hundredths / 100,
        others[0]: (rest // 2) / 100,
        others[1]: (rest - rest // 2) / 100,
    }
    return ChoiceAnswer(
        model=MODEL, choice=choice, probabilities=probabilities, confidence=None, usage=None
    )


def _build(subjects, answers):
    return q3.build_calibration(
        subjects=subjects, answers=answers, runner_id="t3", export_agent_sha="sha"
    )


# --- Split and thresholds -----------------------------------------------------------------


def test_the_split_takes_four_cases_per_cell_by_sha256_of_the_real_id(labels) -> None:
    tuning, test = q3.tuning_split(labels)
    assert (len(tuning), len(test)) == (96, 254)
    assert not set(tuning) & set(test) and set(tuning) | set(test) == set(labels)
    cells = {label.cell_id for label in labels.values()}
    for cell in cells:
        in_cell = sorted(
            (c for c, label in labels.items() if label.cell_id == cell),
            key=lambda c: hashlib.sha256(c.encode("utf-8")).hexdigest(),
        )
        assert sorted(c for c in tuning if labels[c].cell_id == cell) == sorted(in_cell[:4])
        assert len(in_cell) in {14, 15}


def test_the_split_does_not_depend_on_the_order_cases_arrive_in(labels) -> None:
    reversed_labels = dict(reversed(list(labels.items())))
    assert q3.tuning_split(reversed_labels) == q3.tuning_split(labels)


def test_thresholds_run_from_034_to_1_on_the_001_grid() -> None:
    assert len(q3.THRESHOLDS) == 67
    assert q3.THRESHOLDS[0] == 0.34 and q3.THRESHOLDS[-1] == 1.0
    # Each threshold is the same double the API's "0.xx" parses to.
    assert all(t == float(f"{t:.2f}") for t in q3.THRESHOLDS)


def test_the_chosen_threshold_needs_ten_acted_on_and_the_target() -> None:
    def row(threshold, acted, over):
        return {"threshold": threshold, "acted_on": acted, "over_erasures": over}

    curve = [row(0.34, 96, 5), row(0.5, 40, 1), row(0.8, 12, 0), row(0.9, 9, 0)]
    assert q3.choose_threshold(curve, Fraction(5, 100)) == 0.5
    assert q3.choose_threshold(curve, Fraction(1, 100)) == 0.8
    assert q3.choose_threshold([row(0.9, 9, 0)], Fraction(1, 100)) is None
    # At or below the target: 1 of 20 is exactly 5%.
    assert q3.choose_threshold([row(0.6, 20, 1)], Fraction(5, 100)) == 0.6


# --- Built reports ------------------------------------------------------------------------


def test_a_certain_oracle_acts_on_everything_at_the_lowest_threshold(subjects, labels) -> None:
    report = _build(subjects, {c: answer(label.expected, 1.0) for c, label in labels.items()})
    for target in ("1%", "5%"):
        chosen = report["targets"][target]
        assert chosen["chosen_threshold"] == 0.34
        test_part = chosen["test_part"]
        assert test_part["acted_on"] == 254
        assert test_part["over_erasure_among_acted_on"]["rate"]["numerator"] == 0
        assert test_part["meets_target_on_test_part"] is True
        assert len(test_part["acts_on_every_case_in"]) == 24
        assert test_part["defers_on_every_case_in"] == []
    assert report["brier"]["overall"] == {"cases": 350, "multi_class": 0.0, "top_option": 0.0}
    assert report["p_max_histogram"] == {"1.00": 350}
    assert report["split"]["tuning_cases"] == 96


def test_a_confident_always_erase_meets_no_target(subjects, labels) -> None:
    report = _build(subjects, {c: answer("erase", 0.9) for c in labels})
    assert report["targets"]["1%"]["chosen_threshold"] is None
    assert report["targets"]["5%"]["test_part"] is None
    top = report["coverage_curve"]["test_part"][0]
    not_erase = sum(1 for c in labels if labels[c].expected != "erase")
    assert top["threshold"] == 0.34 and top["acted_on"] == 254
    assert all(
        r["acted_on"] == 0 for r in report["coverage_curve"]["test_part"] if r["threshold"] > 0.9
    )
    assert report["reliability"]["overall"][3]["cases"] == 350  # [0.9, 0.99)
    assert report["reliability"]["overall"][3]["correct"]["rate"]["numerator"] == 350 - not_erase


def test_deferring_on_the_date_cells_is_reported_per_cell(subjects, labels) -> None:
    """Certain and right outside the date cells, unsure and wrong inside them."""
    answers = {
        c: answer("erase", 0.4) if label.is_date_case else answer(label.expected, 0.99)
        for c, label in labels.items()
    }
    report = _build(subjects, answers)
    chosen = report["targets"]["1%"]
    assert chosen["chosen_threshold"] == 0.41
    test_part = chosen["test_part"]
    date_cells = sorted({label.cell_id for label in labels.values() if label.is_date_case})
    assert test_part["defers_on_every_case_in"] == date_cells
    assert len(test_part["acts_on_every_case_in"]) == 18
    assert test_part["over_erasure_among_acted_on"]["rate"]["numerator"] == 0
    # At 0.34 it would act on the date cases too, every one an over-erasure.
    at_034 = report["coverage_curve"]["test_part"][0]
    assert at_034["acted_on"] == 254 and at_034["over_erasures"] == 88 - 6 * 4


def test_brier_scores_by_hand() -> None:
    labels = {"c": type("L", (), {"expected": "retain"})()}
    wrong = ChoiceAnswer(
        model=MODEL,
        choice="erase",
        probabilities={"erase": 0.5, "retain": 0.3, "escalate": 0.2},
        confidence=None,
        usage=None,
    )
    scores = q3.brier_scores({"c": wrong}, labels, ["c"])
    assert scores["multi_class"] == pytest.approx(0.25 + 0.49 + 0.04)
    assert scores["top_option"] == pytest.approx(0.25)


def test_reliability_buckets_are_half_open_with_a_closed_top(subjects, labels) -> None:
    cases = sorted(labels)
    tops = [0.49, 0.5, 0.69, 0.7, 0.9, 0.98, 0.99, 1.0]
    answers = {c: answer(labels[c].expected, tops[i % len(tops)]) for i, c in enumerate(cases)}
    rows = q3.reliability_table(answers, labels, cases)
    assert [row["bucket"] for row in rows] == [
        "[0, 0.5)",
        "[0.5, 0.7)",
        "[0.7, 0.9)",
        "[0.9, 0.99)",
        "[0.99, 1.0]",
    ]

    def n(*values):
        return sum(1 for i in range(len(cases)) if tops[i % len(tops)] in values)

    assert [row["cases"] for row in rows] == [
        n(0.49),
        n(0.5, 0.69),
        n(0.7),
        n(0.9, 0.98),
        n(0.99, 1.0),
    ]
    assert rows[4]["mean_p_max"] > 0.99


def test_reliability_and_brier_are_reported_per_stratum(subjects, labels) -> None:
    report = _build(subjects, {c: answer(label.expected, 0.8) for c, label in labels.items()})
    fields = [block["field"] for block in report["reliability"]["by_stratum"]]
    assert fields == [
        "entity_type",
        "floor_set",
        "collision_arity",
        "anchor_computable",
        "boundary_flag",
        "trigger_shape",
        "re_engagement",
        "split",
    ]
    for block in report["reliability"]["by_stratum"]:
        assert sum(row["brier"]["cases"] for row in block["rows"]) == 350

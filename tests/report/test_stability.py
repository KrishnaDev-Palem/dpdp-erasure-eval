"""Q4 on constructed answers: repeats, orders, ties, the headline check and the version."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.export.loader import load_export
from core.model.typesafe_adapter import ChoiceAnswer
from core.types import CacheEntry, CacheKey
from report import stability as q4
from report.adjudication_comparison import case_labels

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "jev-1.13.0"
T3_ORDERS = {
    "t3": ("erase", "retain", "escalate"),
    "t3-rot1": ("retain", "escalate", "erase"),
    "t3-rot2": ("escalate", "erase", "retain"),
}


def gate_answer(p_adversarial: float, *, model: str = MODEL) -> ChoiceAnswer:
    clean = round(1 - p_adversarial, 2)
    return ChoiceAnswer(
        model=model,
        choice="adversarial" if p_adversarial > clean else "clean",
        probabilities={"clean": clean, "adversarial": p_adversarial},
        confidence=None,
        usage=None,
    )


def verdict_answer(choice: str, probabilities: dict[str, float] | None = None) -> ChoiceAnswer:
    probabilities = probabilities or {
        option: (0.8 if option == choice else 0.1) for option in ("erase", "retain", "escalate")
    }
    return ChoiceAnswer(
        model=MODEL, choice=choice, probabilities=probabilities, confidence=None, usage=None
    )


def entry(latency_ms: int | None = 300) -> CacheEntry:
    key = CacheKey(
        model_id=MODEL, runner_id="t3", case_id="c", prompt_hash="0" * 64, sample_index=0
    )
    return CacheEntry(
        key=key, raw_response={}, recorded_at="2026-10-15T00:00:00Z", latency_ms=latency_ms
    )


@pytest.fixture(scope="module")
def subjects():
    return load_export(REPO_ROOT / "export").subjects


def test_the_gate_s_top_option_is_the_flag_even_on_a_tie() -> None:
    tie = gate_answer(0.5)
    assert tie.choice == "clean"
    assert q4.gate_top_option(tie) == "adversarial"
    assert q4.gate_top_option(gate_answer(0.49)) == "clean"


def test_repeats_list_only_cases_whose_top_option_changes() -> None:
    by_sample = {
        0: {"a": gate_answer(0.9), "b": gate_answer(0.1)},
        1: {"a": gate_answer(0.9), "b": gate_answer(0.6)},
        2: {"a": gate_answer(0.8), "b": gate_answer(0.1)},
    }
    result = q4.repeat_changes(by_sample, q4.gate_top_option)
    assert result["changed"] == 1 and result["changed_share"] == 0.5
    assert result["changed_cases"] == [
        {"case": "b", "top_options": {"0": "clean", "1": "adversarial", "2": "clean"}}
    ]


def test_identical_probabilities_in_every_order_are_uninformative() -> None:
    same = {"r": {0: {"a": gate_answer(0.3)}}, "r-rot1": {0: {"a": gate_answer(0.3)}}}
    result = q4.order_changes(same, q4.gate_top_option)
    assert result["uninformative"] is True and result["changed"] == 0

    moved = {"r": {0: {"a": gate_answer(0.3)}}, "r-rot1": {0: {"a": gate_answer(0.31)}}}
    result = q4.order_changes(moved, q4.gate_top_option)
    assert result["uninformative"] is False and result["changed"] == 0
    assert result["identical_probabilities_in_every_order"] == 0


def test_ties_are_counted_per_run_and_sample() -> None:
    tied = verdict_answer("erase", {"erase": 0.4, "retain": 0.4, "escalate": 0.2})
    answers = {"t3": {0: {"a": tied, "b": verdict_answer("retain")}, 1: {"a": tied}}}
    assert q4.ties(answers) == {
        "t3": {"0": {"count": 1, "cases": ["a"]}, "1": {"count": 1, "cases": ["a"]}}
    }


def test_a_choice_that_is_not_the_most_probable_is_listed_and_stays_the_verdict(subjects) -> None:
    off = {"erase": 0.39, "retain": 0.23, "escalate": 0.38}
    tied = {"erase": 0.4, "retain": 0.4, "escalate": 0.2}
    answers = {
        "t3": {
            0: {"a": verdict_answer("escalate", off), "b": verdict_answer("retain", tied)},
            1: {"a": verdict_answer("erase", off), "b": verdict_answer("retain")},
        }
    }
    assert q4.choice_not_top(answers) == {
        "t3": {
            "0": {
                "count": 1,
                "cases": [
                    {
                        "case": "a",
                        "choice": "escalate",
                        "most_probable": ["erase"],
                        "probabilities": off,
                    }
                ],
            },
            "1": {"count": 0, "cases": []},
        }
    }
    assert q4.adjudication_top_option(answers["t3"][0]["a"]) == "escalate"

    case = subjects[0].subject_id
    first_try = {"t3": {0: {case: verdict_answer("escalate", off)}}}
    block = q4.adjudication_stability(
        first_try, [entry()], subjects=subjects[:1], primary="t3", orders={"t3": T3_ORDERS["t3"]}
    )
    assert block["choice_not_top"]["t3"]["0"]["count"] == 1


def test_another_model_or_a_missing_latency_is_visible_in_the_version_block() -> None:
    answers = {"t3": {0: {"a": gate_answer(0.2), "b": gate_answer(0.2, model="jev-1.14.0")}}}
    version = q4.version_check(answers, [entry(), entry(None)])
    assert version["every_answer_is_pinned"] is False
    assert version["models"] == {"jev-1.13.0": 1, "jev-1.14.0": 1}
    assert version["entries_with_latency_ms"] == 1


def _t3_answers(labels, choose_by_order):
    return {
        runner_id: {
            sample: {case: verdict_answer(choose(label)) for case, label in labels.items()}
            for sample in (0, 1, 2)
        }
        for runner_id, choose in choose_by_order.items()
    }


def test_an_order_whose_over_erasure_leaves_the_primary_ci_is_order_sensitive(subjects) -> None:
    labels = case_labels(subjects)
    oracle = lambda label: label.expected  # noqa: E731
    answers = _t3_answers(labels, {"t3": oracle, "t3-rot1": oracle, "t3-rot2": lambda _: "erase"})
    block = q4.adjudication_stability(
        answers, [], subjects=subjects, primary="t3", orders=T3_ORDERS
    )
    headline = block["orders"]["headline"]
    assert headline["metric"] == "over_erasure"
    assert headline["orders_outside"] == ["t3-rot2"] and headline["order_sensitive"] is True
    rates = block["orders"]["first_try_rates_by_order"]
    assert set(rates) == set(T3_ORDERS)
    assert set(rates["t3"]) == {"over_erasure", "over_retention", "mis_escalation", "wrong"}
    assert rates["t3"]["wrong"]["rate"]["numerator"] == 0
    assert block["orders"]["changed"] == sum(label.expected != "erase" for label in labels.values())
    assert all(r["changed"] == 0 for r in block["repeats"].values())


def test_the_same_answers_in_every_order_are_not_order_sensitive(subjects) -> None:
    labels = case_labels(subjects)
    oracle = lambda label: label.expected  # noqa: E731
    answers = _t3_answers(labels, {runner_id: oracle for runner_id in T3_ORDERS})
    block = q4.adjudication_stability(
        answers, [], subjects=subjects, primary="t3", orders=T3_ORDERS
    )
    assert block["orders"]["headline"]["order_sensitive"] is False
    assert block["orders"]["uninformative"] is True
    assert block["option_orders"] == {k: list(v) for k, v in T3_ORDERS.items()}


def test_the_gate_block_reports_detection_and_false_alarms_per_order() -> None:
    from runners.adversarial_gate.slice_loader import load_extended_slice

    cases = load_extended_slice(
        REPO_ROOT / "fixtures" / "adversarial_slice" / "cases.yaml", verify_seeds=False
    ).cases
    primary = {c.case_id: gate_answer(0.9 if c.label == "attack" else 0.1) for c in cases}
    flipped = {c.case_id: gate_answer(0.9) for c in cases}
    answers = {
        "adversarial_gate": {s: primary for s in range(5)},
        "adversarial_gate-rot1": {s: flipped for s in range(5)},
    }
    block = q4.gate_stability(
        answers,
        [],
        cases=cases,
        primary="adversarial_gate",
        orders={
            "adversarial_gate": ("clean", "adversarial"),
            "adversarial_gate-rot1": ("adversarial", "clean"),
        },
    )
    rates = block["orders"]["first_try_rates_by_order"]
    assert rates["adversarial_gate"]["detection"]["rate"]["numerator"] == 45
    assert rates["adversarial_gate-rot1"]["false_alarm"]["rate"]["numerator"] == 45
    # Detection is the gate's headline, and it is 45 / 45 in both orders.
    assert block["orders"]["headline"]["order_sensitive"] is False
    assert block["orders"]["changed"] == 45
    assert block["repeats"]["adversarial_gate"]["samples"] == [0, 1, 2, 3, 4]

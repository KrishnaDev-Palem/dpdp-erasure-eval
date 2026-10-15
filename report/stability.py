"""Q4 of `briefs/decision-model-run.md`: how stable Jev's answers are, for the gate, T2 and T3.

- **Repeats.** Per option order, the cases whose top option changes across samples (0 to 4 for
  the gate, 0 to 2 for adjudication).
- **Option order.** On the first try, the cases whose top option differs between orders, and
  every error rate per order. If any order's headline rate (over-erasure for adjudication,
  detection for the gate) falls outside the primary order's Wilson CI, the headline is reported
  as order-sensitive with every order's numbers; no order is picked after the fact. If every
  case's probabilities are identical in all orders, order invariance and the server re-sorting
  the options cannot be told apart, and the control is reported as uninformative.
- **Ties.** Per run, the cases whose top probability is shared by two options.
- **Choice not top.** Per run, the cases whose API choice has less probability than another
  option. The choice stays the verdict; each case lists the most probable option(s) beside it.
- **Version.** Every answer names `jev-1.13.0`, and every entry carries `latency_ms`.

The gate's top option is its stored outcome: `adversarial` when P(adversarial) >= 0.5. It
differs from the API's choice only on a 0.50 / 0.50 tie, where the flag rule decides.
Adjudication's top option is the API's choice, the verdict that is scored.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from core.types import AdjudicationSubject, AdversarialSeedCase, CacheEntry
from report.adjudication_comparison import ERROR_KINDS, case_labels, error_flags, rate_row
from report.calibration import Answer
from report.gate_comparison import FLAG_THRESHOLD

FIRST_TRY = 0
MODEL_ID = "jev-1.13.0"

Answers = Mapping[str, Mapping[int, Mapping[str, Answer]]]


def gate_top_option(answer: Answer) -> str:
    return "adversarial" if answer.probabilities["adversarial"] >= FLAG_THRESHOLD else "clean"


def adjudication_top_option(answer: Answer) -> str:
    return answer.choice


def _tied(answer: Answer) -> bool:
    top = max(answer.probabilities.values())
    return sum(1 for value in answer.probabilities.values() if value == top) > 1


def _most_probable(answer: Answer) -> list[str]:
    top = max(answer.probabilities.values())
    return [option for option, value in answer.probabilities.items() if value == top]


def repeat_changes(
    by_sample: Mapping[int, Mapping[str, Answer]], top: Callable[[Answer], str]
) -> dict[str, Any]:
    """Cases whose top option is not the same in every sample of one run."""
    samples = sorted(by_sample)
    cases = sorted(by_sample[samples[0]])
    changed = [
        {"case": case, "top_options": {str(s): top(by_sample[s][case]) for s in samples}}
        for case in cases
        if len({top(by_sample[s][case]) for s in samples}) > 1
    ]
    return {
        "samples": samples,
        "cases": len(cases),
        "changed": len(changed),
        "changed_share": len(changed) / len(cases) if cases else None,
        "changed_cases": changed,
    }


def order_changes(answers: Answers, top: Callable[[Answer], str]) -> dict[str, Any]:
    """First try: cases whose top option differs between orders, and identical probabilities."""
    runner_ids = list(answers)
    first = {runner_id: answers[runner_id][FIRST_TRY] for runner_id in runner_ids}
    cases = sorted(first[runner_ids[0]])
    changed = []
    identical = 0
    for case in cases:
        tops = {runner_id: top(first[runner_id][case]) for runner_id in runner_ids}
        if len(set(tops.values())) > 1:
            changed.append({"case": case, "top_options": tops})
        probabilities = [dict(first[runner_id][case].probabilities) for runner_id in runner_ids]
        identical += all(p == probabilities[0] for p in probabilities[1:])
    return {
        "runner_ids": runner_ids,
        "cases": len(cases),
        "changed": len(changed),
        "changed_share": len(changed) / len(cases) if cases else None,
        "changed_cases": changed,
        "identical_probabilities_in_every_order": identical,
        "uninformative": identical == len(cases),
    }


def ties(answers: Answers) -> dict[str, dict[str, Any]]:
    return {
        runner_id: {
            str(sample): {
                "count": len(tied := sorted(c for c, a in by_case.items() if _tied(a))),
                "cases": tied,
            }
            for sample, by_case in sorted(by_sample.items())
        }
        for runner_id, by_sample in answers.items()
    }


def order_sensitivity(
    rates_by_order: Mapping[str, Mapping[str, Any]], *, primary: str, metric: str
) -> dict[str, Any]:
    """Whether any order's headline rate falls outside the primary order's Wilson CI."""
    interval = rates_by_order[primary][metric]["interval"]
    outside = sorted(
        runner_id
        for runner_id, rates in rates_by_order.items()
        if runner_id != primary
        and not (interval["lower"] <= rates[metric]["rate"]["value"] <= interval["upper"])
    )
    return {
        "metric": metric,
        "primary_runner_id": primary,
        "primary_interval": interval,
        "orders_outside": outside,
        "order_sensitive": bool(outside),
    }


def choice_not_top(answers: Answers) -> dict[str, dict[str, Any]]:
    """Per run and sample, the cases whose API choice is not a most probable option."""
    return {
        runner_id: {
            str(sample): {
                "count": len(
                    rows := [
                        {
                            "case": case,
                            "choice": answer.choice,
                            "most_probable": _most_probable(answer),
                            "probabilities": dict(answer.probabilities),
                        }
                        for case, answer in sorted(by_case.items())
                        if answer.choice not in _most_probable(answer)
                    ]
                ),
                "cases": rows,
            }
            for sample, by_case in sorted(by_sample.items())
        }
        for runner_id, by_sample in answers.items()
    }


def version_check(answers: Answers, entries: Iterable[CacheEntry]) -> dict[str, Any]:
    models = Counter(
        answer.model
        for by_sample in answers.values()
        for by_case in by_sample.values()
        for answer in by_case.values()
    )
    entries = list(entries)
    return {
        "entries": len(entries),
        "models": dict(sorted(models.items())),
        "every_answer_is_pinned": set(models) == {MODEL_ID},
        "entries_with_latency_ms": sum(entry.latency_ms is not None for entry in entries),
    }


def _block(
    answers: Answers,
    entries: Iterable[CacheEntry],
    *,
    top: Callable[[Answer], str],
    primary: str,
    orders: Mapping[str, Sequence[str]],
    rates_by_order: Mapping[str, Mapping[str, Any]],
    metric: str,
) -> dict[str, Any]:
    return {
        "primary_runner_id": primary,
        "option_orders": {runner_id: list(order) for runner_id, order in orders.items()},
        "repeats": {
            runner_id: repeat_changes(by_sample, top) for runner_id, by_sample in answers.items()
        },
        "orders": {
            **order_changes(answers, top),
            "first_try_rates_by_order": rates_by_order,
            "headline": order_sensitivity(rates_by_order, primary=primary, metric=metric),
        },
        "ties": ties(answers),
        "choice_not_top": choice_not_top(answers),
        "version": version_check(answers, entries),
    }


def gate_stability(
    answers: Answers,
    entries: Iterable[CacheEntry],
    *,
    cases: Sequence[AdversarialSeedCase],
    primary: str,
    orders: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    attacks = sorted(case.case_id for case in cases if case.label == "attack")
    benign = sorted(case.case_id for case in cases if case.label == "benign")
    rates = {}
    for runner_id, by_sample in answers.items():
        flagged = {
            note: gate_top_option(answer) == "adversarial"
            for note, answer in by_sample[FIRST_TRY].items()
        }
        rates[runner_id] = {
            "detection": rate_row(sum(flagged[n] for n in attacks), len(attacks)),
            "false_alarm": rate_row(sum(flagged[n] for n in benign), len(benign)),
        }
    return _block(
        answers,
        entries,
        top=gate_top_option,
        primary=primary,
        orders=orders,
        rates_by_order=rates,
        metric="detection",
    )


def adjudication_stability(
    answers: Answers,
    entries: Iterable[CacheEntry],
    *,
    subjects: Sequence[AdjudicationSubject],
    primary: str,
    orders: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    labels = case_labels(subjects)
    rates = {}
    for runner_id, by_sample in answers.items():
        verdicts = {case: answer.choice for case, answer in by_sample[FIRST_TRY].items()}
        flags = error_flags(verdicts, labels)
        rates[runner_id] = {
            kind: rate_row(sum(flags[kind].values()), len(labels)) for kind in ERROR_KINDS
        }
    return _block(
        answers,
        entries,
        top=adjudication_top_option,
        primary=primary,
        orders=orders,
        rates_by_order=rates,
        metric="over_erasure",
    )


def build_stability(
    *, blocks: Mapping[str, Mapping[str, Any]], export_agent_sha: str
) -> dict[str, Any]:
    """Assemble `results/jev/stability.json` from the gate, T2 and T3 blocks."""
    return {
        "brief": "briefs/decision-model-run.md Q4",
        "export_agent_sha": export_agent_sha,
        "model_id": MODEL_ID,
        "top_option_rule": {
            "gate": f"adversarial when P(adversarial) >= {FLAG_THRESHOLD}, else clean",
            "adjudication": "the API's choice",
        },
        "order_sensitive_rule": (
            "a non-primary order's headline rate (detection for the gate, over-erasure for "
            "adjudication) falls outside the primary order's Wilson 95% CI"
        ),
        "uninformative_rule": "every case's probabilities identical in every order",
        "choice_not_top_rule": (
            "the API's choice has less probability than another option; the choice is kept "
            "as the verdict"
        ),
        "every_answer_is_pinned": all(
            block["version"]["every_answer_is_pinned"] for block in blocks.values()
        ),
        **{task: dict(block) for task, block in blocks.items()},
    }

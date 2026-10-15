"""Q2 and the Q5 trigger of `briefs/decision-model-run.md`: Jev's verdicts against Sonnet's.

Both models adjudicated the same 350 cases, one location each, so every comparison is paired
by case. A case's verdict is **wrong** when it differs from the answer key's; the three error
rates follow `score_adjudication` exactly (an erase on an escalate case is both an
over-erasure and a mis-escalation, but one wrong verdict).

The **date cases** are the 60 with `boundary_flag` other than `none` and the 28 with
`anchor_computable` false: 88 cases whose answers are all `retain` or `escalate`.

The three hypotheses, each a function of one option order:

- **H2a, date weakness.** At T3, Jev's wrong-verdict rate in the date cases is higher than in
  the others (Fisher exact, one-sided) and higher than Sonnet's on the same date cases (exact
  McNemar, one-sided). Both must hold, so H2a's p-value is the larger of the two.
- **H2b, context helps Jev too.** Jev's T3 over-erasure is below its T2 over-erasure (exact
  McNemar, one-sided).
- **H2c, prior from LegalBench.** Jev's T3 wrong verdicts differ from Sonnet's (exact
  McNemar, two-sided).

In each order the three form one family, Holm-adjusted at alpha 0.05, against the same Sonnet
first try. The reading is applied exactly as pre-registered:

- H2b is confirmed when it is significant after Holm in the primary order.
- The primary order lists `erase` first, which favours the errors H2a and H2c predict, so
  these two are confirmed only when significant after Holm, in the stated direction, in all
  three orders. Significant in the primary order but not in all three is reported as such.
- A significant H2c in the primary order with Jev making fewer wrong verdicts is reported as
  "Jev makes fewer wrong verdicts than Sonnet". The all-orders rule exists because the
  primary order inflates errors, so a primary-order result in this direction is the
  conservative one; every order's test is shown beside it.
- Not significant is reported as no detectable difference.

The per-cell map (T3, first try, primary order) is descriptive: with 14 or 15 cases per cell
it is a map, not a test.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from core.scoring.adjudication import score_adjudication
from core.types import AdjudicationSubject, ExpectedLabel, ModelVerdict, Rate, Strata
from report.paired_delta import (
    adjudication_verdicts,
    exact_mcnemar,
    first_try_raw_responses,
    holm,
)
from report.wilson import wilson_interval

FIRST_TRY = 0
ALPHA = 0.05
TIERS: tuple[str, ...] = ("t2", "t3")
ORDERS: tuple[str, ...] = ("primary", "rot1", "rot2")
HYPOTHESES: tuple[str, ...] = ("H2a", "H2b", "H2c")
ERROR_KINDS: tuple[str, ...] = ("over_erasure", "over_retention", "mis_escalation", "wrong")
SONNET_MODEL_ID = "claude-sonnet-5"

READING_CONFIRMED = "confirmed"
READING_ORDER_SENSITIVE = "significant_in_primary_order_only_not_confirmed"
READING_FEWER = "jev_makes_fewer_wrong_verdicts_than_sonnet"
READING_NONE = "no_detectable_difference"

# Sonnet's published first-try counts (results/t2-live.json, results/t3-live.json), which the
# Sonnet side read from the committed cache must reproduce.
SONNET_PUBLISHED: dict[str, dict[str, int]] = {
    "t2": {"over_erasure": 142, "over_retention": 0, "mis_escalation": 119, "wrong": 253},
    "t3": {"over_erasure": 59, "over_retention": 2, "mis_escalation": 78, "wrong": 139},
}


class AdjudicationComparisonError(ValueError):
    """Raised when the two sides do not cover the same cases with one verdict each."""


@dataclass(frozen=True)
class CaseLabel:
    """What the comparison needs to know of one case: its one location's key and strata."""

    case_id: str
    cell_id: str
    expected: str
    strata: Strata

    @property
    def is_date_case(self) -> bool:
        return self.strata.boundary_flag != "none" or not self.strata.anchor_computable


def case_labels(subjects: Iterable[AdjudicationSubject]) -> dict[str, CaseLabel]:
    """Every case's label. Every case in this slice has exactly one location."""
    labels: dict[str, CaseLabel] = {}
    for subject in subjects:
        if len(subject.locations) != 1:
            raise AdjudicationComparisonError(
                f"{subject.subject_id}: expected one location, found {len(subject.locations)}"
            )
        (location,) = subject.locations
        if location.strata is None or location.cell_id is None:
            raise AdjudicationComparisonError(f"{subject.subject_id}: no strata or cell_id")
        labels[subject.subject_id] = CaseLabel(
            case_id=subject.subject_id,
            cell_id=location.cell_id,
            expected=location.expected.verdict,
            strata=location.strata,
        )
    return labels


def case_errors(verdict: str, label: CaseLabel) -> dict[str, bool]:
    """The case's three error flags by `score_adjudication`'s rules, and whether it is wrong."""
    expected = ExpectedLabel(category="", anchor_resolvable=True, verdict=label.expected)
    scoring = score_adjudication(
        [(ModelVerdict(location_id=label.case_id, verdict=verdict), expected)]
    )
    return {
        "over_erasure": scoring.over_erasure_rate.numerator == 1,
        "over_retention": scoring.over_retention_rate.numerator == 1,
        "mis_escalation": scoring.mis_escalation_rate.numerator == 1,
        "wrong": verdict != label.expected,
    }


def error_flags(
    verdicts: Mapping[str, str], labels: Mapping[str, CaseLabel]
) -> dict[str, dict[str, bool]]:
    """`{kind: {case_id: flag}}` over every labelled case."""
    missing = sorted(set(labels) - set(verdicts))
    if missing:
        raise AdjudicationComparisonError(f"no verdict for {missing[:5]}")
    per_case = {case: case_errors(verdicts[case], label) for case, label in labels.items()}
    return {kind: {case: flags[kind] for case, flags in per_case.items()} for kind in ERROR_KINDS}


def rate_row(numerator: int, denominator: int) -> dict[str, Any]:
    """A count with its rate and Wilson 95% interval, in the published results' layout."""
    rate = Rate(
        numerator=numerator,
        denominator=denominator,
        value=None if denominator == 0 else numerator / denominator,
    )
    return {
        "rate": rate.model_dump(mode="json"),
        "interval": wilson_interval(rate).model_dump(mode="json"),
    }


def sonnet_first_try_verdicts(
    cache_root: Path,
    subjects: Sequence[AdjudicationSubject],
    *,
    tier: str,
    model_id: str = SONNET_MODEL_ID,
) -> dict[str, str]:
    """`{case_id: verdict}` from the committed Sonnet sweep's first try, one per case."""
    raw = first_try_raw_responses(cache_root, model_id=model_id, runner_id=tier)
    verdicts: dict[str, str] = {}
    for case_id, items in adjudication_verdicts(raw, subjects).items():
        if len(items) != 1:
            raise AdjudicationComparisonError(f"{case_id}: {len(items)} Sonnet verdicts")
        verdicts[case_id] = items[0]["verdict"]
    return verdicts


# --- Exact tests --------------------------------------------------------------------------


def exact_mcnemar_greater(predicted: int, other: int) -> float:
    """One-sided exact McNemar: P(at least `predicted` of the discordant pairs go that way)."""
    n = predicted + other
    if n == 0:
        return 1.0
    return float(Fraction(sum(math.comb(n, i) for i in range(predicted, n + 1)), 2**n))


def fisher_exact_greater(wrong_a: int, n_a: int, wrong_b: int, n_b: int) -> float:
    """One-sided Fisher exact: P(group a holds at least `wrong_a` of the wrong cases).

    Under the null every arrangement of the wrong cases over the two groups is equally
    likely, so group a's count is hypergeometric.
    """
    total, wrong = n_a + n_b, wrong_a + wrong_b
    tail = sum(
        math.comb(wrong, x) * math.comb(total - wrong, n_a - x)
        for x in range(wrong_a, min(n_a, wrong) + 1)
    )
    return float(Fraction(tail, math.comb(total, n_a)))


def _discordant(a: Mapping[str, bool], b: Mapping[str, bool], cases: Sequence[str]) -> tuple:
    only_a = sorted(case for case in cases if a[case] and not b[case])
    only_b = sorted(case for case in cases if b[case] and not a[case])
    return only_a, only_b


def h2a(
    jev_t3_wrong: Mapping[str, bool],
    sonnet_t3_wrong: Mapping[str, bool],
    labels: Mapping[str, CaseLabel],
) -> dict[str, Any]:
    date = sorted(case for case, label in labels.items() if label.is_date_case)
    other = sorted(case for case, label in labels.items() if not label.is_date_case)
    date_wrong = sum(jev_t3_wrong[case] for case in date)
    other_wrong = sum(jev_t3_wrong[case] for case in other)
    p_fisher = fisher_exact_greater(date_wrong, len(date), other_wrong, len(other))
    only_jev, only_sonnet = _discordant(jev_t3_wrong, sonnet_t3_wrong, date)
    p_mcnemar = exact_mcnemar_greater(len(only_jev), len(only_sonnet))
    return {
        "date_vs_other": {
            "test": "Fisher exact, one-sided (date-case rate higher)",
            "date_wrong": rate_row(date_wrong, len(date)),
            "other_wrong": rate_row(other_wrong, len(other)),
            "p_exact": p_fisher,
        },
        "jev_vs_sonnet_on_date_cases": {
            "test": "exact McNemar, one-sided (Jev wrong more often), paired by case",
            "cases": len(date),
            "jev_wrong": sum(jev_t3_wrong[case] for case in date),
            "sonnet_wrong": sum(sonnet_t3_wrong[case] for case in date),
            "only_jev": len(only_jev),
            "only_sonnet": len(only_sonnet),
            "p_exact": p_mcnemar,
        },
        "p_exact": max(p_fisher, p_mcnemar),
        "p_rule": "the larger of the two, since both must hold",
    }


def h2b(
    jev_t2_over_erasure: Mapping[str, bool],
    jev_t3_over_erasure: Mapping[str, bool],
) -> dict[str, Any]:
    cases = sorted(jev_t2_over_erasure)
    only_t2, only_t3 = _discordant(jev_t2_over_erasure, jev_t3_over_erasure, cases)
    return {
        "test": "exact McNemar, one-sided (T3 over-erasure lower), paired by case",
        "cases": len(cases),
        "t2_over_erasure": sum(jev_t2_over_erasure.values()),
        "t3_over_erasure": sum(jev_t3_over_erasure.values()),
        "only_t2": len(only_t2),
        "only_t3": len(only_t3),
        "p_exact": exact_mcnemar_greater(len(only_t2), len(only_t3)),
    }


def h2c(jev_t3_wrong: Mapping[str, bool], sonnet_t3_wrong: Mapping[str, bool]) -> dict[str, Any]:
    cases = sorted(jev_t3_wrong)
    only_jev, only_sonnet = _discordant(jev_t3_wrong, sonnet_t3_wrong, cases)
    if len(only_jev) > len(only_sonnet):
        direction = "jev_more_wrong"
    elif len(only_jev) < len(only_sonnet):
        direction = "jev_fewer_wrong"
    else:
        direction = "equal"
    return {
        "test": "exact McNemar, two-sided, paired by case",
        "cases": len(cases),
        "jev_wrong": sum(jev_t3_wrong.values()),
        "sonnet_wrong": sum(sonnet_t3_wrong.values()),
        "only_jev": len(only_jev),
        "only_sonnet": len(only_sonnet),
        "direction": direction,
        "p_exact": exact_mcnemar(len(only_jev), len(only_sonnet)),
    }


def order_family(
    *,
    jev_t2: Mapping[str, Mapping[str, bool]],
    jev_t3: Mapping[str, Mapping[str, bool]],
    sonnet_t3: Mapping[str, Mapping[str, bool]],
    labels: Mapping[str, CaseLabel],
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """H2a, H2b and H2c in one option order, Holm across the three.

    Each argument is `error_flags` output: `{kind: {case_id: flag}}`.
    """
    tests = {
        "H2a": h2a(jev_t3["wrong"], sonnet_t3["wrong"], labels),
        "H2b": h2b(jev_t2["over_erasure"], jev_t3["over_erasure"]),
        "H2c": h2c(jev_t3["wrong"], sonnet_t3["wrong"]),
    }
    adjusted = holm({name: test["p_exact"] for name, test in tests.items()})
    for name, test in tests.items():
        test["p_holm"] = adjusted[name]
        test["significant_holm"] = adjusted[name] < alpha
    return tests


def apply_reading(families: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, str]:
    """The pre-registered reading of each hypothesis from the three orders' families."""
    primary = families["primary"]

    def all_orders(name: str, direction: str | None = None) -> bool:
        return all(
            families[order][name]["significant_holm"]
            and (direction is None or families[order][name]["direction"] == direction)
            for order in ORDERS
        )

    readings: dict[str, str] = {}
    if all_orders("H2a"):
        readings["H2a"] = READING_CONFIRMED
    elif primary["H2a"]["significant_holm"]:
        readings["H2a"] = READING_ORDER_SENSITIVE
    else:
        readings["H2a"] = READING_NONE

    readings["H2b"] = READING_CONFIRMED if primary["H2b"]["significant_holm"] else READING_NONE

    if all_orders("H2c", "jev_more_wrong"):
        readings["H2c"] = READING_CONFIRMED
    elif primary["H2c"]["significant_holm"] and primary["H2c"]["direction"] == "jev_fewer_wrong":
        readings["H2c"] = READING_FEWER
    elif primary["H2c"]["significant_holm"]:
        readings["H2c"] = READING_ORDER_SENSITIVE
    else:
        readings["H2c"] = READING_NONE
    return readings


# --- Descriptive tables -------------------------------------------------------------------


def _counts(flags: Mapping[str, Mapping[str, bool]], cases: Sequence[str]) -> dict[str, Any]:
    return {kind: rate_row(sum(flags[kind][c] for c in cases), len(cases)) for kind in ERROR_KINDS}


def wrong_verdict_summary(
    flags: Mapping[str, Mapping[str, bool]], labels: Mapping[str, CaseLabel]
) -> dict[str, Any]:
    """Error counts over all cases, the date cases and the rest; the date share of wrong."""
    cases = sorted(labels)
    date = [case for case in cases if labels[case].is_date_case]
    other = [case for case in cases if not labels[case].is_date_case]
    wrong = sum(flags["wrong"][case] for case in cases)
    date_wrong = sum(flags["wrong"][case] for case in date)
    return {
        "all_cases": _counts(flags, cases),
        "date_cases": _counts(flags, date),
        "other_cases": _counts(flags, other),
        "date_share_of_wrong": None if wrong == 0 else date_wrong / wrong,
    }


def cell_map(
    jev_t3_wrong: Mapping[str, bool],
    sonnet_t3_wrong: Mapping[str, bool],
    labels: Mapping[str, CaseLabel],
) -> list[dict[str, Any]]:
    """Per cell, both models' first-try wrong count at T3, and which is wrong on over half."""
    by_cell: dict[str, list[str]] = {}
    for case, label in labels.items():
        by_cell.setdefault(label.cell_id, []).append(case)
    rows = []
    for cell, cases in sorted(by_cell.items()):
        jev = sum(jev_t3_wrong[case] for case in cases)
        sonnet = sum(sonnet_t3_wrong[case] for case in cases)
        jev_over, sonnet_over = 2 * jev > len(cases), 2 * sonnet > len(cases)
        if jev_over and sonnet_over:
            reading = "both_wrong_on_over_half_keep_in_code_candidate"
        elif sonnet_over:
            reading = "sonnet_only_model_specific"
        elif jev_over:
            reading = "jev_only_model_specific"
        else:
            reading = "neither"
        rows.append(
            {
                "cell": cell,
                "cases": len(cases),
                "date_cell": all(labels[case].is_date_case for case in cases),
                "sonnet_wrong": sonnet,
                "jev_wrong": jev,
                "reading": reading,
            }
        )
    return rows


def split_run_trigger(
    jev_t3_primary: Mapping[str, Mapping[str, bool]],
    labels: Mapping[str, CaseLabel],
    h2a_reading: str,
) -> dict[str, Any]:
    """Q5: fires when date cases hold over half of Jev's T3 wrong verdicts, or H2a holds."""
    wrong = [case for case in sorted(labels) if jev_t3_primary["wrong"][case]]
    date_wrong = sum(labels[case].is_date_case for case in wrong)
    share = None if not wrong else date_wrong / len(wrong)
    by_share = share is not None and share > 0.5
    by_h2a = h2a_reading == READING_CONFIRMED
    return {
        "brief": "briefs/decision-model-run.md Q5",
        "unit": "T3, first try, primary option order",
        "jev_wrong": len(wrong),
        "date_case_wrong": date_wrong,
        "date_share_of_wrong": share,
        "share_rule": "date cases hold more than half of Jev's wrong verdicts",
        "share_rule_met": by_share,
        "h2a_reading": h2a_reading,
        "h2a_rule_met": by_h2a,
        "fires": by_share or by_h2a,
    }


def build_adjudication_comparison(
    *,
    subjects: Sequence[AdjudicationSubject],
    jev_first_try: Mapping[str, Mapping[str, Mapping[str, str]]],
    sonnet_first_try: Mapping[str, Mapping[str, str]],
    option_orders: Mapping[str, Sequence[str]],
    export_agent_sha: str,
    usage: Mapping[str, Any],
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """Assemble `results/jev/adjudication-comparison.json`.

    `jev_first_try` is `{order: {tier: {case_id: verdict}}}` for the orders `primary`, `rot1`
    and `rot2`; `sonnet_first_try` is `{tier: {case_id: verdict}}`.
    """
    labels = case_labels(subjects)
    jev = {
        order: {tier: error_flags(jev_first_try[order][tier], labels) for tier in TIERS}
        for order in ORDERS
    }
    sonnet = {tier: error_flags(sonnet_first_try[tier], labels) for tier in TIERS}
    for tier in TIERS:
        counts = {kind: sum(sonnet[tier][kind].values()) for kind in ERROR_KINDS}
        if counts != SONNET_PUBLISHED[tier]:
            raise AdjudicationComparisonError(
                f"Sonnet {tier} first try {counts} is not the published {SONNET_PUBLISHED[tier]}"
            )

    families = {
        order: order_family(
            jev_t2=jev[order]["t2"],
            jev_t3=jev[order]["t3"],
            sonnet_t3=sonnet["t3"],
            labels=labels,
            alpha=alpha,
        )
        for order in ORDERS
    }
    readings = apply_reading(families)
    return {
        "brief": "briefs/decision-model-run.md Q2, Q5",
        "export_agent_sha": export_agent_sha,
        "unit": "case (one location each), first try (sample 0)",
        "wrong_verdict": "the case's verdict differs from the answer key's",
        "date_cases": "boundary_flag other than none, or anchor_computable false",
        "option_orders": {order: list(option_orders[order]) for order in ORDERS},
        "alpha": alpha,
        "correction": "Holm across H2a, H2b and H2c within each option order",
        "reading_rules": {
            "H2a": "significant after Holm in all three orders",
            "H2b": "significant after Holm in the primary order",
            "H2c": (
                "confirmed when significant after Holm with Jev more wrong in all three orders; "
                "reported as Jev making fewer wrong verdicts when significant after Holm in the "
                "primary order in that direction"
            ),
        },
        "readings": readings,
        "tests_by_order": families,
        "wrong_verdicts": {
            tier: {
                SONNET_MODEL_ID: wrong_verdict_summary(sonnet[tier], labels),
                "jev-1.13.0": {
                    order: wrong_verdict_summary(jev[order][tier], labels) for order in ORDERS
                },
            }
            for tier in TIERS
        },
        "t3_cell_map_descriptive": cell_map(
            jev["primary"]["t3"]["wrong"], sonnet["t3"]["wrong"], labels
        ),
        "split_run_trigger": split_run_trigger(jev["primary"]["t3"], labels, readings["H2a"]),
        "usage": dict(usage),
    }

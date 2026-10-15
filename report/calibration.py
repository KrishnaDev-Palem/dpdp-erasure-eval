"""Q3 of `briefs/decision-model-run.md`: partial handover on Jev's own probabilities.

If Jev acts only when its top probability p_max reaches a threshold t, how much does it act on,
and how often is the act an over-erasure? TypeSafe's `confidence` is linear in p_max, so a
threshold on either is the same threshold.

- A case is **acted on** at t when p_max >= t, whatever the top option is.
- **Over-erasure among acted-on cases** counts the cases acted on with `erase` whose answer is
  `retain` or `escalate`, over the number acted on.
- Thresholds run from 0.34 to 1.00 in steps of 0.01, written as k / 100 so each compares
  exactly with the 0.01 grid the probabilities come back on.

**Held-out split.** Within each cell, cases are ordered by the SHA-256 of the real case id
(UTF-8, hex digest), and the first 30%, rounded down, form the tuning part; the rest form the
test part. The export's `split` field assigns whole cells, so it cannot be used.

**Choosing a threshold.** For each target, the lowest threshold whose tuning-part over-erasure
among acted-on cases is at or below the target, with at least 10 tuning cases acted on. If none
qualifies, no threshold meets that target.

Everything is at T3, first try, primary option order. The reading is per cell: at a chosen
threshold, which cells Jev acts on and which it defers on. No headline coverage share is
reported, because the slice is weighted by design.

Brier score and the reliability table are over all 350 cases, since nothing is tuned on them.
The multi-class Brier score sums (p - y)^2 over the three options (0 to 2); the top-option score
is (p_max - correct)^2 (0 to 1) and matches the reliability table, which buckets p_max.
"Correct" and "acted on with `erase`" read the API's choice, the scored verdict, even in the
rare answer whose choice is not the top option (counted in `stability.json`).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import Any, Protocol

from core.scoring.adjudication import stratum_value_key
from core.types import STRATA_GROUP_FIELDS, AdjudicationSubject
from report.adjudication_comparison import CaseLabel, case_errors, case_labels, rate_row

TUNING_SHARE = Fraction(3, 10)
THRESHOLDS: tuple[float, ...] = tuple(k / 100 for k in range(34, 101))
TARGETS: dict[str, Fraction] = {"1%": Fraction(1, 100), "5%": Fraction(5, 100)}
MIN_TUNING_ACTED_ON = 10
# Half-open buckets of p_max, the last one closed: [0.99, 1.0].
RELIABILITY_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("[0, 0.5)", 0.0, 0.5),
    ("[0.5, 0.7)", 0.5, 0.7),
    ("[0.7, 0.9)", 0.7, 0.9),
    ("[0.9, 0.99)", 0.9, 0.99),
    ("[0.99, 1.0]", 0.99, math.inf),
)


class Answer(Protocol):
    """What Q3 and Q4 read of one response: the model, the API's choice, the probabilities."""

    @property
    def model(self) -> str: ...

    @property
    def choice(self) -> str: ...

    @property
    def probabilities(self) -> dict[str, float]: ...


def split_digest(case_id: str) -> str:
    return hashlib.sha256(case_id.encode("utf-8")).hexdigest()


def tuning_split(labels: Mapping[str, CaseLabel]) -> tuple[list[str], list[str]]:
    """`(tuning, test)` case ids: per cell, the first 30% by SHA-256, rounded down."""
    by_cell: dict[str, list[str]] = {}
    for case, label in labels.items():
        by_cell.setdefault(label.cell_id, []).append(case)
    tuning: list[str] = []
    test: list[str] = []
    for _, cases in sorted(by_cell.items()):
        ordered = sorted(cases, key=split_digest)
        cut = math.floor(len(ordered) * TUNING_SHARE)
        tuning.extend(ordered[:cut])
        test.extend(ordered[cut:])
    return sorted(tuning), sorted(test)


def _top(answer: Answer) -> float:
    return max(answer.probabilities.values())


def _over_erasure(answer: Answer, label: CaseLabel) -> bool:
    return case_errors(answer.choice, label)["over_erasure"]


def coverage_curve(
    answers: Mapping[str, Answer],
    labels: Mapping[str, CaseLabel],
    cases: Sequence[str],
) -> list[dict[str, Any]]:
    """At every threshold: cases acted on, their share, and over-erasure among them."""
    rows = []
    for threshold in THRESHOLDS:
        acted = [case for case in cases if _top(answers[case]) >= threshold]
        over = sum(_over_erasure(answers[case], labels[case]) for case in acted)
        rows.append(
            {
                "threshold": threshold,
                "cases": len(cases),
                "acted_on": len(acted),
                "acted_on_share": len(acted) / len(cases) if cases else None,
                "over_erasures": over,
                "over_erasure_among_acted_on": over / len(acted) if acted else None,
            }
        )
    return rows


def choose_threshold(tuning_curve: Sequence[Mapping[str, Any]], target: Fraction) -> float | None:
    """The lowest threshold at or below the target with at least 10 tuning cases acted on."""
    for row in tuning_curve:
        acted = row["acted_on"]
        if acted >= MIN_TUNING_ACTED_ON and row["over_erasures"] <= target * acted:
            return row["threshold"]
    return None


def at_threshold(
    answers: Mapping[str, Answer],
    labels: Mapping[str, CaseLabel],
    cases: Sequence[str],
    threshold: float,
    target: Fraction,
) -> dict[str, Any]:
    """On the test part: what Jev acts on at t, over-erasure among it, and the per-cell map."""
    acted = [case for case in cases if _top(answers[case]) >= threshold]
    over = sum(_over_erasure(answers[case], labels[case]) for case in acted)
    by_cell: dict[str, list[str]] = {}
    for case in cases:
        by_cell.setdefault(labels[case].cell_id, []).append(case)
    cells = []
    for cell, cell_cases in sorted(by_cell.items()):
        cell_acted = [case for case in cell_cases if _top(answers[case]) >= threshold]
        cells.append(
            {
                "cell": cell,
                "cases": len(cell_cases),
                "acted_on": len(cell_acted),
                "wrong_among_acted_on": sum(
                    answers[case].choice != labels[case].expected for case in cell_acted
                ),
                "over_erasures_among_acted_on": sum(
                    _over_erasure(answers[case], labels[case]) for case in cell_acted
                ),
            }
        )
    return {
        "threshold": threshold,
        "test_cases": len(cases),
        "acted_on": len(acted),
        "over_erasure_among_acted_on": rate_row(over, len(acted)),
        "meets_target_on_test_part": bool(acted) and over <= target * len(acted),
        "acts_on_every_case_in": [c["cell"] for c in cells if c["acted_on"] == c["cases"]],
        "acts_on_some_cases_in": [c["cell"] for c in cells if 0 < c["acted_on"] < c["cases"]],
        "defers_on_every_case_in": [c["cell"] for c in cells if c["acted_on"] == 0],
        "by_cell": cells,
    }


def brier_scores(
    answers: Mapping[str, Answer], labels: Mapping[str, CaseLabel], cases: Sequence[str]
) -> dict[str, Any]:
    if not cases:
        return {"cases": 0, "multi_class": None, "top_option": None}
    multi = top = 0.0
    for case in cases:
        answer, expected = answers[case], labels[case].expected
        multi += sum(
            (p - (1.0 if option == expected else 0.0)) ** 2
            for option, p in answer.probabilities.items()
        )
        top += (_top(answer) - (1.0 if answer.choice == expected else 0.0)) ** 2
    return {"cases": len(cases), "multi_class": multi / len(cases), "top_option": top / len(cases)}


def reliability_table(
    answers: Mapping[str, Answer], labels: Mapping[str, CaseLabel], cases: Sequence[str]
) -> list[dict[str, Any]]:
    """Per p_max bucket: cases, mean p_max, and the share whose top option is correct."""
    rows = []
    for name, low, high in RELIABILITY_BUCKETS:
        inside = [case for case in cases if low <= _top(answers[case]) < high]
        correct = sum(answers[case].choice == labels[case].expected for case in inside)
        rows.append(
            {
                "bucket": name,
                "cases": len(inside),
                "mean_p_max": (
                    sum(_top(answers[case]) for case in inside) / len(inside) if inside else None
                ),
                "correct": rate_row(correct, len(inside)),
            }
        )
    return rows


def p_max_histogram(answers: Mapping[str, Answer], cases: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        key = f"{_top(answers[case]):.2f}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _by_stratum(
    answers: Mapping[str, Answer], labels: Mapping[str, CaseLabel], cases: Sequence[str]
) -> list[dict[str, Any]]:
    out = []
    for field in STRATA_GROUP_FIELDS:
        groups: dict[str, list[str]] = {}
        for case in cases:
            key = stratum_value_key(labels[case].strata.model_dump()[field])
            groups.setdefault(key, []).append(case)
        out.append(
            {
                "field": field,
                "rows": [
                    {
                        "key": key,
                        "brier": brier_scores(answers, labels, group),
                        "reliability": reliability_table(answers, labels, group),
                    }
                    for key, group in sorted(groups.items())
                ],
            }
        )
    return out


def build_calibration(
    *,
    subjects: Sequence[AdjudicationSubject],
    answers: Mapping[str, Answer],
    runner_id: str,
    export_agent_sha: str,
) -> dict[str, Any]:
    """Assemble `results/jev/calibration.json` from T3's first try in the primary order."""
    labels = case_labels(subjects)
    missing = sorted(set(labels) - set(answers))
    if missing:
        raise ValueError(f"no answer for {missing[:5]}")
    every = sorted(labels)
    tuning, test = tuning_split(labels)
    tuning_curve = coverage_curve(answers, labels, tuning)
    test_curve = coverage_curve(answers, labels, test)

    targets: dict[str, Any] = {}
    for name, target in TARGETS.items():
        chosen = choose_threshold(tuning_curve, target)
        targets[name] = {
            "target": float(target),
            "chosen_threshold": chosen,
            "test_part": (
                None if chosen is None else at_threshold(answers, labels, test, chosen, target)
            ),
        }

    return {
        "brief": "briefs/decision-model-run.md Q3",
        "export_agent_sha": export_agent_sha,
        "runner_id": runner_id,
        "unit": "case (one location each), T3, first try (sample 0), primary option order",
        "confidence": "p_max, the top option's probability",
        "acted_on_rule": "p_max >= threshold, whatever the top option is",
        "over_erasure_rule": (
            "acted on with erase and the answer key is retain or escalate, over cases acted on"
        ),
        "split": {
            "rule": (
                "within each cell, cases ordered by SHA-256 of the real case id (UTF-8, hex "
                "digest); the first 30%, rounded down, form the tuning part"
            ),
            "tuning_cases": len(tuning),
            "test_cases": len(test),
            "tuning_case_ids": tuning,
        },
        "threshold_rule": (
            f"lowest threshold whose tuning-part over-erasure among acted-on cases is at or "
            f"below the target, with at least {MIN_TUNING_ACTED_ON} tuning cases acted on"
        ),
        "targets": targets,
        "coverage_curve": {"test_part": test_curve, "tuning_part": tuning_curve},
        "brier": {
            "cases": "all 350; nothing is tuned on them",
            "overall": brier_scores(answers, labels, every),
        },
        "reliability": {
            "cases": "all 350",
            "correct_rule": "the API's choice equals the answer key",
            "overall": reliability_table(answers, labels, every),
            "by_stratum": _by_stratum(answers, labels, every),
        },
        "p_max_histogram": p_max_histogram(answers, every),
    }

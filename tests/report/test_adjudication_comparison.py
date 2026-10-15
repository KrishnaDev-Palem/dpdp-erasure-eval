"""Q2 and the Q5 trigger on constructed Jev verdicts. Sonnet's side is the committed cache.

No Jev response exists when these run: each test builds Jev's first try from the answer key
(an oracle, Sonnet's own verdicts, or a model wrong on chosen cases), so every reading the
brief pre-registers is reached on purpose.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from core.export.loader import load_export
from core.scoring.adjudication import score_adjudication
from core.types import ExpectedLabel, ModelVerdict
from report import adjudication_comparison as q2
from report.paired_delta import exact_mcnemar

REPO_ROOT = Path(__file__).resolve().parents[2]
ORDERS = {
    "primary": ("erase", "retain", "escalate"),
    "rot1": ("retain", "escalate", "erase"),
    "rot2": ("escalate", "erase", "retain"),
}
SONNET_T3_OVER_HALF = [
    "arity4_cite_1_securities",
    "boundary_elapsed_1d_customer",
    "elapsed_no_trigger_customer",
    "elapsed_no_trigger_payment",
    "elapsed_no_trigger_securities",
    "marketing_active",
    "ordinary_elapsed_with_purpose_payment",
    "ordinary_erase_securities",
    "ordinary_inactivity_erase_payment",
]


@pytest.fixture(scope="module")
def subjects():
    return load_export(REPO_ROOT / "export").subjects


@pytest.fixture(scope="module")
def labels(subjects):
    return q2.case_labels(subjects)


@pytest.fixture(scope="module")
def sonnet(subjects):
    return {
        tier: q2.sonnet_first_try_verdicts(REPO_ROOT / "cache", subjects, tier=tier)
        for tier in ("t2", "t3")
    }


def _oracle(labels) -> dict[str, str]:
    return {case: label.expected for case, label in labels.items()}


def _wrong_on(labels, cases) -> dict[str, str]:
    """The answer key, except a wrong verdict on the given cases (erase, or retain on erase)."""
    verdicts = _oracle(labels)
    for case in cases:
        verdicts[case] = "retain" if labels[case].expected == "erase" else "erase"
    return verdicts


def _build(subjects, sonnet, jev_t2, jev_t3, *, by_order=None):
    first_try = by_order or {order: {"t2": jev_t2, "t3": jev_t3} for order in ORDERS}
    return q2.build_adjudication_comparison(
        subjects=subjects,
        jev_first_try=first_try,
        sonnet_first_try=sonnet,
        option_orders=ORDERS,
        export_agent_sha="sha",
        usage={},
    )


# --- The slice and Sonnet's side ----------------------------------------------------------


def test_the_slice_has_88_date_cases_in_6_cells_all_retain_or_escalate(labels) -> None:
    date = [label for label in labels.values() if label.is_date_case]
    assert len(labels) == 350 and len(date) == 88
    assert len({label.cell_id for label in date}) == 6
    assert {label.expected for label in date} == {"retain", "escalate"}
    assert all(
        all(other.is_date_case for other in labels.values() if other.cell_id == label.cell_id)
        for label in date
    )


def test_sonnet_first_try_reproduces_the_published_counts(sonnet, labels) -> None:
    for tier in ("t2", "t3"):
        flags = q2.error_flags(sonnet[tier], labels)
        assert {kind: sum(flags[kind].values()) for kind in q2.ERROR_KINDS} == (
            q2.SONNET_PUBLISHED[tier]
        )


def test_sonnet_date_case_wrong_verdicts_are_68_at_t2_and_22_at_t3(sonnet, labels) -> None:
    for tier, expected in (("t2", 68), ("t3", 22)):
        summary = q2.wrong_verdict_summary(q2.error_flags(sonnet[tier], labels), labels)
        assert summary["date_cases"]["wrong"]["rate"]["numerator"] == expected
    t3 = q2.wrong_verdict_summary(q2.error_flags(sonnet["t3"], labels), labels)
    assert t3["date_share_of_wrong"] == pytest.approx(22 / 139)


def test_a_sonnet_count_that_is_not_the_published_one_stops_the_build(
    subjects, sonnet, labels
) -> None:
    broken = {**sonnet, "t3": _oracle(labels)}
    with pytest.raises(q2.AdjudicationComparisonError, match="not the published"):
        _build(subjects, broken, _oracle(labels), _oracle(labels))


def test_an_erase_on_an_escalate_case_is_two_errors_but_one_wrong_verdict(labels) -> None:
    case, label = next((c, lab) for c, lab in labels.items() if lab.expected == "escalate")
    flags = q2.case_errors("erase", label)
    assert flags == {
        "over_erasure": True,
        "over_retention": False,
        "mis_escalation": True,
        "wrong": True,
    }
    expected = ExpectedLabel(category="x", anchor_resolvable=False, verdict="escalate")
    scoring = score_adjudication([(ModelVerdict(location_id=case, verdict="erase"), expected)])
    assert scoring.over_erasure_rate.numerator == scoring.mis_escalation_rate.numerator == 1


# --- Exact tests --------------------------------------------------------------------------


def test_one_sided_mcnemar_is_the_upper_binomial_tail() -> None:
    assert q2.exact_mcnemar_greater(6, 0) == 1 / 64
    assert q2.exact_mcnemar_greater(0, 6) == 1.0
    assert q2.exact_mcnemar_greater(3, 3) == 42 / 64
    assert q2.exact_mcnemar_greater(0, 0) == 1.0
    for a, b in ((6, 1), (2, 9), (10, 10)):
        one_sided = min(q2.exact_mcnemar_greater(a, b), q2.exact_mcnemar_greater(b, a))
        assert exact_mcnemar(a, b) == pytest.approx(min(1.0, 2 * one_sided))


def test_one_sided_fisher_is_the_upper_hypergeometric_tail() -> None:
    # Four of eight wrong, three of them in group a of four: (C(4,3)C(4,1) + 1) / C(8,4).
    assert q2.fisher_exact_greater(3, 4, 1, 4) == pytest.approx(17 / 70)
    assert q2.fisher_exact_greater(0, 4, 4, 4) == 1.0
    assert q2.fisher_exact_greater(88, 88, 0, 262) == pytest.approx(1 / math.comb(350, 88))


# --- Readings -----------------------------------------------------------------------------


def test_jev_identical_to_sonnet_reads_as_no_detectable_difference(
    subjects, sonnet, labels
) -> None:
    report = _build(subjects, sonnet, sonnet["t2"], sonnet["t3"])
    assert report["readings"] == {
        "H2a": q2.READING_NONE,
        "H2b": q2.READING_CONFIRMED,
        "H2c": q2.READING_NONE,
    }
    primary = report["tests_by_order"]["primary"]
    # Sonnet's own T2 -> T3 drop is 142 -> 59 over-erasures, so H2b holds for a copy of it.
    assert primary["H2b"]["t2_over_erasure"] == 142 and primary["H2b"]["t3_over_erasure"] == 59
    assert primary["H2c"]["only_jev"] == primary["H2c"]["only_sonnet"] == 0
    trigger = report["split_run_trigger"]
    assert trigger["date_case_wrong"] == 22 and trigger["jev_wrong"] == 139
    assert trigger["fires"] is False


def test_holm_runs_across_the_three_hypotheses_within_each_order(subjects, sonnet, labels) -> None:
    report = _build(subjects, sonnet, sonnet["t2"], sonnet["t3"])
    for order in ORDERS:
        family = report["tests_by_order"][order]
        assert set(family) == {"H2a", "H2b", "H2c"}
        raw = sorted(family[name]["p_exact"] for name in family)
        adjusted = sorted(family[name]["p_holm"] for name in family)
        assert adjusted[0] == pytest.approx(min(1.0, 3 * raw[0]))


def test_wrong_on_every_date_case_confirms_h2a_and_fires_the_trigger(
    subjects, sonnet, labels
) -> None:
    date = [case for case, label in labels.items() if label.is_date_case]
    jev = _wrong_on(labels, date)
    report = _build(subjects, sonnet, jev, jev)
    assert report["readings"]["H2a"] == q2.READING_CONFIRMED
    h2a = report["tests_by_order"]["primary"]["H2a"]
    assert h2a["p_exact"] == max(
        h2a["date_vs_other"]["p_exact"], h2a["jev_vs_sonnet_on_date_cases"]["p_exact"]
    )
    trigger = report["split_run_trigger"]
    assert trigger["share_rule_met"] and trigger["h2a_rule_met"] and trigger["fires"]
    assert trigger["date_share_of_wrong"] == 1.0


def test_wrong_on_every_date_case_and_40_percent_of_the_rest_fires_through_h2a_only(
    subjects, sonnet, labels
) -> None:
    """The brief's example: the share rule alone would miss this model."""
    date = sorted(case for case, label in labels.items() if label.is_date_case)
    other = sorted(case for case, label in labels.items() if not label.is_date_case)
    jev = _wrong_on(labels, date + other[: math.ceil(0.4 * len(other))])
    trigger = _build(subjects, sonnet, jev, jev)["split_run_trigger"]
    assert trigger["date_share_of_wrong"] < 0.5
    assert not trigger["share_rule_met"] and trigger["h2a_rule_met"] and trigger["fires"]


def test_h2a_in_the_primary_order_only_is_not_confirmed(subjects, sonnet, labels) -> None:
    date = [case for case, label in labels.items() if label.is_date_case]
    weak = _wrong_on(labels, date)
    by_order = {
        "primary": {"t2": weak, "t3": weak},
        "rot1": {"t2": sonnet["t3"], "t3": sonnet["t3"]},
        "rot2": {"t2": weak, "t3": weak},
    }
    report = _build(subjects, sonnet, None, None, by_order=by_order)
    assert report["tests_by_order"]["primary"]["H2a"]["significant_holm"]
    assert not report["tests_by_order"]["rot1"]["H2a"]["significant_holm"]
    assert report["readings"]["H2a"] == q2.READING_ORDER_SENSITIVE
    # Q5 reads H2a as pre-registered, so only the share rule can fire it here.
    assert report["split_run_trigger"]["h2a_rule_met"] is False


def test_an_oracle_reads_as_fewer_wrong_verdicts_than_sonnet(subjects, sonnet, labels) -> None:
    report = _build(subjects, sonnet, _oracle(labels), _oracle(labels))
    assert report["readings"]["H2c"] == q2.READING_FEWER
    h2c = report["tests_by_order"]["primary"]["H2c"]
    assert (h2c["only_jev"], h2c["only_sonnet"], h2c["direction"]) == (0, 139, "jev_fewer_wrong")
    # An oracle at both tiers has no over-erasure to lose: H2b cannot hold.
    assert report["readings"]["H2b"] == q2.READING_NONE
    assert report["split_run_trigger"]["fires"] is False


def test_h2c_more_wrong_needs_all_three_orders(subjects, sonnet, labels) -> None:
    always_erase = {case: "erase" for case in labels}
    everywhere = {order: {"t2": always_erase, "t3": always_erase} for order in ORDERS}
    assert _build(subjects, sonnet, None, None, by_order=everywhere)["readings"]["H2c"] == (
        q2.READING_CONFIRMED
    )
    one_order = {**everywhere, "rot2": {"t2": sonnet["t3"], "t3": sonnet["t3"]}}
    assert _build(subjects, sonnet, None, None, by_order=one_order)["readings"]["H2c"] == (
        q2.READING_ORDER_SENSITIVE
    )


def test_h2b_is_one_sided_toward_less_over_erasure_at_t3(subjects, sonnet, labels) -> None:
    always_erase = {case: "erase" for case in labels}
    lower = _build(subjects, sonnet, always_erase, _oracle(labels))
    assert lower["readings"]["H2b"] == q2.READING_CONFIRMED
    higher = _build(subjects, sonnet, _oracle(labels), always_erase)
    assert higher["readings"]["H2b"] == q2.READING_NONE
    assert higher["tests_by_order"]["primary"]["H2b"]["p_exact"] == 1.0


# --- Cell map -----------------------------------------------------------------------------


def test_the_cell_map_names_sonnet_s_nine_cells(subjects, sonnet, labels) -> None:
    copy = _build(subjects, sonnet, sonnet["t2"], sonnet["t3"])["t3_cell_map_descriptive"]
    assert len(copy) == 24
    both = [row["cell"] for row in copy if row["reading"].startswith("both")]
    assert both == SONNET_T3_OVER_HALF

    oracle = _build(subjects, sonnet, _oracle(labels), _oracle(labels))["t3_cell_map_descriptive"]
    assert [row["cell"] for row in oracle if row["reading"] == "sonnet_only_model_specific"] == (
        SONNET_T3_OVER_HALF
    )
    assert sum(row["sonnet_wrong"] for row in oracle) == 139
    assert sum(row["cases"] for row in oracle) == 350
    assert sum(row["date_cell"] for row in oracle) == 6


def test_a_missing_jev_verdict_is_an_error_not_a_silent_skip(subjects, sonnet, labels) -> None:
    partial = dict(list(_oracle(labels).items())[:-1])
    with pytest.raises(q2.AdjudicationComparisonError, match="no verdict"):
        _build(subjects, sonnet, partial, partial)

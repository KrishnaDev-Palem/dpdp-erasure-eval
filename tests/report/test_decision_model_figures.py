"""The decision-model figures: pure helpers on constructed inputs, then the committed results."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from report.figures import decision_model as figs

REPO_ROOT = Path(__file__).resolve().parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "decision_model_figures", REPO_ROOT / "scripts" / "decision_model_figures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# {model verdict: {answer key: n}}
CONFUSION = {
    "erase": {"erase": 5, "retain": 3, "escalate": 1},
    "retain": {"erase": 2, "retain": 10, "escalate": 0},
    "escalate": {"erase": 0, "retain": 4, "escalate": 2},
}


def test_mixes_and_wrong_split_from_a_confusion_matrix() -> None:
    assert figs.verdict_mix(CONFUSION) == {"erase": 9, "retain": 12, "escalate": 6}
    assert figs.answer_key_mix(CONFUSION) == {"erase": 7, "retain": 17, "escalate": 3}
    assert figs.wrong_by_verdict_given(CONFUSION) == {"erase": 4, "retain": 2, "escalate": 4}


def test_constant_answer_is_wrong_on_every_case_with_another_key() -> None:
    key_mix = {"erase": 84, "retain": 238, "escalate": 28}
    assert figs.constant_wrong(key_mix, "erase") == {"erase": 266, "retain": 0, "escalate": 0}
    assert figs.constant_wrong(key_mix, "retain") == {"erase": 0, "retain": 112, "escalate": 0}


@pytest.mark.parametrize(
    ("expected", "metrics", "split"),
    [
        ("retain", (4, 0, 3), {"erase": 4, "retain": 0, "escalate": 3}),
        ("erase", (0, 6, 2), {"erase": 0, "retain": 6, "escalate": 2}),
        # An erase on an escalate case counts as both an over-erasure and a mis-escalation.
        ("escalate", (2, 0, 9), {"erase": 2, "retain": 7, "escalate": 0}),
    ],
)
def test_cell_split_by_verdict_given(expected, metrics, split) -> None:
    counts = dict(zip(("over_erasure", "over_retention", "mis_escalation"), metrics, strict=True))
    assert figs.cell_wrong_by_verdict_given(counts, expected) == split


def test_cell_rows_sort_by_group_and_stop_on_a_mismatch() -> None:
    zero = {"over_erasure": 0, "over_retention": 0, "mis_escalation": 0}
    cell_map = [
        {"cell": "b", "cases": 14, "sonnet_wrong": 0, "jev_wrong": 0, "reading": "neither"},
        {
            "cell": "a",
            "cases": 15,
            "sonnet_wrong": 15,
            "jev_wrong": 15,
            "reading": "both_wrong_on_over_half_keep_in_code_candidate",
        },
    ]
    erased = {**zero, "over_erasure": 15}
    rows = figs.cell_rows(
        cell_map,
        sonnet_by_cell={"a": erased, "b": zero},
        jev_by_cell={"a": erased, "b": zero},
        cell_keys={"a": "retain", "b": "retain"},
    )
    assert [row.cell for row in rows] == ["a", "b"]
    assert rows[0].jev == {"erase": 15, "retain": 0, "escalate": 0}
    with pytest.raises(figs.DecisionModelFigureError, match="does not sum"):
        figs.cell_rows(
            cell_map,
            sonnet_by_cell={"a": zero, "b": zero},
            jev_by_cell={"a": erased, "b": zero},
            cell_keys={"a": "retain", "b": "retain"},
        )


def test_coverage_points_keep_one_point_per_change_and_drop_empty_bars() -> None:
    curve = [
        {"threshold": t, "cases": 10, "acted_on": a, "over_erasures": o}
        for t, a, o in ((0.34, 10, 1), (0.5, 10, 1), (0.6, 4, 1), (0.9, 0, 0))
    ]
    points = figs.coverage_points(curve)
    assert [(p.threshold, p.acted_on) for p in points] == [(0.34, 10), (0.6, 4)]
    assert points[1].over_erasure_share == 0.25
    assert figs.coverage_at(curve, 0.5).acted_on == 10
    with pytest.raises(figs.DecisionModelFigureError):
        figs.coverage_at(curve, 0.77)


def test_reliability_points_skip_empty_buckets() -> None:
    def row(bucket, cases, numerator):
        return {
            "bucket": bucket,
            "cases": cases,
            "mean_p_max": 0.8 if cases else None,
            "correct": {
                "rate": {"numerator": numerator},
                "interval": {"lower": 0.1 if cases else None, "upper": 0.9 if cases else None},
            },
        }

    points = figs.reliability_points([row("[0, 0.5)", 0, 0), row("[0.7, 0.9)", 5, 3)])
    assert [(p.bucket, p.cases, p.correct) for p in points] == [("[0.7, 0.9)", 5, 3)]


# --- the committed results -------------------------------------------------------------------


@pytest.fixture(scope="module")
def results():
    return figs.load_results(REPO_ROOT / "results")


@pytest.fixture(scope="module")
def cell_keys():
    return _script().cell_keys(REPO_ROOT / "export")


def test_committed_results_give_the_published_counts(results) -> None:
    data = figs.figure_data(results)
    key = {"erase": 84, "retain": 238, "escalate": 28}
    assert data["mixes"]["t2"][figs.ANSWER_KEY] == key
    assert data["mixes"]["t3"][figs.ANSWER_KEY] == key
    assert data["mixes"]["t2"][figs.JEV] == {"erase": 345, "retain": 2, "escalate": 3}
    assert data["mixes"]["t3"][figs.JEV] == {"erase": 29, "retain": 321, "escalate": 0}
    totals = {
        tier: {label: sum(split.values()) for label, split in data["wrong"][tier].items()}
        for tier in figs.TIERS
    }
    assert totals["t2"] == {"Jev": 266, "Sonnet": 253, "Always\nerase": 266, "Always\nretain": 112}
    assert totals["t3"] == {"Jev": 113, "Sonnet": 139, "Always\nerase": 266, "Always\nretain": 112}


def test_committed_cell_map_splits_add_up(results, cell_keys) -> None:
    assert len(cell_keys) == 24
    data = figs.figure_data(results)
    rows = figs.cell_rows(
        data["cell_map"],
        sonnet_by_cell=data["sonnet_by_cell"],
        jev_by_cell=data["jev_by_cell"],
        cell_keys=cell_keys,
    )
    shared = [row.cell for row in rows if row.group == figs.CELL_GROUPS[0][0]]
    assert len(shared) == 4
    marketing = next(row for row in rows if row.cell == "marketing_active")
    assert marketing.sonnet == marketing.jev == {"erase": 15, "retain": 0, "escalate": 0}


def test_a_disagreeing_answer_key_stops_the_figures(results) -> None:
    broken = copy.deepcopy(results)
    broken["sonnet_t3"]["confusion_matrix"]["retain"]["retain"] -= 1
    broken["sonnet_t3"]["confusion_matrix"]["retain"]["erase"] += 1
    with pytest.raises(figs.DecisionModelFigureError, match="answer key"):
        figs.figure_data(broken)


def test_renders_four_files_byte_identically(results, cell_keys, tmp_path: Path) -> None:
    first = figs.generate_decision_model_figures(results, cell_keys, tmp_path / "a")
    second = figs.generate_decision_model_figures(results, cell_keys, tmp_path / "b")
    names = sorted(path.name for path in first)
    assert names == sorted(f"{stem}.png" for stem in figs.FIGURE_FILES.values())
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes()
    committed = REPO_ROOT / "results" / "jev" / "figures"
    assert sorted(path.name for path in committed.glob("*.png")) == names

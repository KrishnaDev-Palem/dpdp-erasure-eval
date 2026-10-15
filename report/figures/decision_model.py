"""Figures for the decision-model run: Jev beside the published Sonnet run, T2 and T3.

Every input is a committed results file (`results/jev/*.json`, `results/t2-live.json`,
`results/t3-live.json`) or the export's answer key, so the figures need no cache and no
call. The data helpers are pure and unit-tested; the renderers only draw what they return.

Colour always means a verdict: the verdict a model gave, or, for the answer key, the
correct one. A confusion matrix here is the scoring shape `{model verdict: {answer key: n}}`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, PercentFormatter

from report.figures import style
from report.figures.layout import heatmap_text_color
from report.figures.style import FONT_SIZE_ANNOTATION, FONT_SIZE_CAPTION, savefig_metadata

VERDICTS: tuple[str, ...] = ("erase", "retain", "escalate")

# Reference categorical slots 2, 1 and 3; validated all-pairs on white (CVD dE 9.2, normal-vision
# 24.0). Escalate sits below 3:1 contrast, so every chart labels its segments or totals directly.
VERDICT_COLORS: dict[str, str] = {"erase": "#eb6834", "retain": "#2a78d6", "escalate": "#1baf7a"}
COLOR_POINT = "#2a78d6"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
SEGMENT_GAP = "white"
SEGMENT_GAP_WIDTH = 1.0

TIERS: tuple[str, ...] = ("t2", "t3")
TIER_LABELS: dict[str, str] = {"t2": "Tier 2: + records", "t3": "Tier 3: + rule text"}

JEV = "jev-1.13.0"
SONNET = "claude-sonnet-5"
ANSWER_KEY = "answer key"
MODEL_LABELS: dict[str, str] = {ANSWER_KEY: "Answer key", SONNET: "Sonnet", JEV: "Jev"}

CELL_GROUPS: tuple[tuple[str, str], ...] = (
    ("both_wrong_on_over_half_keep_in_code_candidate", "Both wrong on more than half"),
    ("jev_only_model_specific", "Only Jev wrong on more than half"),
    ("sonnet_only_model_specific", "Only Sonnet wrong on more than half"),
    ("neither", "Neither"),
)

RELIABILITY_LABELS: dict[str, str] = {
    "[0, 0.5)": "below 0.5",
    "[0.5, 0.7)": "0.5 to 0.7",
    "[0.7, 0.9)": "0.7 to 0.9",
    "[0.9, 0.99)": "0.9 to 0.99",
    "[0.99, 1.0]": "0.99 and up",
}
LABELLED_THRESHOLDS: tuple[float, ...] = (0.34, 0.85, 0.9, 0.94, 0.98)
# Label positions in data coordinates (x, top y, alignment), clear of the points, whiskers and
# the diagonal; and label offsets in points for the curve.
RELIABILITY_LABEL_AT: dict[str, tuple[float, float, str]] = {
    "[0, 0.5)": (0.52, 0.12, "left"),
    "[0.5, 0.7)": (0.69, 0.27, "left"),
    "[0.7, 0.9)": (0.805, 0.6, "right"),
    "[0.9, 0.99)": (0.938, 0.47, "center"),
    "[0.99, 1.0]": (0.98, 0.12, "right"),
}
COVERAGE_LABEL_OFFSET: dict[float, tuple[int, int, str]] = {0.34: (-6, 8, "right")}
SEGMENT_LABEL_MIN = 18

Confusion = Mapping[str, Mapping[str, int]]


class DecisionModelFigureError(ValueError):
    """Raised when the inputs disagree with each other, rather than drawing a wrong figure."""


# --- data helpers -------------------------------------------------------------------------


def verdict_mix(confusion: Confusion) -> dict[str, int]:
    """How many cases got each verdict from the model (row sums)."""
    return {verdict: sum(confusion[verdict].values()) for verdict in VERDICTS}


def answer_key_mix(confusion: Confusion) -> dict[str, int]:
    """How many cases have each correct verdict (column sums)."""
    return {key: sum(confusion[verdict][key] for verdict in VERDICTS) for key in VERDICTS}


def wrong_by_verdict_given(confusion: Confusion) -> dict[str, int]:
    """Wrong verdicts, split by the verdict the model gave."""
    return {
        verdict: sum(n for key, n in confusion[verdict].items() if key != verdict)
        for verdict in VERDICTS
    }


def constant_wrong(key_mix: Mapping[str, int], verdict: str) -> dict[str, int]:
    """Wrong verdicts of a constant answer: every case whose correct verdict is another one."""
    wrong = sum(n for key, n in key_mix.items() if key != verdict)
    return {item: (wrong if item == verdict else 0) for item in VERDICTS}


def cell_wrong_by_verdict_given(metrics: Mapping[str, int], expected: str) -> dict[str, int]:
    """One cell's wrong verdicts by the verdict given, from its error counts and its one key.

    Every case in a cell has the same correct verdict, so each error kind names the verdict
    given: over-erasure is an erase; over-retention a retain on an erase case; mis-escalation an
    escalate on a decidable case, or a retain or erase on an escalate case (an erase there is
    also counted as an over-erasure).
    """
    over_erasure = metrics["over_erasure"]
    over_retention = metrics["over_retention"]
    mis_escalation = metrics["mis_escalation"]
    if expected == "retain":
        return {"erase": over_erasure, "retain": 0, "escalate": mis_escalation}
    if expected == "erase":
        return {"erase": 0, "retain": over_retention, "escalate": mis_escalation}
    if expected == "escalate":
        return {"erase": over_erasure, "retain": mis_escalation - over_erasure, "escalate": 0}
    raise DecisionModelFigureError(f"unknown verdict {expected!r}")


def by_cell_counts(tier_report: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    """`{cell: {error kind: count}}` from a `*-live.json` report's `by_cell` rows."""
    return {
        row["key"]: {kind: rate["rate"]["numerator"] for kind, rate in row["metrics"].items()}
        for row in tier_report["by_cell"]
    }


@dataclass(frozen=True)
class CellRow:
    group: str
    cell: str
    cases: int
    sonnet: dict[str, int]
    jev: dict[str, int]


def cell_rows(
    cell_map: Sequence[Mapping[str, Any]],
    *,
    sonnet_by_cell: Mapping[str, Mapping[str, int]],
    jev_by_cell: Mapping[str, Mapping[str, int]],
    cell_keys: Mapping[str, str],
) -> list[CellRow]:
    """The T3 cell map's rows in group order, each model's wrong verdicts split by verdict given.

    Stops if a split does not add up to the map's own wrong count for that model and cell.
    """
    rows: list[CellRow] = []
    groups = [group for group, _ in CELL_GROUPS]
    for entry in cell_map:
        cell = entry["cell"]
        if entry["reading"] not in groups:
            raise DecisionModelFigureError(f"{cell}: unknown reading {entry['reading']!r}")
        sonnet = cell_wrong_by_verdict_given(sonnet_by_cell[cell], cell_keys[cell])
        jev = cell_wrong_by_verdict_given(jev_by_cell[cell], cell_keys[cell])
        for name, split, wrong in (
            ("Sonnet", sonnet, entry["sonnet_wrong"]),
            ("Jev", jev, entry["jev_wrong"]),
        ):
            if sum(split.values()) != wrong:
                raise DecisionModelFigureError(
                    f"{cell}: {name} split {split} does not sum to the map's {wrong}"
                )
        rows.append(CellRow(entry["reading"], cell, entry["cases"], sonnet, jev))
    return sorted(rows, key=lambda row: (groups.index(row.group), row.cell))


@dataclass(frozen=True)
class ReliabilityPoint:
    bucket: str
    cases: int
    mean_confidence: float
    correct: int
    lower: float
    upper: float


def reliability_points(rows: Sequence[Mapping[str, Any]]) -> list[ReliabilityPoint]:
    """The pre-registered buckets that hold at least one case."""
    points = []
    for row in rows:
        if row["cases"] == 0:
            continue
        correct = row["correct"]
        points.append(
            ReliabilityPoint(
                bucket=row["bucket"],
                cases=row["cases"],
                mean_confidence=row["mean_p_max"],
                correct=correct["rate"]["numerator"],
                lower=correct["interval"]["lower"],
                upper=correct["interval"]["upper"],
            )
        )
    return points


@dataclass(frozen=True)
class CoveragePoint:
    threshold: float
    acted_on: int
    cases: int
    over_erasures: int

    @property
    def acted_on_share(self) -> float:
        return self.acted_on / self.cases

    @property
    def over_erasure_share(self) -> float:
        return self.over_erasures / self.acted_on


def coverage_points(curve: Sequence[Mapping[str, Any]]) -> list[CoveragePoint]:
    """One point per distinct (acted on, over-erasures) pair, at its lowest threshold.

    Thresholds that act on no case have no over-erasure share and are left out.
    """
    points: list[CoveragePoint] = []
    seen: set[tuple[int, int]] = set()
    for row in sorted(curve, key=lambda item: item["threshold"]):
        key = (row["acted_on"], row["over_erasures"])
        if row["acted_on"] == 0 or key in seen:
            continue
        seen.add(key)
        points.append(
            CoveragePoint(row["threshold"], row["acted_on"], row["cases"], row["over_erasures"])
        )
    return points


def coverage_at(curve: Sequence[Mapping[str, Any]], threshold: float) -> CoveragePoint:
    """The curve's row at one threshold."""
    for row in curve:
        if abs(row["threshold"] - threshold) < 1e-9:
            return CoveragePoint(
                row["threshold"], row["acted_on"], row["cases"], row["over_erasures"]
            )
    raise DecisionModelFigureError(f"no curve row at threshold {threshold}")


# --- rendering ----------------------------------------------------------------------------


def _save(fig: plt.Figure, path: Path, *, dpi: int, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        path,
        dpi=dpi,
        format=fmt,
        bbox_inches="tight",
        pad_inches=0.08,
        metadata=savefig_metadata(),
    )
    plt.close(fig)


def _header(
    fig: plt.Figure, title: str, *, subtitle: str | None = None, legend: bool = False
) -> float:
    """Title, optional subtitle and verdict legend at fixed inch offsets from the top.

    Returns the figure fraction below the header, for `tight_layout(rect=...)`.
    """
    height = fig.get_figheight()
    y = 1 - 0.04 / height
    fig.text(0.01, y, title, ha="left", va="top", fontsize=13, color=INK)
    y -= 0.32 / height
    if subtitle is not None:
        fig.text(
            0.01, y, subtitle, ha="left", va="top", fontsize=FONT_SIZE_CAPTION, color=INK_SECONDARY
        )
        y -= 0.24 / height
    if legend:
        handles = [Patch(facecolor=VERDICT_COLORS[v], label=v) for v in VERDICTS]
        fig.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(0.003, y + 0.04 / height),
            ncol=len(VERDICTS),
            frameon=False,
            fontsize=FONT_SIZE_ANNOTATION + 1,
            handlelength=1.4,
        )
        y -= 0.3 / height
    return y - 0.04 / height


def _label_color(verdict: str) -> str:
    rgb = tuple(int(VERDICT_COLORS[verdict][i : i + 2], 16) / 255 for i in (1, 3, 5))
    return heatmap_text_color(rgb)


def render_verdict_mix(
    mixes: Mapping[str, Mapping[str, Mapping[str, int]]],
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    """Fig 1: per tier, the answer key's verdict mix beside Sonnet's and Jev's first try."""
    rows = (ANSWER_KEY, SONNET, JEV)
    fig, axes = plt.subplots(len(TIERS), 1, figsize=(8.0, 4.6), sharex=True)
    for ax, tier in zip(axes, TIERS, strict=True):
        total = None
        for y, who in enumerate(reversed(rows)):
            mix = mixes[tier][who]
            row_total = sum(mix.values())
            if total is not None and row_total != total:
                raise DecisionModelFigureError(f"{tier}: {who} covers {row_total}, not {total}")
            total = row_total
            left = 0
            for verdict in VERDICTS:
                width = mix[verdict]
                ax.barh(
                    y,
                    width,
                    left=left,
                    height=0.62,
                    color=VERDICT_COLORS[verdict],
                    edgecolor=SEGMENT_GAP,
                    linewidth=SEGMENT_GAP_WIDTH,
                )
                if width >= SEGMENT_LABEL_MIN:
                    ax.text(
                        left + width / 2,
                        y,
                        str(width),
                        ha="center",
                        va="center",
                        fontsize=FONT_SIZE_ANNOTATION,
                        color=_label_color(verdict),
                    )
                left += width
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([MODEL_LABELS[who] for who in reversed(rows)])
        ax.get_yticklabels()[-1].set_color(INK_SECONDARY)
        ax.set_title(TIER_LABELS[tier], loc="left", fontsize=11)
        ax.set_xlim(0, total)
        ax.grid(False)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[-1].set_xlabel("cases (first try, out of 350)")
    axes[-1].xaxis.set_major_locator(MultipleLocator(50))
    top = _header(
        fig,
        "Verdicts given, against the answer key",
        subtitle="Colour: the verdict each model gave; for the answer key, the correct verdict.",
        legend=True,
    )
    fig.tight_layout(rect=(0, 0, 1, top))
    _save(fig, path, dpi=dpi, fmt=fmt)


def render_wrong_against_constant(
    wrong: Mapping[str, Mapping[str, Mapping[str, int]]],
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    """Fig 2: wrong verdicts per tier for Jev, Sonnet and two constant answers.

    `wrong[tier]` maps a bar label to its wrong verdicts split by the verdict given. The first
    two bars are the models; the rest are constant answers.
    """
    fig, axes = plt.subplots(1, len(TIERS), figsize=(9.0, 4.9), sharey=True)
    largest = max(sum(split.values()) for tier in TIERS for split in wrong[tier].values())
    limit = 50 * (largest // 50 + 2)
    for ax, tier in zip(axes, TIERS, strict=True):
        labels = list(wrong[tier])
        for x, label in enumerate(labels):
            bottom = 0
            for verdict in VERDICTS:
                height = wrong[tier][label][verdict]
                ax.bar(
                    x,
                    height,
                    bottom=bottom,
                    width=0.62,
                    color=VERDICT_COLORS[verdict],
                    edgecolor=SEGMENT_GAP,
                    linewidth=SEGMENT_GAP_WIDTH,
                )
                bottom += height
            ax.text(
                x,
                bottom + limit * 0.015,
                str(bottom),
                ha="center",
                va="bottom",
                fontsize=FONT_SIZE_ANNOTATION + 1,
                color=INK,
            )
        ax.axvline(1.5, color=INK_MUTED, linewidth=0.6)
        ax.text(
            2.5,
            limit * 0.97,
            "constant answers",
            ha="center",
            va="top",
            fontsize=FONT_SIZE_ANNOTATION,
            color=INK_SECONDARY,
        )
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_title(TIER_LABELS[tier], loc="left", fontsize=11)
        ax.set_ylim(0, limit)
        ax.yaxis.set_major_locator(MultipleLocator(50))
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("wrong verdicts (first try, out of 350)")
    top = _header(
        fig,
        "Wrong verdicts, against giving every case the same answer",
        subtitle="The constant answers were added after the results: a descriptive comparison, "
        "not a test fixed in advance. Colour: the wrong verdict given.",
        legend=True,
    )
    fig.tight_layout(rect=(0, 0, 1, top))
    _save(fig, path, dpi=dpi, fmt=fmt)


def render_t3_cell_map(rows: Sequence[CellRow], path: Path, *, dpi: int, fmt: str) -> None:
    """Fig 3: per T3 design cell, each model's wrong verdicts, grouped by the map's reading."""
    positions: list[float] = []
    tick_labels: list[str] = []
    headers: list[tuple[float, str]] = []
    y = 0.0
    group_names = dict(CELL_GROUPS)
    current = None
    for row in rows:
        if row.group != current:
            if current is not None:
                y += 0.6
            headers.append((y, group_names[row.group]))
            y += 1.0
            current = row.group
        positions.append(y)
        tick_labels.append(f"{row.cell} ({row.cases})")
        y += 1.0
    height = 1.5 + 0.24 * y
    fig, axes = plt.subplots(1, 2, figsize=(9.5, height), sharey=True)
    limit = max(row.cases for row in rows)
    for ax, who, title in ((axes[0], "sonnet", "Sonnet"), (axes[1], "jev", "Jev")):
        for pos, row in zip(positions, rows, strict=True):
            split = getattr(row, who)
            left = 0
            for verdict in VERDICTS:
                width = split[verdict]
                ax.barh(
                    pos,
                    width,
                    left=left,
                    height=0.66,
                    color=VERDICT_COLORS[verdict],
                    edgecolor=SEGMENT_GAP,
                    linewidth=SEGMENT_GAP_WIDTH,
                )
                left += width
            ax.text(
                left + limit * 0.02,
                pos,
                str(left),
                ha="left",
                va="center",
                fontsize=FONT_SIZE_ANNOTATION,
                color=INK if left else INK_MUTED,
            )
        ax.set_xlim(0, limit * 1.15)
        ax.xaxis.set_major_locator(MultipleLocator(5))
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_xlabel("wrong verdicts in the cell (first try)")
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(positions)
    axes[0].set_yticklabels(tick_labels, fontsize=FONT_SIZE_ANNOTATION, family="monospace")
    axes[0].set_ylim(y - 0.4, -0.6)
    for header_y, text in headers:
        axes[0].text(
            -0.01,
            header_y,
            text,
            transform=axes[0].get_yaxis_transform(),
            ha="right",
            va="center",
            fontsize=FONT_SIZE_ANNOTATION + 1,
            fontweight="bold",
            color=INK,
        )
    top = _header(
        fig,
        "Tier 3: wrong verdicts per design cell",
        subtitle="First try. Cases per cell in brackets. Colour: the wrong verdict given.",
        legend=True,
    )
    fig.tight_layout(rect=(0, 0, 1, top))
    _save(fig, path, dpi=dpi, fmt=fmt)


def render_confidence(
    reliability: Sequence[ReliabilityPoint],
    curve: Sequence[CoveragePoint],
    labelled: Sequence[CoveragePoint],
    path: Path,
    *,
    target: float,
    dpi: int,
    fmt: str,
) -> None:
    """Fig 4: T3 stated confidence against share correct, and over-erasure as the bar rises."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.0, 5.0))

    left.plot(
        [0.5, 1.0], [0.5, 1.0], color=INK_MUTED, linewidth=0.8, label="confidence = share correct"
    )
    for point in reliability:
        share = point.correct / point.cases
        left.errorbar(
            point.mean_confidence,
            share,
            yerr=[[share - point.lower], [point.upper - share]],
            fmt="none",
            ecolor=INK_SECONDARY,
            elinewidth=1.0,
            capsize=3,
        )
        left.scatter(
            point.mean_confidence,
            share,
            s=40 + 0.6 * point.cases,
            color=COLOR_POINT,
            edgecolor="white",
            linewidth=1.5,
            zorder=3,
        )
        x, y, ha = RELIABILITY_LABEL_AT[point.bucket]
        left.text(
            x,
            y,
            f"{RELIABILITY_LABELS[point.bucket]}:\n{point.correct} of {point.cases} correct",
            ha=ha,
            va="top",
            fontsize=FONT_SIZE_ANNOTATION,
            color=INK,
        )
    left.legend(loc="upper left", frameon=False, fontsize=FONT_SIZE_ANNOTATION)
    left.set_xlim(0.5, 1.0)
    left.set_ylim(0.0, 1.0)
    left.xaxis.set_major_locator(MultipleLocator(0.1))
    left.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    left.set_xlabel("stated confidence (mean top probability in the band)")
    left.set_ylabel("share correct (95% interval)")
    left.set_title("Stated confidence against share correct", loc="left", fontsize=11)

    xs = [point.acted_on_share for point in curve]
    ys = [point.over_erasure_share for point in curve]
    right.plot(xs, ys, color=COLOR_POINT, linewidth=2.0, marker="o", markersize=3.5)
    right.axhline(target, color=INK_MUTED, linewidth=0.8)
    right.text(
        0.3,
        target + 0.01,
        f"{target:.0%} target",
        ha="left",
        va="bottom",
        fontsize=FONT_SIZE_CAPTION,
        color=INK_SECONDARY,
    )
    for point in labelled:
        dx, dy, ha = COVERAGE_LABEL_OFFSET.get(point.threshold, (8, 4, "left"))
        right.scatter(
            point.acted_on_share,
            point.over_erasure_share,
            s=64,
            color=COLOR_POINT,
            edgecolor="white",
            linewidth=1.5,
            zorder=3,
        )
        right.annotate(
            f"bar {point.threshold:.2f}: {point.over_erasures} of {point.acted_on}",
            (point.acted_on_share, point.over_erasure_share),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="bottom",
            fontsize=FONT_SIZE_ANNOTATION,
            color=INK,
        )
    right.annotate(
        "",
        xy=(0.36, 0.40),
        xytext=(0.72, 0.40),
        arrowprops={"arrowstyle": "->", "color": INK_SECONDARY, "linewidth": 1.0},
    )
    right.text(
        0.54,
        0.415,
        "raising the bar: fewer cases,\nmore of them over-erasures",
        ha="center",
        va="bottom",
        fontsize=FONT_SIZE_ANNOTATION,
        color=INK_SECONDARY,
    )
    right.set_xlim(0.0, 1.05)
    right.set_ylim(0.0, max(ys) + 0.08)
    right.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    right.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    right.set_xlabel("share of held-out cases acted on")
    right.set_ylabel("over-erasures among cases acted on")
    right.set_title("Acting only above a confidence bar", loc="left", fontsize=11)

    top = _header(
        fig,
        "Jev at tier 3: what its confidence is worth",
        subtitle="First try. Left: all 350 cases in the fixed confidence bands that hold any. "
        "Right: the 254 held-out cases; each point is a bar, labelled with over-erasures "
        "of cases acted on.",
    )
    fig.tight_layout(rect=(0, 0, 1, top))
    _save(fig, path, dpi=dpi, fmt=fmt)


# --- generation ---------------------------------------------------------------------------

FIGURE_FILES: dict[str, str] = {
    "verdict_mix": "verdict_mix_by_tier",
    "wrong_against_constant": "wrong_verdicts_against_constant",
    "cell_map": "t3_cell_map",
    "confidence": "confidence_t3",
}

RESULT_FILES: dict[str, str] = {
    "jev_t2": "jev/t2-live.json",
    "jev_t3": "jev/t3-live.json",
    "sonnet_t2": "t2-live.json",
    "sonnet_t3": "t3-live.json",
    "comparison": "jev/adjudication-comparison.json",
    "calibration": "jev/calibration.json",
}

CONSTANT_ANSWERS: tuple[str, ...] = ("erase", "retain")
CALIBRATION_TARGET = "5%"


def load_results(results_root: Path) -> dict[str, Any]:
    """The six committed results files the figures read, by role."""
    return {
        role: json.loads((results_root / name).read_text(encoding="utf-8"))
        for role, name in RESULT_FILES.items()
    }


def _check_model(report: Mapping[str, Any], model_id: str, tier: str) -> None:
    if report.get("model_id") != model_id or report.get("runner_id") != tier:
        raise DecisionModelFigureError(
            f"expected {model_id} {tier}, found {report.get('model_id')} {report.get('runner_id')}"
        )


def figure_data(results: Mapping[str, Any]) -> dict[str, Any]:
    """Everything the four figures draw, cross-checked against the comparison file."""
    comparison = results["comparison"]
    mixes: dict[str, dict[str, dict[str, int]]] = {}
    wrong: dict[str, dict[str, dict[str, int]]] = {}
    for tier in TIERS:
        jev, sonnet = results[f"jev_{tier}"], results[f"sonnet_{tier}"]
        _check_model(jev, JEV, tier)
        _check_model(sonnet, SONNET, tier)
        jev_cm, sonnet_cm = jev["confusion_matrix"], sonnet["confusion_matrix"]
        key_mix = answer_key_mix(jev_cm)
        if key_mix != answer_key_mix(sonnet_cm):
            raise DecisionModelFigureError(f"{tier}: the two runs disagree on the answer key")
        mixes[tier] = {
            ANSWER_KEY: key_mix,
            SONNET: verdict_mix(sonnet_cm),
            JEV: verdict_mix(jev_cm),
        }
        published = comparison["wrong_verdicts"][tier]
        expected_wrong = {
            JEV: published[JEV]["primary"]["all_cases"]["wrong"]["rate"]["numerator"],
            SONNET: published[SONNET]["all_cases"]["wrong"]["rate"]["numerator"],
        }
        split = {JEV: wrong_by_verdict_given(jev_cm), SONNET: wrong_by_verdict_given(sonnet_cm)}
        for model_id, counts in split.items():
            if sum(counts.values()) != expected_wrong[model_id]:
                raise DecisionModelFigureError(
                    f"{tier}: {model_id} wrong {sum(counts.values())} differs from the "
                    f"comparison file's {expected_wrong[model_id]}"
                )
        wrong[tier] = {
            "Jev": split[JEV],
            "Sonnet": split[SONNET],
            **{f"Always\n{v}": constant_wrong(key_mix, v) for v in CONSTANT_ANSWERS},
        }
    calibration = results["calibration"]
    curve = calibration["coverage_curve"]["test_part"]
    target = calibration["targets"][CALIBRATION_TARGET]["target"]
    return {
        "mixes": mixes,
        "wrong": wrong,
        "cell_map": comparison["t3_cell_map_descriptive"],
        "sonnet_by_cell": by_cell_counts(results["sonnet_t3"]),
        "jev_by_cell": by_cell_counts(results["jev_t3"]),
        "reliability": reliability_points(calibration["reliability"]["overall"]),
        "curve": coverage_points(curve),
        "labelled": [coverage_at(curve, t) for t in LABELLED_THRESHOLDS],
        "target": target,
    }


def generate_decision_model_figures(
    results: Mapping[str, Any],
    cell_keys: Mapping[str, str],
    out_dir: Path,
    *,
    dpi: int = 200,
    fmt: str = "png",
) -> list[Path]:
    """Render the four figures into out_dir; returns the paths written."""
    style.configure_matplotlib()
    data = figure_data(results)
    rows = cell_rows(
        data["cell_map"],
        sonnet_by_cell=data["sonnet_by_cell"],
        jev_by_cell=data["jev_by_cell"],
        cell_keys=cell_keys,
    )
    paths = {name: out_dir / f"{stem}.{fmt}" for name, stem in FIGURE_FILES.items()}
    render_verdict_mix(data["mixes"], paths["verdict_mix"], dpi=dpi, fmt=fmt)
    render_wrong_against_constant(data["wrong"], paths["wrong_against_constant"], dpi=dpi, fmt=fmt)
    render_t3_cell_map(rows, paths["cell_map"], dpi=dpi, fmt=fmt)
    render_confidence(
        data["reliability"],
        data["curve"],
        data["labelled"],
        paths["confidence"],
        target=data["target"],
        dpi=dpi,
        fmt=fmt,
    )
    return list(paths.values())

"""Individual chart renderers for report figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from report.adjudication_types import TierAdjudicationReportTables
from report.figures.style import (
    COLOR_BAR,
    COLOR_BAR_EDGE,
    COLOR_ERROR,
    COLOR_HEATMAP_CMAP,
    COLOR_OVER_ERASURE_ACCENT,
    FONT_SIZE_ANNOTATION,
    FONT_SIZE_CAPTION,
    HEATMAP_SIZE,
    REFERENCE_LINE_DETECTION,
    REFERENCE_LINE_FALSE_ALARM,
    SINGLE_CHART_SIZE,
    VARIANCE_SIZE,
    savefig_metadata,
)
from report.figures.types import (
    CONTEXT_TIERS,
    LANE_DISPLAY,
    TIER_DISPLAY,
    VERDICT_LANES_ORDERED,
    AdjudicationFigureData,
    GateFigureData,
    VerdictAgreementDistribution,
)
from report.types import GateReportTables, RateWithCI
from report.wilson import wilson_interval


def _save_figure(path: Path, *, dpi: int, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(
        path,
        dpi=dpi,
        format=fmt,
        bbox_inches="tight",
        pad_inches=0.08,
        metadata=savefig_metadata(),
    )
    plt.close()


def _truth_model_matrix(report: TierAdjudicationReportTables) -> np.ndarray:
    """Transpose scoring matrix to rows=ground truth, columns=model verdict."""
    matrix = report.confusion_matrix
    size = len(VERDICT_LANES_ORDERED)
    data = np.zeros((size, size), dtype=int)
    for row_idx, truth in enumerate(VERDICT_LANES_ORDERED):
        for col_idx, model in enumerate(VERDICT_LANES_ORDERED):
            data[row_idx, col_idx] = matrix[model][truth]
    return data


def render_over_erasure_by_tier(
    data: AdjudicationFigureData,
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    tiers = [tier for tier in CONTEXT_TIERS if tier in data.tier_reports]
    rates: list[RateWithCI] = [
        data.tier_reports[tier].primary_metrics.over_erasure for tier in tiers
    ]

    values = [item.rate.value or 0.0 for item in rates]
    lowers = []
    uppers = []
    for item in rates:
        if item.interval is None or item.interval.lower is None or item.interval.upper is None:
            interval = wilson_interval(item.rate)
        else:
            interval = item.interval
        lowers.append((item.rate.value or 0.0) - (interval.lower or 0.0))
        uppers.append((interval.upper or 0.0) - (item.rate.value or 0.0))

    labels = [TIER_DISPLAY[tier] for tier in tiers]
    x = np.arange(len(tiers))

    fig, ax = plt.subplots(figsize=SINGLE_CHART_SIZE)
    bars = ax.bar(
        x,
        values,
        color=COLOR_BAR,
        edgecolor=COLOR_BAR_EDGE,
        linewidth=0.8,
        yerr=[lowers, uppers],
        capsize=4,
        error_kw={"ecolor": COLOR_ERROR, "linewidth": 1.0},
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("over-erasure rate")
    ax.set_xlabel("context tier")
    ax.set_title("Over-erasure rate by context tier (Wilson 95% CI)")
    ax.set_ylim(0.0, max(max(values) * 1.25, 0.05) if values else 0.05)

    for bar, value in zip(bars, values, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{value:.1%}",
            ha="center",
            va="bottom",
            fontsize=FONT_SIZE_ANNOTATION,
        )

    _save_figure(path, dpi=dpi, fmt=fmt)


def render_confusion_heatmap(
    report: TierAdjudicationReportTables,
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    data = _truth_model_matrix(report)
    row_labels = [LANE_DISPLAY[lane] for lane in VERDICT_LANES_ORDERED]
    col_labels = [LANE_DISPLAY[lane] for lane in VERDICT_LANES_ORDERED]

    fig, ax = plt.subplots(figsize=HEATMAP_SIZE)
    im = ax.imshow(data, cmap=COLOR_HEATMAP_CMAP, aspect="auto")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(col_labels, rotation=30, ha="right")
    ax.set_yticklabels(row_labels)
    ax.set_xlabel("model verdict")
    ax.set_ylabel("ground-truth lane")
    tier_label = TIER_DISPLAY.get(report.tier, report.tier)
    ax.set_title(f"Confusion matrix — {tier_label} context tier")

    over_erasure_cells = {
        (row_idx, col_idx)
        for row_idx, truth in enumerate(VERDICT_LANES_ORDERED)
        for col_idx, model in enumerate(VERDICT_LANES_ORDERED)
        if model == "erase" and truth in {"retain", "escalate"}
    }

    for row_idx in range(data.shape[0]):
        for col_idx in range(data.shape[1]):
            count = int(data[row_idx, col_idx])
            text_color = "white" if count > data.max() * 0.55 else "black"
            ax.text(
                col_idx,
                row_idx,
                str(count),
                ha="center",
                va="center",
                color=text_color,
                fontsize=FONT_SIZE_ANNOTATION,
            )
            if (row_idx, col_idx) in over_erasure_cells and count > 0:
                ax.add_patch(
                    plt.Rectangle(
                        (col_idx - 0.5, row_idx - 0.5),
                        1,
                        1,
                        fill=False,
                        edgecolor=COLOR_OVER_ERASURE_ACCENT,
                        linewidth=2.5,
                    )
                )

    _save_figure(path, dpi=dpi, fmt=fmt)


def render_adversarial_detection_by_family(
    data: GateFigureData,
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    report: GateReportTables = data.report
    families = [row.family for row in report.per_family]
    values = [row.detection.rate.value or 0.0 for row in report.per_family]
    lowers = []
    uppers = []
    for row in report.per_family:
        interval = row.detection.interval or wilson_interval(row.detection.rate)
        value = row.detection.rate.value or 0.0
        lowers.append(value - (interval.lower or 0.0))
        uppers.append((interval.upper or 0.0) - value)

    x = np.arange(len(families))
    fig, ax = plt.subplots(figsize=SINGLE_CHART_SIZE)
    ax.bar(
        x,
        values,
        color=COLOR_BAR,
        edgecolor=COLOR_BAR_EDGE,
        linewidth=0.8,
        yerr=[lowers, uppers],
        capsize=4,
        error_kw={"ecolor": COLOR_ERROR, "linewidth": 1.0},
    )
    ax.set_xticks(x)
    ax.set_xticklabels(families, rotation=25, ha="right")
    ax.set_ylabel("detection rate")
    ax.set_xlabel("attack family")
    ax.set_title("Adversarial-gate detection rate by attack family (Wilson 95% CI)")
    ax.set_ylim(0.0, 1.05)

    detection_rate = report.detection.rate.value
    false_alarm_rate = report.false_alarm.rate.value
    if detection_rate is not None:
        ax.axhline(
            detection_rate,
            color=REFERENCE_LINE_DETECTION,
            linestyle="--",
            linewidth=1.2,
            label=f"overall detection rate ({detection_rate:.1%})",
        )
    if false_alarm_rate is not None:
        ax.axhline(
            false_alarm_rate,
            color=REFERENCE_LINE_FALSE_ALARM,
            linestyle=":",
            linewidth=1.2,
            label=f"overall false-alarm rate ({false_alarm_rate:.1%})",
        )
    ax.legend(loc="lower right", frameon=True)

    _save_figure(path, dpi=dpi, fmt=fmt)


def render_verdict_variance_by_tier(
    variance_by_tier: dict[str, VerdictAgreementDistribution],
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    tiers = [tier for tier in CONTEXT_TIERS if tier in variance_by_tier]
    buckets = ["5/5 unanimous", "4/5", "3/5", "split"]
    bucket_matrix = []
    for tier in tiers:
        distribution = variance_by_tier[tier]
        total = distribution.total_cases or 1
        bucket_matrix.append(
            [distribution.bucket_counts[bucket] / total for bucket in buckets]
        )

    data = np.array(bucket_matrix)
    x = np.arange(len(tiers))
    width = 0.18
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]

    fig, ax = plt.subplots(figsize=VARIANCE_SIZE)
    for bucket_idx, bucket in enumerate(buckets):
        offsets = x + (bucket_idx - 1.5) * width
        ax.bar(
            offsets,
            data[:, bucket_idx],
            width=width,
            label=bucket,
            color=colors[bucket_idx],
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels([TIER_DISPLAY[tier] for tier in tiers])
    ax.set_ylabel("share of cases")
    ax.set_xlabel("context tier")
    ax.set_title("Verdict variance by context tier (N=5 samples per case)")
    ax.set_ylim(0.0, 1.05)
    ax.legend(title="sample agreement", loc="upper right", frameon=True)
    fig.text(
        0.01,
        0.01,
        "Note: the deterministic core's variance is zero by construction.",
        fontsize=FONT_SIZE_CAPTION,
        ha="left",
        va="bottom",
    )

    _save_figure(path, dpi=dpi, fmt=fmt)

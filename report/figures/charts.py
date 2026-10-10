"""Individual chart renderers for report figures."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.ticker import PercentFormatter

from report.adjudication_types import TierAdjudicationReportTables
from report.figures.layout import (
    annotation_fits,
    annotation_y,
    heatmap_text_color,
    horizontal_bar_annotation_x,
    rate_axis_ticks,
    rate_axis_upper_limit,
)
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
    ADJUDICATION_SETTINGS,
    FAMILY_DISPLAY,
    FIVE_SAMPLE_AGREEMENT_BUCKETS,
    LANE_DISPLAY,
    THREE_SAMPLE_AGREEMENT_BUCKETS,
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
    tiers = [tier for tier in ADJUDICATION_SETTINGS if tier in data.tier_reports]
    rates: list[RateWithCI] = [
        data.tier_reports[tier].primary_metrics.over_erasure for tier in tiers
    ]

    values = [item.rate.value or 0.0 for item in rates]
    lowers = []
    uppers = []
    upper_bounds = []
    for item in rates:
        if item.interval is None or item.interval.lower is None or item.interval.upper is None:
            interval = wilson_interval(item.rate)
        else:
            interval = item.interval
        value = item.rate.value or 0.0
        upper_bound = interval.upper or 0.0
        lowers.append(value - (interval.lower or 0.0))
        uppers.append(upper_bound - value)
        upper_bounds.append(upper_bound)

    labels = [TIER_DISPLAY[tier] for tier in tiers]
    x = np.arange(len(tiers))
    limit = rate_axis_upper_limit(max(upper_bounds, default=0.0))

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
    ax.set_xlabel("setting")
    ax.set_title("Over-erasure rate by setting (Wilson 95% CI)")
    ax.set_ylim(0.0, limit)
    ax.set_yticks(rate_axis_ticks(limit))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))

    for bar, value, upper in zip(bars, values, uppers, strict=True):
        baseline = annotation_y(value, upper)
        if not annotation_fits(baseline, limit):
            raise ValueError(
                f"over-erasure annotation baseline {baseline:.4f} collides with "
                f"axis limit {limit:.4f}; surface instead of clipping"
            )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            baseline,
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
            cell_rgba = im.cmap(im.norm(count))
            text_color = heatmap_text_color(cell_rgba)
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
    labels = [FAMILY_DISPLAY.get(row.family, row.family) for row in report.per_family]
    values = [row.detection.rate.value or 0.0 for row in report.per_family]
    counts = [
        (row.detection.rate.numerator, row.detection.rate.denominator) for row in report.per_family
    ]
    lowers = []
    uppers = []
    upper_bounds = []
    for row in report.per_family:
        interval = row.detection.interval or wilson_interval(row.detection.rate)
        value = row.detection.rate.value or 0.0
        upper_bound = interval.upper or 0.0
        lowers.append(value - (interval.lower or 0.0))
        uppers.append(upper_bound - value)
        upper_bounds.append(upper_bound)

    limit = rate_axis_upper_limit(max(upper_bounds, default=0.0))
    y = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=SINGLE_CHART_SIZE)
    ax.barh(
        y,
        values,
        color=COLOR_BAR,
        edgecolor=COLOR_BAR_EDGE,
        linewidth=0.8,
        xerr=[lowers, uppers],
        capsize=4,
        error_kw={"ecolor": COLOR_ERROR, "linewidth": 1.0},
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("detection rate")
    ax.set_ylabel("attack family")
    ax.set_title("Adversarial-gate detection rate by attack family (Wilson 95% CI)")
    ax.set_xlim(0.0, limit)
    ax.set_xticks(rate_axis_ticks(limit, step=0.25))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))

    bar_rgba = to_rgba(COLOR_BAR)
    for row_pos, value, upper, (numerator, denominator) in zip(
        y, values, uppers, counts, strict=True
    ):
        text_x, placement = horizontal_bar_annotation_x(value, upper, limit)
        ax.text(
            text_x,
            row_pos,
            f"{numerator}/{denominator} ({value:.1%})",
            ha="left",
            va="center",
            color=heatmap_text_color(bar_rgba) if placement == "inside" else COLOR_ERROR,
            fontsize=FONT_SIZE_ANNOTATION,
        )

    detection_rate = report.detection.rate.value
    false_alarm_rate = report.false_alarm.rate.value
    if detection_rate is not None:
        ax.axvline(
            detection_rate,
            color=REFERENCE_LINE_DETECTION,
            linestyle="--",
            linewidth=1.2,
            label=f"overall detection rate ({detection_rate:.1%})",
        )
    if false_alarm_rate is not None:
        ax.axvline(
            false_alarm_rate,
            color=REFERENCE_LINE_FALSE_ALARM,
            linestyle=":",
            linewidth=1.2,
            label=f"overall false-alarm rate ({false_alarm_rate:.1%})",
        )
    handles, legend_labels = ax.get_legend_handles_labels()
    if handles:
        fig.legend(
            handles,
            legend_labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.0),
            ncol=2,
            frameon=False,
        )

    _save_figure(path, dpi=dpi, fmt=fmt)


UNANIMOUS_BUCKETS = frozenset({"3/3 unanimous", "5/5 unanimous"})
AGREEMENT_BUCKET_COLORS = {
    "5/5 unanimous": "#4C72B0",
    "3/3 unanimous": "#4C72B0",
    "4/5": "#55A868",
    "2/3": "#55A868",
    "3/5": "#C44E52",
    "split": "#C44E52",
}


def _agreement_bucket_labels(
    variance_by_tier: dict[str, VerdictAgreementDistribution],
) -> list[str]:
    first = next(iter(variance_by_tier.values()), None)
    if first is None:
        return list(THREE_SAMPLE_AGREEMENT_BUCKETS)
    keys = first.bucket_counts
    if "5/5 unanimous" in keys:
        return list(FIVE_SAMPLE_AGREEMENT_BUCKETS)
    return list(THREE_SAMPLE_AGREEMENT_BUCKETS)


def unstable_agreement_buckets(buckets: list[str]) -> list[str]:
    """Agreement buckets other than the unanimous majority share."""
    return [bucket for bucket in buckets if bucket not in UNANIMOUS_BUCKETS]


def _share_matrix(
    variance_by_tier: dict[str, VerdictAgreementDistribution],
    settings: list[str],
    buckets: list[str],
) -> np.ndarray:
    rows = []
    for setting in settings:
        distribution = variance_by_tier[setting]
        total = distribution.total_cases or 1
        rows.append([distribution.bucket_counts.get(bucket, 0) / total for bucket in buckets])
    if not buckets:
        return np.zeros((len(settings), 0))
    return np.array(rows)


def _plot_grouped_agreement_bars(
    ax,
    x: np.ndarray,
    data: np.ndarray,
    buckets: list[str],
    *,
    width: float,
) -> None:
    midpoint = (len(buckets) - 1) / 2 if buckets else 0.0
    for bucket_idx, bucket in enumerate(buckets):
        offsets = x + (bucket_idx - midpoint) * width
        ax.bar(
            offsets,
            data[:, bucket_idx],
            width=width,
            label=bucket,
            color=AGREEMENT_BUCKET_COLORS.get(bucket, COLOR_BAR),
            edgecolor="white",
            linewidth=0.5,
        )


def render_verdict_variance_by_tier(
    variance_by_tier: dict[str, VerdictAgreementDistribution],
    path: Path,
    *,
    dpi: int,
    fmt: str,
) -> None:
    """Two-panel variance: unanimous on top (0–100%), 2/3 and split below (zoomed)."""
    tiers = [tier for tier in ADJUDICATION_SETTINGS if tier in variance_by_tier]
    buckets = _agreement_bucket_labels(variance_by_tier)
    sample_count = 5 if buckets == list(FIVE_SAMPLE_AGREEMENT_BUCKETS) else 3
    unanimous_label = "5/5 unanimous" if sample_count == 5 else "3/3 unanimous"
    plotted = unstable_agreement_buckets(buckets)
    unanimous = _share_matrix(variance_by_tier, tiers, [unanimous_label])
    unstable = _share_matrix(variance_by_tier, tiers, plotted)
    x = np.arange(len(tiers))
    unstable_width = 0.32 if len(plotted) <= 2 else 0.22

    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        sharex=True,
        figsize=VARIANCE_SIZE,
        gridspec_kw={"height_ratios": [1, 1], "hspace": 0.22},
    )
    _plot_grouped_agreement_bars(ax_top, x, unanimous, [unanimous_label], width=0.55)
    ax_top.set_ylabel("share of cases")
    ax_top.set_title(unanimous_label)
    ax_top.set_ylim(0.0, 1.0)
    ax_top.set_yticks(rate_axis_ticks(1.0, step=0.20))
    ax_top.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))

    _plot_grouped_agreement_bars(ax_bottom, x, unstable, plotted, width=unstable_width)
    ax_bottom.set_xticks(x)
    ax_bottom.set_xticklabels([TIER_DISPLAY[tier] for tier in tiers])
    ax_bottom.set_ylabel("share of cases")
    ax_bottom.set_xlabel("setting")
    ax_bottom.set_title(" / ".join(plotted) if plotted else "unstable")
    limit = rate_axis_upper_limit(float(unstable.max()) if unstable.size else 0.0)
    ax_bottom.set_ylim(0.0, limit)
    ax_bottom.set_yticks(rate_axis_ticks(limit, step=0.05))
    ax_bottom.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    if plotted:
        # Upper left, one row: the tallest unstable bar is on the right (autonomous 2/3).
        ax_bottom.legend(
            title="sample agreement",
            loc="upper left",
            ncol=len(plotted),
            frameon=True,
            framealpha=1.0,
        )

    fig.suptitle(f"Verdict variance by setting (N={sample_count} samples per case)")
    fig.subplots_adjust(bottom=0.14, top=0.90)
    fig.text(
        0.01,
        0.01,
        "The deterministic core's variance is zero by construction.",
        fontsize=FONT_SIZE_CAPTION,
        ha="left",
        va="bottom",
    )
    _save_figure(path, dpi=dpi, fmt=fmt)

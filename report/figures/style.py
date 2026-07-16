"""Pinned matplotlib style for deterministic report figures."""

from __future__ import annotations

import matplotlib as mpl

FIGURE_DPI_DEFAULT = 200

# Figure dimensions (inches)
SINGLE_CHART_SIZE = (8.0, 5.0)
HEATMAP_SIZE = (6.5, 5.5)
VARIANCE_SIZE = (8.0, 5.5)

FONT_SIZE_TITLE = 13
FONT_SIZE_LABEL = 11
FONT_SIZE_TICK = 10
FONT_SIZE_ANNOTATION = 9
FONT_SIZE_CAPTION = 9

COLOR_BAR = "#4C72B0"
COLOR_BAR_EDGE = "#2F4F7A"
COLOR_ERROR = "#1F1F1F"
COLOR_GRID = "#D0D0D0"
COLOR_HEATMAP_CMAP = "Blues"
COLOR_OVER_ERASURE_ACCENT = "#C0392B"

REFERENCE_LINE_DETECTION = "#2E7D32"
REFERENCE_LINE_FALSE_ALARM = "#C0392B"


def configure_matplotlib() -> None:
    """Apply project style; must run before pyplot is imported."""
    mpl.use("Agg")
    mpl.rcParams.update(
        {
            "figure.dpi": FIGURE_DPI_DEFAULT,
            "savefig.dpi": FIGURE_DPI_DEFAULT,
            "font.size": FONT_SIZE_TICK,
            "axes.titlesize": FONT_SIZE_TITLE,
            "axes.labelsize": FONT_SIZE_LABEL,
            "xtick.labelsize": FONT_SIZE_TICK,
            "ytick.labelsize": FONT_SIZE_TICK,
            "legend.fontsize": FONT_SIZE_TICK,
            "axes.grid": True,
            "grid.color": COLOR_GRID,
            "grid.linestyle": "-",
            "grid.linewidth": 0.5,
            "grid.alpha": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "figure.autolayout": False,
        }
    )


def savefig_metadata() -> dict[str, str]:
    """Strip run-specific metadata from saved figure files."""
    return {
        "Software": "",
        "Date": "",
    }

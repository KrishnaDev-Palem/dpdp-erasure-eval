"""Pure layout rules for report figures.

Axis limits, tick positions, annotation placement, and heatmap text color are
computed here as pure functions of the plotted data so they are unit-testable
without rendering.
"""

from __future__ import annotations

import math

AXIS_LIMIT_STEP = 0.05
AXIS_LIMIT_MARGIN = 0.02
ANNOTATION_OFFSET = 0.01
ANNOTATION_CLEARANCE = 0.01
HEATMAP_LUMINANCE_THRESHOLD = 0.5

# Absorbs float noise such as 0.13 + 0.02 == 0.15000000000000002 so that values
# landing exactly on a step multiple do not round up an extra step.
_STEP_TOLERANCE = 1e-9


def rate_axis_upper_limit(
    largest_upper_bound: float,
    *,
    margin: float = AXIS_LIMIT_MARGIN,
    step: float = AXIS_LIMIT_STEP,
) -> float:
    """Smallest multiple of step that is >= largest_upper_bound + margin."""
    target = largest_upper_bound + margin
    multiples = math.ceil(target / step - _STEP_TOLERANCE)
    return round(multiples * step, 10)


def rate_axis_ticks(limit: float, *, step: float = AXIS_LIMIT_STEP) -> list[float]:
    """Tick positions at step intervals from 0 up to and including limit."""
    count = math.floor(limit / step + _STEP_TOLERANCE)
    return [round(index * step, 10) for index in range(count + 1)]


def annotation_y(value: float, upper_error: float, *, offset: float = ANNOTATION_OFFSET) -> float:
    """Baseline for a rate annotation: a fixed offset above the whisker cap."""
    return value + upper_error + offset


def annotation_fits(
    baseline: float,
    limit: float,
    *,
    clearance: float = ANNOTATION_CLEARANCE,
) -> bool:
    """Whether an annotation baseline leaves clearance below the axis limit."""
    return baseline + clearance <= limit + _STEP_TOLERANCE


BAR_ANNOTATION_INSIDE_MIN_FRACTION = 0.2
BAR_ANNOTATION_PAD_FRACTION = 0.02


def horizontal_bar_annotation_x(
    value: float,
    upper_error: float,
    limit: float,
    *,
    inside_min_fraction: float = BAR_ANNOTATION_INSIDE_MIN_FRACTION,
    pad_fraction: float = BAR_ANNOTATION_PAD_FRACTION,
) -> tuple[float, str]:
    """X position and placement for a horizontal-bar count annotation.

    Returns (x, placement) where placement is "inside" when the bar is long
    enough to hold the text near its base, or "outside" to sit past the
    whisker cap of a short bar.
    """
    pad = pad_fraction * limit
    if value >= inside_min_fraction * limit:
        return pad, "inside"
    return value + upper_error + pad, "outside"


def heatmap_text_color(
    rgb: tuple[float, ...],
    *,
    threshold: float = HEATMAP_LUMINANCE_THRESHOLD,
) -> str:
    """Annotation color readable against a heatmap cell color.

    Uses relative luminance of the cell color: light text on dark cells,
    dark text on light cells.
    """
    red, green, blue = rgb[0], rgb[1], rgb[2]
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "white" if luminance < threshold else "black"

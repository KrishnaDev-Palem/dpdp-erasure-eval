"""Orchestrate offline figure generation from scored evaluation inputs."""

from __future__ import annotations

from pathlib import Path

from report.figures import style
from report.figures.charts import (
    render_adversarial_detection_by_family,
    render_confusion_heatmap,
    render_over_erasure_by_tier,
    render_verdict_variance_by_tier,
)
from report.figures.types import CONTEXT_TIERS, FigureGenerationResult, FigureInputs

FIGURE_NAMES = {
    "over_erasure": "over_erasure_by_tier",
    "confusion_t1": "confusion_t1",
    "confusion_t2": "confusion_t2",
    "confusion_t3": "confusion_t3",
    "adversarial_detection": "adversarial_detection_by_family",
    "verdict_variance": "verdict_variance_by_tier",
}


def generate_figures(
    inputs: FigureInputs,
    out_dir: Path,
    *,
    dpi: int = style.FIGURE_DPI_DEFAULT,
    fmt: str = "png",
) -> FigureGenerationResult:
    """Render all available figures from scored inputs into out_dir."""
    style.configure_matplotlib()
    out_dir.mkdir(parents=True, exist_ok=True)
    result = FigureGenerationResult()

    if inputs.adjudication is not None:
        adjudication = inputs.adjudication
        _write(
            result,
            out_dir / f"{FIGURE_NAMES['over_erasure']}.{fmt}",
            lambda path: render_over_erasure_by_tier(adjudication, path, dpi=dpi, fmt=fmt),
        )
        for tier in CONTEXT_TIERS:
            if tier in adjudication.tier_reports:
                _write(
                    result,
                    out_dir / f"{FIGURE_NAMES[f'confusion_{tier}']}.{fmt}",
                    lambda path, tier=tier: render_confusion_heatmap(
                        adjudication.tier_reports[tier],
                        path,
                        dpi=dpi,
                        fmt=fmt,
                    ),
                )
        _write(
            result,
            out_dir / f"{FIGURE_NAMES['verdict_variance']}.{fmt}",
            lambda path: render_verdict_variance_by_tier(
                adjudication.variance_by_tier,
                path,
                dpi=dpi,
                fmt=fmt,
            ),
        )
    else:
        for name in (
            "over_erasure_by_tier",
            "confusion_t1",
            "confusion_t2",
            "confusion_t3",
            "verdict_variance_by_tier",
        ):
            result.skipped.append((name, "adjudication scored results missing"))

    if inputs.gate is not None:
        _write(
            result,
            out_dir / f"{FIGURE_NAMES['adversarial_detection']}.{fmt}",
            lambda path: render_adversarial_detection_by_family(
                inputs.gate,
                path,
                dpi=dpi,
                fmt=fmt,
            ),
        )
    else:
        result.skipped.append(
            ("adversarial_detection_by_family", "adversarial-gate scored results missing")
        )

    return result


def _write(result: FigureGenerationResult, path: Path, render_fn) -> None:
    render_fn(path)
    result.written.append(path.name)

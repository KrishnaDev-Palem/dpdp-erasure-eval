"""T3 rule-augmented tier sweep runner."""

from __future__ import annotations

from pathlib import Path

from core.context import build_t3
from core.model.seam import ModelSeam
from runners.spine import run_tier_sweep
from runners.types import SweepConfig, TierSweepResult


def run_t3_sweep(
    *,
    seam: ModelSeam,
    config: SweepConfig | None = None,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
    sample_indices: list[int] | None = None,
) -> TierSweepResult:
    return run_tier_sweep(
        tier="t3",
        seam=seam,
        config=config,
        export_dir=export_dir,
        cache_root=cache_root,
        builder=build_t3,
        sample_indices=sample_indices,
    )

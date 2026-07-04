"""Adversarial-gate sweep orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.cache.store import CacheStore
from core.model.seam import ModelSeam, load_model_config
from core.scoring.adversarial import score_adversarial
from core.types import AdversarialSeedCase, ClassifierResult
from runners.adversarial_gate.cache import classify_with_cache
from runners.adversarial_gate.slice_loader import load_extended_slice
from runners.adversarial_gate.types import (
    GATE_RUNNER_ID,
    GateSampleRollup,
    GateSweepConfig,
    GateSweepResult,
)
from runners.adversarial_gate.variance import compute_gate_variance_summary


def _resolve_config(
    config: GateSweepConfig | None,
    slice_path: Path | None,
    cache_root: Path | None,
) -> GateSweepConfig:
    if config is not None:
        return config
    env = load_model_config()
    return GateSweepConfig(
        runner_id=GATE_RUNNER_ID,
        model_id=env.model_id,
        cache_mode=env.cache_mode,
        slice_path=slice_path,
        cache_root=cache_root,
    )


def run_adversarial_gate_sweep(
    *,
    seam: ModelSeam,
    config: GateSweepConfig | None = None,
    slice_path: Path | None = None,
    cache_root: Path | None = None,
) -> GateSweepResult:
    """Execute a full adversarial-gate sweep over the extended slice."""
    resolved = _resolve_config(config, slice_path, cache_root)
    slice_file = resolved.slice_path or Path("fixtures/adversarial_slice/cases.yaml")
    cache_path = resolved.cache_root or Path("cache")

    slice_result = load_extended_slice(
        slice_file,
        verify_seeds=resolved.verify_export_seeds,
    )
    cases = slice_result.cases

    store = CacheStore(root=cache_path, cache_mode=resolved.cache_mode)
    started_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    sample_rollups: list[GateSampleRollup] = []
    for sample_index in resolved.sample_indices:
        pairs: list[tuple[ClassifierResult, AdversarialSeedCase]] = []
        for case in cases:
            try:
                result = classify_with_cache(
                    case=case,
                    sample_index=sample_index,
                    model_id=resolved.model_id,
                    store=store,
                    seam=seam,
                )
            except Exception as exc:
                if "Invalid classifier outcome" in str(exc):
                    raise ValueError(
                        f"Invalid outcome for case_id={case.case_id}, sample_index={sample_index}"
                    ) from exc
                raise
            if result.outcome not in {"clean", "adversarial"}:
                raise ValueError(
                    f"Invalid outcome for case_id={case.case_id}, sample_index={sample_index}"
                )
            pairs.append((result, case))

        scoring = score_adversarial(pairs)
        sample_rollups.append(
            GateSampleRollup(
                sample_index=sample_index,
                scoring=scoring,
                total_cases=len(cases),
                scored_pairs=len(pairs),
            )
        )

    finished_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return GateSweepResult(
        runner_id=GATE_RUNNER_ID,
        model_id=resolved.model_id,
        cache_mode=resolved.cache_mode,
        slice_case_count=len(cases),
        samples=sample_rollups,
        variance=compute_gate_variance_summary(sample_rollups),
        started_at=started_at,
        finished_at=finished_at,
    )

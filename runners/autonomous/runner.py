"""Autonomous adjudication sweep orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.cache.store import CacheStore
from core.context.tiers import build_t1
from core.export.loader import load_export
from core.model.seam import ModelSeam
from core.scoring.adjudication import score_adjudication, score_adjudication_grouped
from core.tools.registry import build_retrieval_tool_registry
from core.types import LabeledLocation
from runners.autonomous.cache import resolve_autonomous_entry
from runners.autonomous.types import (
    AUTONOMOUS_RUNNER_ID,
    AutonomousSweepConfig,
    AutonomousSweepResult,
)
from runners.pairing import pair_subject_verdicts
from runners.types import SampleRollup
from runners.variance import compute_variance_summary


def _resolve_config(
    config: AutonomousSweepConfig | None,
    export_dir: Path | None,
    cache_root: Path | None,
    sample_indices: list[int] | None = None,
) -> AutonomousSweepConfig:
    if config is not None:
        if sample_indices is None:
            return config
        return config.model_copy(update={"sample_indices": list(sample_indices)})
    resolved = AutonomousSweepConfig.from_env(export_dir=export_dir, cache_root=cache_root)
    if sample_indices is None:
        return resolved
    return resolved.model_copy(update={"sample_indices": list(sample_indices)})


def run_autonomous_sweep(
    *,
    seam: ModelSeam,
    config: AutonomousSweepConfig | None = None,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
    sample_indices: list[int] | None = None,
) -> AutonomousSweepResult:
    """Execute a full autonomous sweep over all export subjects and configured sample indices."""
    resolved = _resolve_config(config, export_dir, cache_root, sample_indices)
    export_path = resolved.export_dir or Path("export")
    cache_path = resolved.cache_root or Path("cache")

    bundle = load_export(export_path)
    manifest = bundle.verify_provenance()
    locations_by_id: dict[str, LabeledLocation] = {
        location.location_id: location
        for subject in bundle.subjects
        for location in subject.locations
    }

    store = CacheStore(root=cache_path, cache_mode=resolved.cache_mode)
    tool_registry = build_retrieval_tool_registry(bundle)
    started_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    sample_rollups: list[SampleRollup] = []
    for sample_index in resolved.sample_indices:
        all_pairs: list[tuple[Any, Any]] = []
        for subject in bundle.subjects:
            context = build_t1(subject.request, subject)
            context_location_ids = [location["location_id"] for location in context.locations]
            export_location_ids = [location.location_id for location in subject.locations]
            pairing_location_ids = (
                context_location_ids if context_location_ids else export_location_ids
            )
            if not pairing_location_ids:
                continue

            session = resolve_autonomous_entry(
                context=context,
                subject_id=subject.subject_id,
                sample_index=sample_index,
                model_id=resolved.model_id,
                store=store,
                seam=seam,
                tool_registry=tool_registry,
            )
            pairs = pair_subject_verdicts(
                subject_id=subject.subject_id,
                sample_index=sample_index,
                locations=subject.locations,
                pairing_location_ids=pairing_location_ids,
                raw_verdicts=session.raw_verdicts,
            )
            all_pairs.extend(pairs)

        scoring = score_adjudication(all_pairs)
        sample_rollups.append(
            SampleRollup(
                sample_index=sample_index,
                scoring=scoring,
                total_subjects=len(bundle.subjects),
                scored_location_pairs=scoring.total_cases,
                grouped=score_adjudication_grouped(all_pairs, locations_by_id),
            )
        )

    finished_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return AutonomousSweepResult(
        runner_id=AUTONOMOUS_RUNNER_ID,
        model_id=resolved.model_id,
        cache_mode=resolved.cache_mode,
        export_agent_sha=manifest.agent_commit_sha,
        samples=sample_rollups,
        variance=compute_variance_summary(sample_rollups),
        started_at=started_at,
        finished_at=finished_at,
    )

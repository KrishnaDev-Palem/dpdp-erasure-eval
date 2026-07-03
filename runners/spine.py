"""Shared orchestration spine for context-tier adjudication sweeps."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.cache.store import CacheStore, make_cache_key
from core.context.tiers import build_t1, build_t2, build_t3
from core.export.loader import ExportBundle, load_export
from core.model.seam import ModelSeam, load_model_config
from core.scoring.adjudication import score_adjudication
from core.types import ContextBundle, RulesCorpus, Tier
from runners.pairing import pair_subject_verdicts
from runners.types import SAMPLE_INDICES, SampleRollup, SweepConfig, TierSweepResult
from runners.variance import compute_variance_summary

ContextBuilder = Callable[..., ContextBundle]

_BUILDERS: dict[Tier, ContextBuilder] = {
    "t1": build_t1,
    "t2": build_t2,
    "t3": build_t3,
}


def _resolve_config(
    tier: Tier,
    config: SweepConfig | None,
    export_dir: Path | None,
    cache_root: Path | None,
) -> SweepConfig:
    if config is not None:
        return config
    env = load_model_config()
    return SweepConfig(
        tier=tier,
        runner_id=tier,
        model_id=env.model_id,
        cache_mode=env.cache_mode,
        sample_indices=list(SAMPLE_INDICES),
        export_dir=export_dir,
        cache_root=cache_root,
    )


def _build_context(
    *,
    tier: Tier,
    subject,
    rules: RulesCorpus | None,
) -> ContextBundle:
    builder = _BUILDERS[tier]
    if tier == "t3":
        if rules is None:
            raise ValueError("rules corpus required for T3 sweep")
        return builder(subject.request, subject, rules)
    return builder(subject.request, subject)


def run_tier_sweep(
    *,
    tier: Tier,
    seam: ModelSeam,
    config: SweepConfig | None = None,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
    builder: ContextBuilder | None = None,
) -> TierSweepResult:
    """Execute a full tier sweep over all export subjects and five sample indices."""
    resolved = _resolve_config(tier, config, export_dir, cache_root)
    export_path = resolved.export_dir or Path("export")
    cache_path = resolved.cache_root or Path("cache")

    bundle: ExportBundle = load_export(export_path)
    manifest = bundle.verify_provenance()

    store = CacheStore(root=cache_path, cache_mode=resolved.cache_mode)
    started_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    sample_rollups: list[SampleRollup] = []
    for sample_index in resolved.sample_indices:
        all_pairs: list[tuple[Any, Any]] = []
        for subject in bundle.subjects:
            context = (
                _build_context(tier=tier, subject=subject, rules=bundle.rules)
                if builder is None
                else (
                    builder(subject.request, subject, bundle.rules)
                    if tier == "t3"
                    else builder(subject.request, subject)
                )
            )
            context_location_ids = [location["location_id"] for location in context.locations]
            export_location_ids = [location.location_id for location in subject.locations]
            pairing_location_ids = (
                context_location_ids if context_location_ids else export_location_ids
            )
            if not pairing_location_ids:
                continue

            key = make_cache_key(
                context=context,
                model_id=resolved.model_id,
                runner_id=resolved.runner_id,
                case_id=subject.subject_id,
                sample_index=sample_index,
            )
            entry = store.get_or_refresh(key=key, context=context, seam=seam)
            pairs = pair_subject_verdicts(
                subject_id=subject.subject_id,
                sample_index=sample_index,
                locations=subject.locations,
                pairing_location_ids=pairing_location_ids,
                raw_verdicts=entry.raw_response.get("verdicts", []),
            )
            all_pairs.extend(pairs)

        scoring = score_adjudication(all_pairs)
        sample_rollups.append(
            SampleRollup(
                sample_index=sample_index,
                scoring=scoring,
                total_subjects=len(bundle.subjects),
                scored_location_pairs=scoring.total_cases,
            )
        )

    finished_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return TierSweepResult(
        tier=tier,
        runner_id=resolved.runner_id,
        model_id=resolved.model_id,
        cache_mode=resolved.cache_mode,
        export_agent_sha=manifest.agent_commit_sha,
        samples=sample_rollups,
        variance=compute_variance_summary(sample_rollups),
        started_at=started_at,
        finished_at=finished_at,
    )

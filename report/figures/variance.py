"""Derive per-case sample agreement distributions from committed cache entries."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path

from core.cache.store import CacheStore, make_cache_key
from core.context.tiers import build_t1, build_t2, build_t3
from core.export.loader import ExportBundle, load_export
from core.types import ContextBundle, RulesCorpus, Tier, Verdict
from report.figures.types import (
    AGREEMENT_BUCKETS,
    CONTEXT_TIERS,
    VerdictAgreementDistribution,
)

ContextBuilder = Callable[..., ContextBundle]

_BUILDERS: dict[Tier, ContextBuilder] = {
    "t1": build_t1,
    "t2": build_t2,
    "t3": build_t3,
}


def _build_context(
    *,
    tier: Tier,
    subject,
    rules: RulesCorpus | None,
) -> ContextBundle:
    builder = _BUILDERS[tier]
    if tier == "t3":
        if rules is None:
            raise ValueError("rules corpus required for T3 context")
        return builder(subject.request, subject, rules)
    return builder(subject.request, subject)


def _pairing_location_ids(subject, context: ContextBundle) -> list[str]:
    context_location_ids = [str(location["location_id"]) for location in context.locations]
    export_location_ids = [location.location_id for location in subject.locations]
    return context_location_ids if context_location_ids else export_location_ids


def _extract_verdict(raw_verdicts: list[dict], location_id: str) -> Verdict:
    for item in raw_verdicts:
        if str(item["location_id"]) == location_id:
            verdict = item.get("verdict")
            if verdict in {"erase", "retain", "escalate"}:
                return verdict
            raise ValueError(f"invalid verdict {verdict!r} for location {location_id}")
    raise ValueError(f"missing verdict for location {location_id}")


def _agreement_bucket(verdicts: list[Verdict]) -> str:
    counts = Counter(verdicts)
    max_count = max(counts.values())
    if max_count == 5:
        return "5/5 unanimous"
    if max_count == 4:
        return "4/5"
    if max_count == 3:
        return "3/5"
    return "split"


def compute_verdict_agreement_by_tier(
    *,
    export_dir: Path,
    cache_root: Path,
    model_id: str,
    sample_indices: list[int] | None = None,
) -> dict[str, VerdictAgreementDistribution]:
    """Compute per-tier verdict agreement buckets from offline cache reads."""
    indices = sample_indices if sample_indices is not None else [0, 1, 2, 3, 4]
    bundle: ExportBundle = load_export(export_dir)
    store = CacheStore(root=cache_root, cache_mode="offline")
    distributions: dict[str, VerdictAgreementDistribution] = {}

    for tier in CONTEXT_TIERS:
        bucket_counts = {bucket: 0 for bucket in AGREEMENT_BUCKETS}
        total_cases = 0
        for subject in sorted(bundle.subjects, key=lambda item: item.subject_id):
            context = _build_context(tier=tier, subject=subject, rules=bundle.rules)
            location_ids = _pairing_location_ids(subject, context)
            for location_id in location_ids:
                verdicts: list[Verdict] = []
                for sample_index in indices:
                    key = make_cache_key(
                        context=context,
                        model_id=model_id,
                        runner_id=tier,
                        case_id=subject.subject_id,
                        sample_index=sample_index,
                    )
                    entry = store.get(key)
                    verdicts.append(
                        _extract_verdict(entry.raw_response.get("verdicts", []), location_id)
                    )
                bucket = _agreement_bucket(verdicts)
                bucket_counts[bucket] += 1
                total_cases += 1
        distributions[tier] = VerdictAgreementDistribution(
            tier=tier,
            bucket_counts=bucket_counts,
            total_cases=total_cases,
        )
    return distributions

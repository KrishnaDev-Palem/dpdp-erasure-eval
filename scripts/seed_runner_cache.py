"""Seed committed cache entries for offline tier runner sweeps."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from core.cache.store import make_cache_key, write_cache
from core.context import build_t1, build_t2, build_t3
from core.export import load_export
from core.pseudonymize import build_substitution_map
from core.types import CacheEntry, Tier, Verdict
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID
from runners.translation import location_id_inverse, to_real_location_id
from runners.types import DEFAULT_ADJUDICATION_SAMPLE_INDICES

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "cache"


def _base_verdicts(subject) -> dict[str, Verdict]:
    """Map each location's expected verdict onto the id the model actually saw.

    A seeded entry stands in for a response a model returned, and a model is only ever
    shown opaque location ids. Keyed on the real id this map cannot be indexed by the
    ids the context builders emit at all.
    """
    mapping = build_substitution_map(subject)
    return {
        mapping[location.location_id]: location.expected.verdict for location in subject.locations
    }


def _verdicts_for(subject, _sample_index: int) -> dict[str, Verdict]:
    return _base_verdicts(subject)


def _build_context(tier: Tier, subject, rules):
    if tier == "t1":
        return build_t1(subject.request, subject)
    if tier == "t2":
        return build_t2(subject.request, subject)
    return build_t3(subject.request, subject, rules)


def _tool_calls_for(subject) -> list[dict]:
    """Mirror the trace a real autonomous session records for this subject.

    `summarize_tool_result` reads its ids straight out of the substituted tool payload,
    so a faithful seeded trace carries opaque ids in both the arguments and the summary.
    """
    mapping = build_substitution_map(subject)
    opaque_subject_id = mapping[subject.subject_id]
    location_ids = sorted(mapping[location.location_id] for location in subject.locations)
    return [
        {
            "sequence": 0,
            "tool_name": "get_location_records",
            "arguments": {"subject_id": opaque_subject_id},
            "result_summary": {
                "subject_id": opaque_subject_id,
                "location_count": len(location_ids),
                "location_ids": location_ids,
            },
        }
    ]


def _verdict_payload(
    subject, location_ids: list[str], verdict_map: dict[str, Verdict]
) -> list[dict]:
    """Build the seeded verdict list, refusing to write one no sweep could read back.

    A seeder that exits 0 having written entries that raise on the read path is a worse
    failure than one that crashes, so every id goes through the same inverse
    `runners/spine.py` and `runners/autonomous/cache.py` apply on each cache hit.
    """
    inverse = location_id_inverse(subject)
    for location_id in location_ids:
        to_real_location_id(location_id, inverse)
    return [
        {"location_id": lid, "verdict": verdict_map[lid], "detail": None} for lid in location_ids
    ]


def _bundle_location_ids(subject, context) -> list[str]:
    """Read the opaque ids out of the bundle, which is what the prompt was rendered from.

    An empty list is a context-builder regression rather than a subject to pass over: the
    committed export gives every subject at least one location, and skipping silently
    would seed a short tier that still looks green.
    """
    location_ids = [location["location_id"] for location in context.locations]
    if not location_ids:
        raise ValueError(f"Context bundle for {subject.subject_id!r} carries no locations")
    return location_ids


def seed_tier(
    tier: Tier,
    *,
    model_id: str = "primary",
    export_dir: Path | None = None,
    cache_root: Path | None = None,
) -> int:
    export = load_export(export_dir or REPO_ROOT / "export")
    cache_path = cache_root or CACHE_ROOT
    written = 0
    recorded_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for subject in export.subjects:
        context = _build_context(tier, subject, export.rules)
        location_ids = _bundle_location_ids(subject, context)
        for sample_index in DEFAULT_ADJUDICATION_SAMPLE_INDICES:
            verdict_map = _verdicts_for(subject, sample_index)
            key = make_cache_key(
                context=context,
                model_id=model_id,
                runner_id=tier,
                case_id=subject.subject_id,
                sample_index=sample_index,
            )
            entry = CacheEntry(
                key=key,
                raw_response={"verdicts": _verdict_payload(subject, location_ids, verdict_map)},
                recorded_at=recorded_at,
            )
            write_cache(entry, cache_path)
            written += 1
    return written


def seed_autonomous(
    *,
    model_id: str = "primary",
    export_dir: Path | None = None,
    cache_root: Path | None = None,
) -> int:
    export = load_export(export_dir or REPO_ROOT / "export")
    cache_path = cache_root or CACHE_ROOT
    written = 0
    recorded_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for subject in export.subjects:
        context = build_t1(subject.request, subject)
        location_ids = _bundle_location_ids(subject, context)
        for sample_index in DEFAULT_ADJUDICATION_SAMPLE_INDICES:
            verdict_map = _verdicts_for(subject, sample_index)
            key = make_cache_key(
                context=context,
                model_id=model_id,
                runner_id=AUTONOMOUS_RUNNER_ID,
                case_id=subject.subject_id,
                sample_index=sample_index,
            )
            entry = CacheEntry(
                key=key,
                raw_response={"verdicts": _verdict_payload(subject, location_ids, verdict_map)},
                recorded_at=recorded_at,
                tool_calls=_tool_calls_for(subject),
            )
            write_cache(entry, cache_path)
            written += 1
    return written


def _clear_runner_namespace(
    runner_id: str,
    *,
    model_id: str = "primary",
    cache_root: Path | None = None,
) -> None:
    namespace = (cache_root or CACHE_ROOT) / model_id / runner_id
    if namespace.is_dir():
        for child in namespace.iterdir():
            if child.is_dir():
                shutil.rmtree(child)


def main() -> None:
    for tier in ("t1", "t2", "t3"):
        _clear_runner_namespace(tier)
    _clear_runner_namespace(AUTONOMOUS_RUNNER_ID)

    total = 0
    for tier in ("t1", "t2", "t3"):
        count = seed_tier(tier)  # type: ignore[arg-type]
        print(f"Seeded {count} cache entries for {tier}")
        total += count
    autonomous_count = seed_autonomous()
    print(f"Seeded {autonomous_count} cache entries for autonomous")
    total += autonomous_count
    print(f"Total: {total} entries under {CACHE_ROOT}")


if __name__ == "__main__":
    main()

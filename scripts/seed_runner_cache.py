"""Seed committed cache entries for offline tier runner sweeps."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.cache.store import make_cache_key, write_cache
from core.context import build_t1, build_t2, build_t3
from core.export import load_export
from core.types import CacheEntry, Tier, Verdict
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "cache"


def _base_verdicts(subject) -> dict[str, Verdict]:
    return {location.location_id: location.expected.verdict for location in subject.locations}


def _verdicts_for(subject, sample_index: int) -> dict[str, Verdict]:
    verdicts = _base_verdicts(subject)
    if sample_index == 1 and "mixed_fanout" in subject.tags:
        for location_id, verdict in list(verdicts.items()):
            if verdict == "erase":
                verdicts[location_id] = "retain"
                break
    return verdicts


def _build_context(tier: Tier, subject, rules):
    if tier == "t1":
        return build_t1(subject.request, subject)
    if tier == "t2":
        return build_t2(subject.request, subject)
    return build_t3(subject.request, subject, rules)


def _tool_calls_for(subject) -> list[dict]:
    location_ids = sorted(location.location_id for location in subject.locations)
    return [
        {
            "sequence": 0,
            "tool_name": "get_location_records",
            "arguments": {"subject_id": subject.subject_id},
            "result_summary": {
                "subject_id": subject.subject_id,
                "location_count": len(location_ids),
                "location_ids": location_ids,
            },
        }
    ]


def seed_tier(tier: Tier, *, model_id: str = "primary") -> int:
    export = load_export(REPO_ROOT / "export")
    written = 0
    recorded_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for subject in export.subjects:
        context = _build_context(tier, subject, export.rules)
        location_ids = (
            [loc.location_id for loc in subject.locations]
            if tier == "t1"
            else [loc["location_id"] for loc in context.locations]
        )
        if not location_ids:
            continue
        for sample_index in range(5):
            verdict_map = _verdicts_for(subject, sample_index)
            key = make_cache_key(
                context=context,
                model_id=model_id,
                runner_id=tier,
                case_id=subject.subject_id,
                sample_index=sample_index,
            )
            verdicts = [
                {"location_id": lid, "verdict": verdict_map[lid], "detail": None}
                for lid in location_ids
            ]
            entry = CacheEntry(
                key=key,
                raw_response={"verdicts": verdicts},
                recorded_at=recorded_at,
            )
            write_cache(entry, CACHE_ROOT)
            written += 1
    return written


def seed_autonomous(*, model_id: str = "primary") -> int:
    export = load_export(REPO_ROOT / "export")
    written = 0
    recorded_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for subject in export.subjects:
        if not subject.locations:
            continue
        context = build_t1(subject.request, subject)
        location_ids = [location.location_id for location in subject.locations]
        for sample_index in range(5):
            verdict_map = _verdicts_for(subject, sample_index)
            key = make_cache_key(
                context=context,
                model_id=model_id,
                runner_id=AUTONOMOUS_RUNNER_ID,
                case_id=subject.subject_id,
                sample_index=sample_index,
            )
            verdicts = [
                {"location_id": lid, "verdict": verdict_map[lid], "detail": None}
                for lid in location_ids
            ]
            entry = CacheEntry(
                key=key,
                raw_response={"verdicts": verdicts},
                recorded_at=recorded_at,
                tool_calls=_tool_calls_for(subject),
            )
            write_cache(entry, CACHE_ROOT)
            written += 1
    return written


def _clear_runner_namespace(runner_id: str, *, model_id: str = "primary") -> None:
    namespace = CACHE_ROOT / model_id / runner_id
    if namespace.is_dir():
        for child in namespace.iterdir():
            if child.is_dir():
                import shutil

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

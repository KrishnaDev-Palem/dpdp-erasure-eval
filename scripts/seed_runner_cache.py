"""Seed committed cache entries for offline tier runner sweeps."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from core.cache.store import make_cache_key, write_cache
from core.context import build_t1, build_t2, build_t3
from core.export import load_export
from core.types import CacheEntry, Tier, Verdict

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "cache"

# Per-subject verdicts per location_id (matches export expected for sample 0;
# sample 1+ may vary for variance testing).
DEFAULT_VERDICTS: dict[str, dict[str, Verdict]] = {
    "mixed-fanout-subject": {"txn-004": "retain", "note-001": "erase"},
    "floor-inside-subject": {"kyc-001": "retain"},
    "empty-locations-subject": {},
}

# Sample 1 introduces one over-erasure on mixed-fanout for variance tests.
SAMPLE_OVERRIDES: dict[int, dict[str, dict[str, Verdict]]] = {
    1: {"mixed-fanout-subject": {"note-001": "retain"}},
}


def _verdicts_for(subject_id: str, sample_index: int) -> dict[str, Verdict]:
    base = dict(DEFAULT_VERDICTS.get(subject_id, {}))
    overrides = SAMPLE_OVERRIDES.get(sample_index, {}).get(subject_id, {})
    base.update(overrides)
    return base


def _build_context(tier: Tier, subject, rules):
    if tier == "t1":
        return build_t1(subject.request, subject)
    if tier == "t2":
        return build_t2(subject.request, subject)
    return build_t3(subject.request, subject, rules)


def seed_tier(tier: Tier, *, model_id: str = "primary") -> int:
    export = load_export(REPO_ROOT / "export")
    written = 0
    recorded_at = datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for subject in export.subjects:
        context = _build_context(tier, subject, export.rules)
        if not context.locations:
            continue
        location_ids = [loc["location_id"] for loc in context.locations]
        for sample_index in range(5):
            verdict_map = _verdicts_for(subject.subject_id, sample_index)
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


def main() -> None:
    total = 0
    for tier in ("t1", "t2", "t3"):
        count = seed_tier(tier)  # type: ignore[arg-type]
        print(f"Seeded {count} cache entries for {tier}")
        total += count
    print(f"Total: {total} entries under {CACHE_ROOT}")


if __name__ == "__main__":
    main()

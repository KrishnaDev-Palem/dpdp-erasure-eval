"""Gate-specific cache key construction and classify_note resolution."""

from __future__ import annotations

from datetime import UTC, datetime

from core.cache.canonicalize import prompt_hash
from core.cache.store import CacheStore, read_cache, write_cache
from core.exceptions import CacheMissError
from core.model.seam import ModelSeam
from core.types import AdversarialSeedCase, CacheEntry, CacheKey, ClassifierResult
from runners.adversarial_gate.types import GATE_RUNNER_ID


def make_gate_cache_key(
    *,
    text: str,
    model_id: str,
    case_id: str,
    sample_index: int,
) -> CacheKey:
    if sample_index not in range(5):
        raise ValueError(f"sample_index must be 0..4, got {sample_index}")
    return CacheKey(
        model_id=model_id,
        runner_id=GATE_RUNNER_ID,
        case_id=case_id,
        prompt_hash=prompt_hash({"text": text}),
        sample_index=sample_index,
    )


def _parse_classifier_result(raw_response: dict) -> ClassifierResult:
    outcome = raw_response.get("outcome")
    if outcome not in {"clean", "adversarial"}:
        raise ValueError(f"Invalid classifier outcome: {outcome!r}")
    return ClassifierResult(outcome=outcome, detail=raw_response.get("detail"))


def classify_with_cache(
    *,
    case: AdversarialSeedCase,
    sample_index: int,
    model_id: str,
    store: CacheStore,
    seam: ModelSeam,
) -> ClassifierResult:
    key = make_gate_cache_key(
        text=case.text,
        model_id=model_id,
        case_id=case.case_id,
        sample_index=sample_index,
    )
    try:
        entry = store.get(key)
        return _parse_classifier_result(entry.raw_response)
    except CacheMissError:
        if store.cache_mode != "refresh":
            raise CacheMissError(
                f"Cache miss for runner_id={GATE_RUNNER_ID}, "
                f"case_id={case.case_id}, sample_index={sample_index}"
            ) from None
        result = seam.classify_note(text=case.text, case_id=case.case_id)
        entry = CacheEntry(
            key=key,
            raw_response=result.model_dump(mode="json"),
            recorded_at=datetime.now(tz=UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        )
        store.put(entry)
        return result


def resolve_from_cache_entry(key: CacheKey, store: CacheStore) -> ClassifierResult:
    entry = read_cache(key, store.root)
    return _parse_classifier_result(entry.raw_response)


def write_gate_cache_entry(
    *,
    case: AdversarialSeedCase,
    sample_index: int,
    model_id: str,
    outcome: str,
    cache_root,
    recorded_at: str = "2026-07-03T12:00:00Z",
) -> CacheKey:
    key = make_gate_cache_key(
        text=case.text,
        model_id=model_id,
        case_id=case.case_id,
        sample_index=sample_index,
    )
    write_cache(
        CacheEntry(
            key=key,
            raw_response={"outcome": outcome, "detail": None},
            recorded_at=recorded_at,
        ),
        cache_root,
    )
    return key

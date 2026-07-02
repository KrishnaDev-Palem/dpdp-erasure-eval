"""Filesystem cache read/write with offline and refresh modes."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from core.cache.canonicalize import prompt_hash
from core.exceptions import CacheMissError
from core.model.seam import ModelSeam
from core.types import CacheEntry, CacheKey, ContextBundle


def _cache_root(root: Path | None = None) -> Path:
    return root or Path("cache")


def _entry_path(root: Path, key: CacheKey) -> Path:
    return (
        root
        / key.model_id
        / key.runner_id
        / key.case_id
        / key.prompt_hash
        / f"{key.sample_index}.json"
    )


def _validate_sample_index(sample_index: int) -> None:
    if sample_index not in range(5):
        raise ValueError(f"sample_index must be 0..4, got {sample_index}")


def make_cache_key(
    *,
    context: ContextBundle,
    model_id: str,
    runner_id: str,
    case_id: str,
    sample_index: int,
) -> CacheKey:
    _validate_sample_index(sample_index)
    return CacheKey(
        model_id=model_id,
        runner_id=runner_id,
        case_id=case_id,
        prompt_hash=prompt_hash(context),
        sample_index=sample_index,
    )


def read_cache(key: CacheKey, root: Path | None = None) -> CacheEntry:
    path = _entry_path(_cache_root(root), key)
    if not path.is_file():
        raise CacheMissError(f"Cache miss for key at {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return CacheEntry(
        key=key,
        raw_response=data.get("raw_response", {}),
        recorded_at=data["recorded_at"],
        tool_calls=data.get("tool_calls", []),
    )


def write_cache(entry: CacheEntry, root: Path | None = None) -> Path:
    path = _entry_path(_cache_root(root), entry.key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": entry.key.model_id,
        "runner_id": entry.key.runner_id,
        "case_id": entry.key.case_id,
        "prompt_hash": entry.key.prompt_hash,
        "sample_index": entry.key.sample_index,
        "recorded_at": entry.recorded_at,
        "raw_response": entry.raw_response,
        "tool_calls": entry.tool_calls,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


class CacheStore:
    def __init__(self, root: Path | None = None, cache_mode: str | None = None) -> None:
        self.root = _cache_root(root)
        self.cache_mode = cache_mode or os.environ.get("CACHE_MODE", "offline")

    def get(self, key: CacheKey) -> CacheEntry:
        return read_cache(key, self.root)

    def put(self, entry: CacheEntry) -> Path:
        return write_cache(entry, self.root)

    def get_or_refresh(
        self,
        *,
        key: CacheKey,
        context: ContextBundle,
        seam: ModelSeam,
    ) -> CacheEntry:
        try:
            return self.get(key)
        except CacheMissError:
            if self.cache_mode != "refresh":
                raise
            verdicts = seam.adjudicate(context=context, case_id=key.case_id)
            entry = CacheEntry(
                key=key,
                raw_response={"verdicts": [item.model_dump(mode="json") for item in verdicts]},
                recorded_at=datetime.now(tz=UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            )
            self.put(entry)
            return entry

"""Acceptance tests for offline cache replay."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.cache import canonicalize, prompt_hash, read_cache, write_cache
from core.cache.store import CacheStore, make_cache_key
from core.context import build_t1
from core.exceptions import CacheMissError
from core.export import load_export
from core.model import FakeModelSeam
from core.types import CacheEntry, ContextBundle, ErasureRequest


def _t1_context(subject_id: str = "mixed-fanout-subject") -> ContextBundle:
    request = ErasureRequest(
        subject_id=subject_id,
        type="erasure",
        basis="explicit_erasure_right",
        as_of="2026-06-01",
    )
    bundle = load_export()
    subject = next(item for item in bundle.subjects if item.subject_id == subject_id)
    return build_t1(request, subject)


def test_cache_hit(export_dir: Path, cache_dir: Path) -> None:
    context = _t1_context()
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id="mixed-fanout-subject",
        sample_index=0,
    )
    entry = read_cache(key, cache_dir)
    assert entry.raw_response["verdicts"]


def test_cache_miss_raises(cache_dir: Path) -> None:
    context = _t1_context("empty-locations-subject")
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id="empty-locations-subject",
        sample_index=0,
    )
    with pytest.raises(CacheMissError):
        read_cache(key, cache_dir)


def test_canonical_hash_stability() -> None:
    context = _t1_context()
    first = prompt_hash(context)
    second = prompt_hash(context)
    assert first == second
    assert canonicalize(context) == canonicalize(context)


@pytest.mark.parametrize("sample_index", [0, 1, 2, 3, 4])
def test_sample_index_keys(sample_index: int, cache_dir: Path) -> None:
    context = _t1_context()
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id="mixed-fanout-subject",
        sample_index=sample_index,
    )
    if sample_index == 0:
        entry = read_cache(key, cache_dir)
        assert entry.key.sample_index == 0
    else:
        with pytest.raises(CacheMissError):
            read_cache(key, cache_dir)


@pytest.mark.refresh
def test_refresh_opt_in_writes_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    context = _t1_context("empty-locations-subject")
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id="empty-locations-subject",
        sample_index=1,
    )
    seam = FakeModelSeam(adjudication_verdicts={})
    store = CacheStore(root=tmp_path, cache_mode="refresh")
    entry = store.get_or_refresh(key=key, context=context, seam=seam)
    assert entry.raw_response["verdicts"] == []
    assert (tmp_path / "primary/t1/empty-locations-subject").exists()


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    context = _t1_context()
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id="mixed-fanout-subject",
        sample_index=2,
    )
    entry = CacheEntry(
        key=key,
        raw_response={"verdicts": []},
        recorded_at=datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    write_cache(entry, tmp_path)
    loaded = read_cache(key, tmp_path)
    assert loaded.raw_response == {"verdicts": []}

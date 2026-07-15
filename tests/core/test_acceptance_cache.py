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
from core.types import AdjudicationSubject, CacheEntry, ContextBundle, ErasureRequest
from tests.core.conftest import subject_with_tag

SYNTHETIC_EMPTY_SUBJECT_ID = "synthetic-empty-subject"


def _mixed_fanout_subject():
    export = load_export()
    return subject_with_tag(export.subjects, "mixed_fanout")


def _t1_context(subject: AdjudicationSubject | None = None) -> ContextBundle:
    subject = subject or _mixed_fanout_subject()
    return build_t1(subject.request, subject)


def _empty_subject() -> AdjudicationSubject:
    return AdjudicationSubject(
        subject_id=SYNTHETIC_EMPTY_SUBJECT_ID,
        tags=["under_determined"],
        request=ErasureRequest(
            subject_id=SYNTHETIC_EMPTY_SUBJECT_ID,
            type="erasure",
            basis="explicit_erasure_right",
            as_of="2026-06-01",
        ),
        locations=[],
    )


def test_cache_hit(export_dir: Path, cache_dir: Path) -> None:
    subject = _mixed_fanout_subject()
    context = _t1_context(subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        sample_index=0,
    )
    entry = read_cache(key, cache_dir)
    assert entry.raw_response["verdicts"]


def test_cache_miss_raises(cache_dir: Path) -> None:
    subject = _empty_subject()
    context = _t1_context(subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
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
    subject = _mixed_fanout_subject()
    context = _t1_context(subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        sample_index=sample_index,
    )
    entry = read_cache(key, cache_dir)
    assert entry.key.sample_index == sample_index


@pytest.mark.refresh
def test_refresh_opt_in_writes_entry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    subject = _empty_subject()
    context = _t1_context(subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        sample_index=1,
    )
    seam = FakeModelSeam(adjudication_verdicts={})
    store = CacheStore(root=tmp_path, cache_mode="refresh")
    entry = store.get_or_refresh(key=key, context=context, seam=seam)
    assert entry.raw_response["verdicts"] == []
    assert (tmp_path / "primary/t1" / subject.subject_id).exists()


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    subject = _mixed_fanout_subject()
    context = _t1_context(subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
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

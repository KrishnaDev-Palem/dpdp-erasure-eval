"""Opt-in acceptance tests for CACHE_MODE=refresh."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.cache.store import CacheStore, make_cache_key
from core.context import build_t2
from core.export import load_export
from core.model import FakeModelSeam
from tests.core.conftest import subject_with_tag


@pytest.mark.refresh
def test_refresh_cache_hit_replays_without_live_call(
    export_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    monkeypatch.setenv("MODEL_ID", "primary")

    export = load_export(export_dir)
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
    context = build_t2(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t2",
        case_id=subject.subject_id,
        sample_index=0,
    )

    cache_root = tmp_path / "cache"
    shutil.copytree(export_dir.parent / "cache" / "primary", cache_root / "primary")
    seam = FakeModelSeam()
    store = CacheStore(root=cache_root, cache_mode="refresh")

    store.get_or_refresh(key=key, context=context, seam=seam)
    assert seam.adjudicate_calls == []


@pytest.mark.refresh
def test_tier_refresh_integration_with_factory_seam(
    export_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US2: refresh miss via factory-built seam writes canonical cache entry."""
    from unittest.mock import MagicMock

    from core.model.anthropic_adapter import AnthropicModelSeam, LiveAdapterConfig

    monkeypatch.setenv("CACHE_MODE", "refresh")
    monkeypatch.setenv("MODEL_ID", "claude-sonnet-5")

    export = load_export(export_dir)
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
    context = build_t2(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="claude-sonnet-5",
        runner_id="t2",
        case_id=subject.subject_id,
        sample_index=0,
    )

    client = MagicMock()
    from types import SimpleNamespace

    client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="text",
                text=(
                    '{"verdicts": [{"location_id": "txn-004", "verdict": "retain"}, '
                    '{"location_id": "note-001", "verdict": "erase"}]}'
                ),
            )
        ]
    )
    seam = AnthropicModelSeam(
        LiveAdapterConfig(
            role_id="claude-sonnet-5",
            provider_model_id="claude-sonnet-5",
            api_key="sk-test",
        ),
        client=client,
    )
    cache_root = tmp_path / "cache"
    store = CacheStore(root=cache_root, cache_mode="refresh")
    entry = store.get_or_refresh(key=key, context=context, seam=seam)
    assert entry.raw_response.get("verdicts")
    replay = store.get(key)
    assert replay.raw_response == entry.raw_response


@pytest.mark.refresh
def test_refresh_writes_cache_entry_on_miss(
    export_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-007: refresh mode fetches via seam and persists a new cache entry."""
    monkeypatch.setenv("CACHE_MODE", "refresh")
    monkeypatch.setenv("MODEL_ID", "primary")

    export = load_export(export_dir)
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    context = build_t2(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t2",
        case_id=subject.subject_id,
        sample_index=0,
    )

    cache_root = tmp_path / "cache"
    seam = FakeModelSeam(
        adjudication_verdicts={
            location.location_id: location.expected.verdict for location in subject.locations
        }
    )
    store = CacheStore(root=cache_root, cache_mode="refresh")

    entry = store.get_or_refresh(key=key, context=context, seam=seam)
    assert entry.raw_response.get("verdicts")
    assert seam.adjudicate_calls

    replay = store.get(key)
    assert replay.raw_response == entry.raw_response

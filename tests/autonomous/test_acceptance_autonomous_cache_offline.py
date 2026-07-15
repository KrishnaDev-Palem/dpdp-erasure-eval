"""Acceptance tests for autonomous offline cache replay."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cache import make_cache_key, prompt_hash
from core.cache.store import CacheStore
from core.context import build_t1
from core.exceptions import CacheMissError
from core.model import FakeModelSeam
from core.tools import build_retrieval_tool_registry
from runners.autonomous.cache import resolve_autonomous_entry
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID
from tests.core.conftest import subject_with_tag


def test_offline_replay_via_autonomous_runner_id(
    fake_seam: FakeModelSeam,
    export_bundle,
    autonomous_config,
) -> None:
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    store = CacheStore(root=autonomous_config.cache_root, cache_mode="offline")
    session = resolve_autonomous_entry(
        context=context,
        subject_id=subject.subject_id,
        sample_index=0,
        model_id=autonomous_config.model_id,
        store=store,
        seam=fake_seam,
        tool_registry=registry,
    )
    assert len(session.raw_verdicts) == len(subject.locations)
    assert fake_seam.adjudicate_calls == []


def test_cache_prompt_identity_from_t1_context_only(export_bundle) -> None:
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    context = build_t1(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=AUTONOMOUS_RUNNER_ID,
        case_id=subject.subject_id,
        sample_index=0,
    )
    assert key.prompt_hash == prompt_hash(context)
    assert context.tier == "t1"
    assert context.locations == []


@pytest.mark.cache_miss
def test_offline_cache_miss_names_identifiers(
    fake_seam: FakeModelSeam,
    export_bundle,
    tmp_path: Path,
) -> None:
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    empty_cache = tmp_path / "cache"
    empty_cache.mkdir()
    store = CacheStore(root=empty_cache, cache_mode="offline")
    with pytest.raises(CacheMissError) as exc_info:
        resolve_autonomous_entry(
            context=context,
            subject_id=subject.subject_id,
            sample_index=0,
            model_id="primary",
            store=store,
            seam=fake_seam,
            tool_registry=registry,
        )
    message = str(exc_info.value).lower()
    assert "autonomous" in message
    assert subject.subject_id in message
    assert "sample_index=0" in message or "sample_index" in message
    assert fake_seam.adjudicate_calls == []


@pytest.mark.refresh
def test_resolve_autonomous_entry_refresh_miss_writes_tool_calls(
    export_bundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from core.model.anthropic_adapter import AnthropicModelSeam, LiveAdapterConfig

    monkeypatch.setenv("CACHE_MODE", "refresh")
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    verdict_json = ", ".join(
        f'{{"location_id": "{location.location_id}", "verdict": "{location.expected.verdict}"}}'
        for location in subject.locations
    )
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    cache_root = tmp_path / "cache"
    store = CacheStore(root=cache_root, cache_mode="refresh")

    tool_block = SimpleNamespace(
        type="tool_use",
        id="tool-1",
        name="get_location_records",
        input={"subject_id": subject.subject_id},
    )
    text_block = SimpleNamespace(
        type="text",
        text=f'{{"verdicts": [{verdict_json}]}}',
    )
    client = MagicMock()
    client.messages.create.side_effect = [
        SimpleNamespace(content=[tool_block]),
        SimpleNamespace(content=[text_block]),
    ]

    seam = AnthropicModelSeam(
        LiveAdapterConfig(
            role_id="claude-sonnet-5",
            provider_model_id="claude-sonnet-5",
            api_key="sk-test",
        ),
        client=client,
    )
    session = resolve_autonomous_entry(
        context=context,
        subject_id=subject.subject_id,
        sample_index=0,
        model_id="claude-sonnet-5",
        store=store,
        seam=seam,
        tool_registry=registry,
    )
    assert session.tool_calls
    assert len(session.tool_calls) >= 1
    key = make_cache_key(
        context=context,
        model_id="claude-sonnet-5",
        runner_id=AUTONOMOUS_RUNNER_ID,
        case_id=subject.subject_id,
        sample_index=0,
    )
    entry = store.get(key)
    assert entry.tool_calls


@pytest.mark.refresh
def test_refresh_path_available(
    export_bundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    cache_root = tmp_path / "cache"
    store = CacheStore(root=cache_root, cache_mode="refresh")
    seam = FakeModelSeam(
        pairing_location_ids=[location.location_id for location in subject.locations],
        adjudication_verdicts={
            location.location_id: location.expected.verdict for location in subject.locations
        },
    )
    session = resolve_autonomous_entry(
        context=context,
        subject_id=subject.subject_id,
        sample_index=0,
        model_id="primary",
        store=store,
        seam=seam,
        tool_registry=registry,
    )
    assert session.verdicts
    assert seam.adjudicate_calls

"""Acceptance tests for ground-truth isolation in autonomous evaluation."""

from __future__ import annotations

import json

import pytest

from core.cache import make_cache_key, prompt_hash
from core.context import build_t1
from core.tools import build_retrieval_tool_registry
from runners.autonomous.cache import resolve_autonomous_entry
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID
from tests.core.conftest import subject_with_tag


def _assert_no_expected(payload) -> None:
    serialized = payload if isinstance(payload, str) else json.dumps(payload)
    assert "expected" not in serialized


def _mixed_fanout_subject(export_bundle):
    return subject_with_tag(export_bundle.subjects, "mixed_fanout")


@pytest.mark.context_isolation
def test_t1_initial_context_has_no_expected(export_bundle) -> None:
    subject = _mixed_fanout_subject(export_bundle)
    context = build_t1(subject.request, subject)
    _assert_no_expected(context.model_dump(mode="json"))


@pytest.mark.context_isolation
def test_autonomous_cache_key_context_has_no_expected(export_bundle) -> None:
    subject = _mixed_fanout_subject(export_bundle)
    context = build_t1(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=AUTONOMOUS_RUNNER_ID,
        case_id=subject.subject_id,
        sample_index=0,
    )
    _assert_no_expected(context.model_dump(mode="json"))
    assert key.prompt_hash == prompt_hash(context)


@pytest.mark.context_isolation
def test_offline_cache_payload_has_no_expected(
    fake_seam,
    export_bundle,
    cache_dir,
    autonomous_config,
) -> None:
    from core.cache.store import CacheStore

    subject = _mixed_fanout_subject(export_bundle)
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    store = CacheStore(root=autonomous_config.cache_root, cache_mode=autonomous_config.cache_mode)
    session = resolve_autonomous_entry(
        context=context,
        subject_id=subject.subject_id,
        sample_index=0,
        model_id=autonomous_config.model_id,
        store=store,
        seam=fake_seam,
        tool_registry=registry,
    )
    _assert_no_expected(session.model_dump(mode="json"))
    assert fake_seam.adjudicate_calls == []


@pytest.mark.tool_isolation
def test_location_records_has_no_expected(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    subject = _mixed_fanout_subject(export_bundle)
    result = registry.invoke(
        "get_location_records",
        {"subject_id": subject.subject_id},
    )
    _assert_no_expected(result)
    assert result["locations"]


@pytest.mark.tool_isolation
def test_retention_floors_has_no_expected(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    result = registry.invoke("get_retention_floors", {})
    _assert_no_expected(result)
    assert len(result["retention_floors"]) == 5


@pytest.mark.tool_isolation
def test_governance_map_has_no_expected(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    result = registry.invoke("get_governance_map", {})
    _assert_no_expected(result)
    assert result["governance_map"]

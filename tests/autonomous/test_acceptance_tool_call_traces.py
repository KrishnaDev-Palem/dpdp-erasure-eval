"""Acceptance tests for tool-call trace persistence in autonomous cache."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.cache import make_cache_key, read_cache
from core.cache.store import CacheStore
from core.context import build_t1
from core.model import FakeModelSeam
from core.tools import build_retrieval_tool_registry
from core.types import ToolCallTrace
from runners.autonomous.cache import resolve_autonomous_entry
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID


def test_tool_call_trace_model_validates_tool_name() -> None:
    trace = ToolCallTrace(
        sequence=0,
        tool_name="get_location_records",
        arguments={"subject_id": "mixed-fanout-subject"},
        result_summary={
            "subject_id": "mixed-fanout-subject",
            "location_count": 2,
            "location_ids": ["note-001", "txn-004"],
        },
    )
    assert trace.sequence == 0


def test_tool_call_trace_rejects_expected_in_payload() -> None:
    with pytest.raises(ValueError, match="expected"):
        ToolCallTrace(
            sequence=0,
            tool_name="get_location_records",
            arguments={"expected": "erase"},
            result_summary={"location_count": 0, "location_ids": []},
        )


def test_offline_replay_reads_stored_tool_calls(
    fake_seam: FakeModelSeam,
    export_bundle,
    autonomous_config,
) -> None:
    subject = next(
        item for item in export_bundle.subjects if item.subject_id == "mixed-fanout-subject"
    )
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
    assert session.tool_calls
    assert session.tool_calls[0].tool_name == "get_location_records"
    assert fake_seam.adjudicate_calls == []


def test_offline_replay_does_not_reexecute_tools(
    fake_seam: FakeModelSeam,
    export_bundle,
    autonomous_config,
) -> None:
    subject = next(
        item for item in export_bundle.subjects if item.subject_id == "mixed-fanout-subject"
    )
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    store = CacheStore(root=autonomous_config.cache_root, cache_mode="offline")
    resolve_autonomous_entry(
        context=context,
        subject_id=subject.subject_id,
        sample_index=0,
        model_id=autonomous_config.model_id,
        store=store,
        seam=fake_seam,
        tool_registry=registry,
    )
    assert fake_seam.adjudicate_calls == []


def test_empty_tool_calls_valid_when_no_tools_invoked(
    fake_seam: FakeModelSeam,
    export_bundle,
    autonomous_config,
) -> None:
    subject = next(
        item for item in export_bundle.subjects if item.subject_id == "floor-inside-subject"
    )
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
    assert session.tool_calls == []


@pytest.mark.refresh
def test_refresh_path_persists_tool_calls(
    export_bundle,
    export_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    subject = next(
        item for item in export_bundle.subjects if item.subject_id == "mixed-fanout-subject"
    )
    context = build_t1(subject.request, subject)
    registry = build_retrieval_tool_registry(export_bundle)
    cache_root = tmp_path / "cache"
    store = CacheStore(root=cache_root, cache_mode="refresh")
    seam = FakeModelSeam(
        pairing_location_ids=["txn-004", "note-001"],
        adjudication_verdicts={"txn-004": "retain", "note-001": "erase"},
        planned_tool_calls=[
            ("get_location_records", {"subject_id": subject.subject_id}),
        ],
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
    assert session.tool_calls
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=AUTONOMOUS_RUNNER_ID,
        case_id=subject.subject_id,
        sample_index=0,
    )
    entry = read_cache(key, cache_root)
    assert entry.tool_calls


def test_tier_isolation() -> None:
    cache_root = Path(__file__).resolve().parents[2] / "cache" / "primary"
    for tier in ("t1", "t2", "t3"):
        tier_dir = cache_root / tier
        if not tier_dir.is_dir():
            continue
        for path in tier_dir.rglob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert payload.get("tool_calls", []) == []


def test_gate_isolation() -> None:
    cache_root = Path(__file__).resolve().parents[2] / "cache" / "primary" / "adversarial_gate"
    if not cache_root.is_dir():
        pytest.skip("no gate cache entries")
    for path in cache_root.rglob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("tool_calls", []) == []

"""Acceptance tests for offline autonomous replay from committed live-role cache (Feature 007)."""

from __future__ import annotations

import json

import pytest

from core.cache.store import CacheStore
from core.context import build_t1
from core.model import FakeModelSeam
from core.tools import build_retrieval_tool_registry
from core.types import ToolCallTrace
from runners.autonomous.cache import resolve_autonomous_entry
from runners.autonomous.runner import run_autonomous_sweep
from tests.autonomous.conftest import CACHE_DIR, EXPORT_DIR, make_autonomous_sweep_config
from tests.conftest import LIVE_ROLE_SKIP_REASON, live_role_namespace_ready

LIVE_ROLE = "claude-sonnet-5"
SAMPLE_INDICES = [0, 1, 2, 3, 4]
NAMESPACE = CACHE_DIR / LIVE_ROLE / "autonomous"

pytestmark = pytest.mark.skipif(
    not live_role_namespace_ready(LIVE_ROLE, "autonomous"),
    reason=LIVE_ROLE_SKIP_REASON,
)


def _live_role_config():
    return make_autonomous_sweep_config(
        model_id=LIVE_ROLE,
        cache_mode="offline",
        export_dir=EXPORT_DIR,
        cache_root=CACHE_DIR,
    )


def _serialized(result) -> dict:
    return result.model_dump(mode="json", exclude={"started_at", "finished_at"})


def _cached_subject_ids() -> set[str]:
    return {item.name for item in NAMESPACE.iterdir() if item.is_dir()}


def _replay_sessions(export_bundle) -> dict[tuple[str, int], object]:
    """Replay each committed session via the autonomous cache resolver."""
    registry = build_retrieval_tool_registry(export_bundle)
    store = CacheStore(root=CACHE_DIR, cache_mode="offline")
    sessions: dict[tuple[str, int], object] = {}
    cached_subjects = _cached_subject_ids()
    for subject in export_bundle.subjects:
        if subject.subject_id not in cached_subjects:
            continue
        context = build_t1(subject.request, subject)
        for sample_index in SAMPLE_INDICES:
            sessions[(subject.subject_id, sample_index)] = resolve_autonomous_entry(
                context=context,
                subject_id=subject.subject_id,
                sample_index=sample_index,
                model_id=LIVE_ROLE,
                store=store,
                seam=FakeModelSeam(),
                tool_registry=registry,
            )
    return sessions


def test_autonomous_live_role_replay_completes_without_cache_miss_or_seam_calls() -> None:
    seam = FakeModelSeam()
    result = run_autonomous_sweep(seam=seam, config=_live_role_config())
    assert result is not None
    assert seam.adjudicate_calls == []
    assert seam.classify_calls == []


def test_autonomous_live_role_coverage_five_samples_per_cached_subject() -> None:
    assert NAMESPACE.is_dir(), f"committed live-role namespace missing: {NAMESPACE}"
    case_dirs = _cached_subject_ids()
    assert case_dirs
    entries = sorted(NAMESPACE.rglob("*.json"))
    assert len(entries) == len(case_dirs) * len(SAMPLE_INDICES)
    for subject_id in case_dirs:
        sample_names = sorted(p.name for p in (NAMESPACE / subject_id).rglob("*.json"))
        assert sample_names == [f"{index}.json" for index in SAMPLE_INDICES]

    result = run_autonomous_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert [sample.sample_index for sample in result.samples] == SAMPLE_INDICES


def test_autonomous_live_role_two_run_determinism_including_traces(export_bundle) -> None:
    first_result = run_autonomous_sweep(seam=FakeModelSeam(), config=_live_role_config())
    second_result = run_autonomous_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert _serialized(first_result) == _serialized(second_result)

    first_sessions = _replay_sessions(export_bundle)
    second_sessions = _replay_sessions(export_bundle)
    assert first_sessions.keys() == second_sessions.keys()
    for key, session in first_sessions.items():
        assert session.model_dump(mode="json") == second_sessions[key].model_dump(mode="json")


def test_autonomous_live_role_result_metadata() -> None:
    result = run_autonomous_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert result.model_id == LIVE_ROLE
    assert result.cache_mode == "offline"
    assert result.runner_id == "autonomous"


def test_autonomous_live_role_tool_call_traces_validate(export_bundle) -> None:
    """Every session's tool_calls validate as ToolCallTrace with contiguous sequence."""
    sessions = _replay_sessions(export_bundle)
    assert sessions
    non_empty_by_subject: dict[str, int] = dict.fromkeys(_cached_subject_ids(), 0)
    for (subject_id, _), session in sessions.items():
        for trace in session.tool_calls:
            assert isinstance(trace, ToolCallTrace)
        sequences = [trace.sequence for trace in session.tool_calls]
        assert sequences == list(range(len(sequences)))
        if session.tool_calls:
            non_empty_by_subject[subject_id] += 1
    for subject, count in non_empty_by_subject.items():
        if subject in {key[0] for key in sessions}:
            assert count >= 1, f"no session with tool-use trace for subject {subject!r}"


def test_autonomous_live_role_entries_match_path_segments() -> None:
    """Committed entries embed metadata matching their namespace path segments."""
    assert NAMESPACE.is_dir(), f"committed live-role namespace missing: {NAMESPACE}"
    for entry_path in sorted(NAMESPACE.rglob("*.json")):
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        assert payload["model_id"] == LIVE_ROLE
        assert payload["runner_id"] == "autonomous"
        assert payload["case_id"] == entry_path.parents[1].name
        assert payload["prompt_hash"] == entry_path.parent.name
        assert payload["sample_index"] == int(entry_path.stem)
        for verdict in payload["raw_response"]["verdicts"]:
            assert verdict["verdict"] in {"erase", "retain", "escalate"}
        for item in payload["tool_calls"]:
            ToolCallTrace.model_validate(item)

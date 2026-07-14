"""Acceptance tests for offline gate replay from committed gemini-3.5-flash cache (Feature 007)."""

from __future__ import annotations

import json

from core.model import FakeModelSeam
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from tests.gate.conftest import CACHE_DIR, SLICE_PATH, make_gate_sweep_config

LIVE_ROLE = "gemini-3.5-flash"
SAMPLE_INDICES = [0, 1, 2, 3, 4]
NAMESPACE = CACHE_DIR / LIVE_ROLE / "adversarial_gate"


def _live_role_config():
    return make_gate_sweep_config(
        model_id=LIVE_ROLE,
        cache_mode="offline",
        slice_path=SLICE_PATH,
        cache_root=CACHE_DIR,
    )


def _serialized(result) -> dict:
    return result.model_dump(mode="json", exclude={"started_at", "finished_at"})


def test_gate_live_role_replay_completes_without_cache_miss_or_seam_calls() -> None:
    seam = FakeModelSeam()
    result = run_adversarial_gate_sweep(seam=seam, config=_live_role_config())
    assert result is not None
    assert seam.classify_calls == []
    assert seam.adjudicate_calls == []


def test_gate_live_role_coverage_ninety_cases_five_samples() -> None:
    assert NAMESPACE.is_dir(), f"committed live-role namespace missing: {NAMESPACE}"
    case_dirs = [item for item in NAMESPACE.iterdir() if item.is_dir()]
    assert len(case_dirs) == 90
    entries = sorted(NAMESPACE.rglob("*.json"))
    assert len(entries) == 450

    result = run_adversarial_gate_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert result.slice_case_count == 90
    assert [sample.sample_index for sample in result.samples] == SAMPLE_INDICES
    for sample in result.samples:
        assert sample.total_cases == 90
        assert sample.scored_pairs == 90


def test_gate_live_role_two_run_determinism() -> None:
    first = run_adversarial_gate_sweep(seam=FakeModelSeam(), config=_live_role_config())
    second = run_adversarial_gate_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert _serialized(first) == _serialized(second)


def test_gate_live_role_result_metadata() -> None:
    result = run_adversarial_gate_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert result.model_id == LIVE_ROLE
    assert result.cache_mode == "offline"
    assert result.runner_id == "adversarial_gate"


def test_gate_live_role_entries_match_path_segments() -> None:
    """Committed entries embed metadata matching their namespace path segments."""
    assert NAMESPACE.is_dir(), f"committed live-role namespace missing: {NAMESPACE}"
    for entry_path in sorted(NAMESPACE.rglob("*.json")):
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        assert payload["model_id"] == LIVE_ROLE
        assert payload["runner_id"] == "adversarial_gate"
        assert payload["case_id"] == entry_path.parents[1].name
        assert payload["prompt_hash"] == entry_path.parent.name
        assert payload["sample_index"] == int(entry_path.stem)
        assert payload["raw_response"]["outcome"] in {"clean", "adversarial"}
        assert payload["tool_calls"] == []

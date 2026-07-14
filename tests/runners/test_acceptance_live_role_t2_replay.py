"""Acceptance tests for offline T2 replay from committed claude-sonnet-5 cache (Feature 007)."""

from __future__ import annotations

import json

from core.model import FakeModelSeam
from runners.t2 import run_t2_sweep
from runners.types import SweepConfig
from tests.runners.conftest import CACHE_DIR, EXPORT_DIR

LIVE_ROLE = "claude-sonnet-5"
EXPECTED_SUBJECTS = {"floor-inside-subject", "mixed-fanout-subject"}
SAMPLE_INDICES = [0, 1, 2, 3, 4]
NAMESPACE = CACHE_DIR / LIVE_ROLE / "t2"


def _live_role_config() -> SweepConfig:
    return SweepConfig(
        tier="t2",
        runner_id="t2",
        model_id=LIVE_ROLE,
        cache_mode="offline",
        sample_indices=list(SAMPLE_INDICES),
        export_dir=EXPORT_DIR,
        cache_root=CACHE_DIR,
    )


def _serialized(result) -> dict:
    return result.model_dump(mode="json", exclude={"started_at", "finished_at"})


def test_t2_live_role_replay_completes_without_cache_miss_or_seam_calls() -> None:
    seam = FakeModelSeam()
    result = run_t2_sweep(seam=seam, config=_live_role_config())
    assert result is not None
    assert seam.adjudicate_calls == []
    assert seam.classify_calls == []


def test_t2_live_role_coverage_two_subjects_five_samples() -> None:
    assert NAMESPACE.is_dir(), f"committed live-role namespace missing: {NAMESPACE}"
    case_dirs = {item.name for item in NAMESPACE.iterdir() if item.is_dir()}
    assert case_dirs == EXPECTED_SUBJECTS
    entries = sorted(NAMESPACE.rglob("*.json"))
    assert len(entries) == 10
    for subject in EXPECTED_SUBJECTS:
        sample_names = sorted(p.name for p in (NAMESPACE / subject).rglob("*.json"))
        assert sample_names == [f"{index}.json" for index in SAMPLE_INDICES]

    result = run_t2_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert [sample.sample_index for sample in result.samples] == SAMPLE_INDICES
    for sample in result.samples:
        assert sample.scoring.total_cases > 0


def test_t2_live_role_two_run_determinism() -> None:
    first = run_t2_sweep(seam=FakeModelSeam(), config=_live_role_config())
    second = run_t2_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert _serialized(first) == _serialized(second)


def test_t2_live_role_result_metadata() -> None:
    result = run_t2_sweep(seam=FakeModelSeam(), config=_live_role_config())
    assert result.model_id == LIVE_ROLE
    assert result.cache_mode == "offline"
    assert result.tier == "t2"
    assert result.runner_id == "t2"


def test_t2_live_role_entries_match_path_segments() -> None:
    """Committed entries embed metadata matching their namespace path segments."""
    assert NAMESPACE.is_dir(), f"committed live-role namespace missing: {NAMESPACE}"
    for entry_path in sorted(NAMESPACE.rglob("*.json")):
        payload = json.loads(entry_path.read_text(encoding="utf-8"))
        assert payload["model_id"] == LIVE_ROLE
        assert payload["runner_id"] == "t2"
        assert payload["case_id"] == entry_path.parents[1].name
        assert payload["prompt_hash"] == entry_path.parent.name
        assert payload["sample_index"] == int(entry_path.stem)
        for verdict in payload["raw_response"]["verdicts"]:
            assert verdict["verdict"] in {"erase", "retain", "escalate"}
        assert payload["tool_calls"] == []

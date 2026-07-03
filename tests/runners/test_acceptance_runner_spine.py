"""Acceptance tests for shared runner spine orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.exceptions import CacheMissError, ExportLoadError, ProvenanceError
from core.export import load_export
from core.model import FakeModelSeam
from runners.pairing import PairingValidationError
from runners.spine import run_tier_sweep
from runners.types import SweepConfig


def _config(export_dir: Path, cache_dir: Path, **kwargs) -> SweepConfig:
    defaults = {
        "tier": "t1",
        "runner_id": "t1",
        "model_id": "primary",
        "cache_mode": "offline",
        "sample_indices": [0, 1, 2, 3, 4],
        "export_dir": export_dir,
        "cache_root": cache_dir,
    }
    defaults.update(kwargs)
    return SweepConfig(**defaults)


def test_export_load_and_provenance(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    manifest = bundle.verify_provenance()
    assert len(manifest.agent_commit_sha) == 40


def test_provenance_failure_aborts_sweep(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    bad_export = tmp_path / "export"
    bad_export.mkdir()
    (bad_export / "PINNED_AGENT_SHA").write_text("bad" * 10 + "badbad", encoding="utf-8")
    with pytest.raises((ProvenanceError, ExportLoadError)):
        run_tier_sweep(
            tier="t1",
            seam=fake_seam,
            config=_config(bad_export, cache_dir),
        )


def test_all_subjects_visited(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    export = load_export(export_dir)
    result = run_tier_sweep(
        tier="t1",
        seam=fake_seam,
        config=_config(export_dir, cache_dir),
    )
    expected_count = len(export.subjects)
    for sample in result.samples:
        assert sample.total_subjects == expected_count


def test_empty_locations_subject_visited_no_pairs(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_tier_sweep(
        tier="t1",
        seam=fake_seam,
        config=_config(export_dir, cache_dir),
    )
    assert fake_seam.adjudicate_calls == []
    assert result.samples[0].scoring.total_cases >= 0


def test_offline_deterministic_replay(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    config = _config(export_dir, cache_dir)
    first = run_tier_sweep(tier="t1", seam=fake_seam, config=config)
    second = run_tier_sweep(tier="t1", seam=FakeModelSeam(), config=config)
    for a, b in zip(first.samples, second.samples, strict=True):
        assert a.scoring.model_dump() == b.scoring.model_dump()


def test_invalid_verdict_enum_rejected(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.cache.store import make_cache_key
    from core.context import build_t2

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
    bad_cache = tmp_path / "cache"
    entry_path = (
        bad_cache
        / key.model_id
        / key.runner_id
        / key.case_id
        / key.prompt_hash
        / f"{key.sample_index}.json"
    )
    entry_path.parent.mkdir(parents=True)
    payload = {
        "case_id": key.case_id,
        "model_id": key.model_id,
        "runner_id": key.runner_id,
        "prompt_hash": key.prompt_hash,
        "sample_index": key.sample_index,
        "recorded_at": "2026-07-01T12:00:00Z",
        "raw_response": {
            "verdicts": [
                {"location_id": "txn-004", "verdict": "invalid", "detail": None},
                {"location_id": "note-001", "verdict": "erase", "detail": None},
            ]
        },
        "tool_calls": [],
    }
    entry_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PairingValidationError) as exc_info:
        run_tier_sweep(
            tier="t2",
            seam=fake_seam,
            config=_config(export_dir, bad_cache, tier="t2", runner_id="t2"),
        )
    message = str(exc_info.value)
    assert subject.subject_id in message
    assert "txn-004" in message
    assert "0" in message or "sample_index" in message.lower()


def test_missing_verdict_rejected(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    tmp_path: Path,
) -> None:
    from core.cache.store import make_cache_key
    from core.context import build_t2

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
    bad_cache = tmp_path / "cache"
    entry_path = (
        bad_cache
        / key.model_id
        / key.runner_id
        / key.case_id
        / key.prompt_hash
        / f"{key.sample_index}.json"
    )
    entry_path.parent.mkdir(parents=True)
    payload = {
        "case_id": key.case_id,
        "model_id": key.model_id,
        "runner_id": key.runner_id,
        "prompt_hash": key.prompt_hash,
        "sample_index": key.sample_index,
        "recorded_at": "2026-07-01T12:00:00Z",
        "raw_response": {
            "verdicts": [
                {"location_id": "txn-004", "verdict": "retain", "detail": None},
            ]
        },
        "tool_calls": [],
    }
    entry_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PairingValidationError) as exc_info:
        run_tier_sweep(
            tier="t2",
            seam=fake_seam,
            config=_config(export_dir, bad_cache, tier="t2", runner_id="t2"),
        )
    message = str(exc_info.value)
    assert subject.subject_id in message
    assert "note-001" in message


def test_cache_miss_identifies_subject_and_sample(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    tmp_path: Path,
) -> None:
    empty_cache = tmp_path / "empty-cache"
    empty_cache.mkdir()
    with pytest.raises(CacheMissError) as exc_info:
        run_tier_sweep(
            tier="t2",
            seam=fake_seam,
            config=_config(export_dir, empty_cache, tier="t2", runner_id="t2"),
        )
    message = str(exc_info.value)
    assert "mixed-fanout-subject" in message or "floor-inside-subject" in message
    assert fake_seam.adjudicate_calls == []

"""Acceptance tests for full autonomous adjudication sweep."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.cache import make_cache_key, read_cache
from core.context import build_t1
from core.exceptions import CacheMissError
from core.export import load_export
from core.model import FakeModelSeam
from core.scoring import score_adjudication
from core.types import VERDICT_LANES, ExpectedLabel, ModelVerdict
from runners.autonomous.runner import run_autonomous_sweep
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID
from runners.pairing import PairingValidationError


def test_all_export_subjects_visited(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    assert result.runner_id == "autonomous"
    for sample in result.samples:
        assert sample.total_subjects == 3


def test_request_only_t1_initial_context(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    assert result.initial_context_tier == "t1"


def test_no_blended_accuracy(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    dumped = result.model_dump()
    assert "accuracy" not in dumped
    assert "micro_f1" not in dumped
    assert "blended_score" not in dumped


def test_confusion_matrix_per_lane(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    matrix = result.samples[0].scoring.confusion_matrix
    assert set(matrix.keys()) == set(VERDICT_LANES)
    for row in matrix.values():
        assert set(row.keys()) == set(VERDICT_LANES)


def test_offline_no_model_calls(fake_seam, autonomous_config) -> None:
    run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    assert fake_seam.adjudicate_calls == []


def test_offline_deterministic_replay(
    fake_seam: FakeModelSeam,
    autonomous_config,
) -> None:
    first = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    second = run_autonomous_sweep(seam=FakeModelSeam(), config=autonomous_config)
    for left, right in zip(first.samples, second.samples, strict=True):
        assert left.scoring.model_dump() == right.scoring.model_dump()


def test_empty_locations_subject_visited_no_pairs(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    assert fake_seam.adjudicate_calls == []
    assert result.samples[0].scoring.total_cases == 3


def test_hand_calculated_rate_parity(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    autonomous_config,
) -> None:
    """SC-004: autonomous rates from raw pairs match embedded Rate values."""
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    sample = result.samples[0]
    scoring = sample.scoring

    pairs: list[tuple[ModelVerdict, ExpectedLabel]] = []
    export = load_export(export_dir)
    for subject in export.subjects:
        for location in subject.locations:
            for verdict_data in _cached_verdicts_for_subject(
                subject.subject_id,
                cache_dir,
                sample_index=0,
            ):
                if verdict_data["location_id"] == location.location_id:
                    pairs.append(
                        (
                            ModelVerdict(
                                location_id=location.location_id,
                                verdict=verdict_data["verdict"],
                            ),
                            location.expected,
                        )
                    )

    assert pairs
    hand_scored = score_adjudication(pairs)
    assert hand_scored.over_erasure_rate.numerator == scoring.over_erasure_rate.numerator
    assert hand_scored.over_erasure_rate.denominator == scoring.over_erasure_rate.denominator
    assert hand_scored.over_retention_rate.numerator == scoring.over_retention_rate.numerator
    assert hand_scored.mis_escalation_rate.numerator == scoring.mis_escalation_rate.numerator


def test_invalid_verdict_enum_rejected(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    tmp_path: Path,
    autonomous_config,
) -> None:
    export = load_export(export_dir)
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
    context = build_t1(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=AUTONOMOUS_RUNNER_ID,
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

    config = autonomous_config.model_copy(update={"cache_root": bad_cache})
    with pytest.raises(PairingValidationError) as exc_info:
        run_autonomous_sweep(seam=fake_seam, config=config)
    message = str(exc_info.value)
    assert subject.subject_id in message
    assert "txn-004" in message
    assert "0" in message or "sample_index" in message.lower()


def _cached_verdicts_for_subject(
    subject_id: str,
    cache_dir: Path,
    *,
    sample_index: int,
) -> list[dict]:
    export = load_export()
    subject = next(item for item in export.subjects if item.subject_id == subject_id)
    context = build_t1(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=AUTONOMOUS_RUNNER_ID,
        case_id=subject_id,
        sample_index=sample_index,
    )
    try:
        entry = read_cache(key, cache_dir)
    except CacheMissError:
        return []
    return entry.raw_response.get("verdicts", [])

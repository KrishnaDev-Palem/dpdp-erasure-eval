"""Acceptance tests for T1 request-only tier sweep."""

from __future__ import annotations

from pathlib import Path

from core.export import load_export
from core.model import FakeModelSeam
from core.scoring import score_adjudication
from core.types import VERDICT_LANES, ExpectedLabel, ModelVerdict
from runners.t1 import run_t1_sweep


def test_t1_full_sweep_all_subjects(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    export = load_export(export_dir)
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert result.tier == "t1"
    assert result.runner_id == "t1"
    assert len(result.samples) == 5
    for sample in result.samples:
        assert sample.total_subjects == len(export.subjects)
        assert sample.scoring.total_cases > 0


def test_t1_confusion_matrix_per_lane(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    matrix = result.samples[0].scoring.confusion_matrix
    assert set(matrix.keys()) == set(VERDICT_LANES)
    for row in matrix.values():
        assert set(row.keys()) == set(VERDICT_LANES)


def test_t1_standalone_rates_present(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    scoring = result.samples[0].scoring
    assert scoring.over_erasure_rate.denominator == scoring.total_cases
    assert scoring.over_retention_rate.denominator == scoring.total_cases
    assert scoring.mis_escalation_rate.denominator == scoring.total_cases


def test_t1_no_blended_accuracy(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    dumped = result.model_dump()
    assert "accuracy" not in dumped
    assert "micro_f1" not in dumped
    assert "blended_score" not in dumped
    for sample in result.samples:
        scoring_dump = sample.scoring.model_dump()
        assert "accuracy" not in scoring_dump
        assert "micro_f1" not in scoring_dump


def test_t1_offline_no_model_calls(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert fake_seam.adjudicate_calls == []


def test_t1_hand_calculated_rate_parity(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    """SC-004: T1 rates from raw pairs match embedded Rate values."""
    result = run_t1_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    sample = result.samples[0]
    scoring = sample.scoring

    pairs: list[tuple[ModelVerdict, ExpectedLabel]] = []
    export = load_export(export_dir)
    for subject in export.subjects:
        for location in subject.locations:
            for verdict_data in _cached_verdicts_for_subject(
                subject.subject_id, location.location_id, cache_dir, sample_index=0, tier="t1"
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


def _cached_verdicts_for_subject(
    subject_id: str,
    location_id: str,
    cache_dir: Path,
    *,
    sample_index: int,
    tier: str,
) -> list[dict]:
    from core.cache.store import make_cache_key, read_cache
    from core.context import build_t1
    from core.exceptions import CacheMissError
    from core.export import load_export

    export = load_export()
    subject = next(item for item in export.subjects if item.subject_id == subject_id)
    context = build_t1(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=tier,
        case_id=subject_id,
        sample_index=sample_index,
    )
    try:
        entry = read_cache(key, cache_dir)
    except CacheMissError:
        return []
    return entry.raw_response.get("verdicts", [])

"""Acceptance tests for T1 request-only tier sweep."""

from __future__ import annotations

from pathlib import Path

from core.export import load_export
from core.model import FakeModelSeam
from core.types import VERDICT_LANES
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

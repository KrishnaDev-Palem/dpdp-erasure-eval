"""Acceptance tests for T2 records-augmented tier sweep."""

from __future__ import annotations

from pathlib import Path

from core.context import build_t2
from core.export import load_export
from core.model import FakeModelSeam
from runners.t2 import run_t2_sweep


def test_t2_includes_location_records(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    export = load_export(export_dir)
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
    bundle = build_t2(subject.request, subject)
    assert bundle.locations
    for location in bundle.locations:
        assert "expected" not in location


def test_t2_full_sweep_independent_metrics(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    export = load_export(export_dir)
    result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert result.tier == "t2"
    assert result.runner_id == "t2"
    for sample in result.samples:
        assert sample.total_subjects == len(export.subjects)
        assert sample.scoring.total_cases > 0


def test_t2_metrics_independent_from_t1(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    from runners.t1 import run_t1_sweep

    t1 = run_t1_sweep(seam=FakeModelSeam(), export_dir=export_dir, cache_root=cache_dir)
    t2 = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert t1.runner_id != t2.runner_id
    assert t1.samples[0].scoring.total_cases > 0
    assert t2.samples[0].scoring.total_cases > 0

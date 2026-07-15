"""Acceptance tests for T3 rule-augmented tier sweep."""

from __future__ import annotations

from pathlib import Path

from core.context import build_t3
from core.export import load_export
from core.model import FakeModelSeam
from runners.t3 import run_t3_sweep
from tests.core.conftest import subject_with_tag


def test_t3_includes_rules_corpus(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    export = load_export(export_dir)
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t3(subject.request, subject, export.rules)
    assert bundle.retention_floors
    assert bundle.governance_map
    for location in bundle.locations:
        assert "expected" not in location


def test_t3_runner_id_cache_namespace(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t3_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert result.runner_id == "t3"
    assert result.tier == "t3"


def test_t3_full_sweep_all_subjects(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    export = load_export(export_dir)
    result = run_t3_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    for sample in result.samples:
        assert sample.total_subjects == len(export.subjects)

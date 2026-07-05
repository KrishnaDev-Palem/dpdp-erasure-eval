"""Acceptance tests for N=5 sampling and cross-sample variance in autonomous runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import CacheMissError
from core.model import FakeModelSeam
from runners.autonomous.runner import run_autonomous_sweep


def test_five_per_sample_rollups(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    assert len(result.samples) == 5
    for index, sample in enumerate(result.samples):
        assert sample.sample_index == index


def test_variance_summary_has_constancy_flags(fake_seam, autonomous_config) -> None:
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    variance = result.variance
    assert hasattr(variance.over_erasure, "constant_across_samples")
    assert hasattr(variance.over_retention, "constant_across_samples")
    assert hasattr(variance.mis_escalation, "constant_across_samples")
    assert len(variance.over_erasure.by_sample) == 5


def test_constant_across_samples_flags(fake_seam, autonomous_config) -> None:
    """Sample 1 cache override changes over-retention but not over-erasure."""
    result = run_autonomous_sweep(seam=fake_seam, config=autonomous_config)
    assert result.variance.over_erasure.constant_across_samples is True
    assert result.variance.over_retention.constant_across_samples is False


@pytest.mark.cache_miss
def test_offline_cache_miss_fails_explicitly(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    tmp_path: Path,
    autonomous_config,
) -> None:
    empty_cache = tmp_path / "cache"
    empty_cache.mkdir()
    config = autonomous_config.model_copy(update={"cache_root": empty_cache})
    with pytest.raises(CacheMissError) as exc_info:
        run_autonomous_sweep(seam=fake_seam, config=config)
    message = str(exc_info.value).lower()
    assert "autonomous" in message
    assert "mixed-fanout" in message or "floor-inside" in message
    assert fake_seam.adjudicate_calls == []

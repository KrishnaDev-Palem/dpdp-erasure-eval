"""Acceptance tests for env-driven runner configuration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from core.model import FakeModelSeam
from runners.spine import run_tier_sweep
from runners.types import SweepConfig


def test_model_id_from_environment(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "custom-model")
    monkeypatch.setenv("CACHE_MODE", "offline")

    custom_cache = tmp_path / "cache"
    shutil.copytree(cache_dir / "primary", custom_cache / "custom-model")

    config = SweepConfig(
        tier="t1",
        runner_id="t1",
        model_id=os.environ["MODEL_ID"],
        cache_mode=os.environ["CACHE_MODE"],
        sample_indices=[0, 1, 2, 3, 4],
        export_dir=export_dir,
        cache_root=custom_cache,
    )
    result = run_tier_sweep(tier="t1", seam=fake_seam, config=config)
    assert result.model_id == "custom-model"


def test_cache_mode_from_environment(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "primary")
    monkeypatch.setenv("CACHE_MODE", "offline")

    config = SweepConfig.from_env(export_dir=export_dir, cache_root=cache_dir, tier="t1")
    result = run_tier_sweep(tier="t1", seam=fake_seam, config=config)
    assert result.cache_mode == "offline"


def test_no_hardcoded_model_id_in_runner_source() -> None:
    spine_path = Path(__file__).resolve().parents[2] / "runners" / "spine.py"
    source = spine_path.read_text(encoding="utf-8")
    assert 'model_id="primary"' not in source
    assert "model_id = 'primary'" not in source


def test_sweep_config_accepts_three_or_five_samples(export_dir: Path, cache_dir: Path) -> None:
    for indices in ([0, 1, 2], [0, 1, 2, 3, 4]):
        config = SweepConfig(
            tier="t1",
            runner_id="t1",
            model_id="primary",
            cache_mode="offline",
            sample_indices=indices,
            export_dir=export_dir,
            cache_root=cache_dir,
        )
        assert config.sample_indices == indices


def test_sweep_config_rejects_other_sample_lists(export_dir: Path, cache_dir: Path) -> None:
    from pydantic import ValidationError

    for indices in ([0, 1], [0, 1, 2, 3], [1, 2, 3], [0, 1, 2, 3, 4, 5]):
        with pytest.raises(ValidationError, match=r"\[0, 1, 2\]"):
            SweepConfig(
                tier="t1",
                runner_id="t1",
                model_id="primary",
                cache_mode="offline",
                sample_indices=indices,
                export_dir=export_dir,
                cache_root=cache_dir,
            )


def test_from_env_default_is_five_samples(export_dir: Path, cache_dir: Path) -> None:
    config = SweepConfig.from_env(export_dir=export_dir, cache_root=cache_dir, tier="t1")
    assert config.sample_indices == [0, 1, 2, 3, 4]


def test_three_sample_sweep_against_committed_export(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    config = SweepConfig(
        tier="t1",
        runner_id="t1",
        model_id="primary",
        cache_mode="offline",
        sample_indices=[0, 1, 2],
        export_dir=export_dir,
        cache_root=cache_dir,
    )
    result = run_tier_sweep(tier="t1", seam=fake_seam, config=config)
    assert len(result.samples) == 3
    assert [sample.sample_index for sample in result.samples] == [0, 1, 2]
    assert len(result.variance.over_erasure.by_sample) == 3


def test_default_offline_sweep_is_five_samples(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_tier_sweep(tier="t1", seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert len(result.samples) == 5
    assert result.samples[0].grouped.by_cell == {}
    assert all(not groups for groups in result.samples[0].grouped.by_stratum.values())

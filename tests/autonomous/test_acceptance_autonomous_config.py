"""Acceptance tests for env-driven autonomous runner configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from runners.autonomous.types import AutonomousSweepConfig


def test_model_id_from_environment(
    export_dir: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "custom-model")
    monkeypatch.setenv("CACHE_MODE", "offline")
    config = AutonomousSweepConfig.from_env(export_dir=export_dir, cache_root=cache_dir)
    assert config.model_id == "custom-model"
    assert config.runner_id == "autonomous"


def test_cache_mode_from_environment(
    export_dir: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "primary")
    monkeypatch.setenv("CACHE_MODE", "offline")
    config = AutonomousSweepConfig.from_env(export_dir=export_dir, cache_root=cache_dir)
    assert config.cache_mode == "offline"


def test_autonomous_config_accepts_three_or_five_samples(
    export_dir: Path,
    cache_dir: Path,
) -> None:
    for indices in ([0, 1, 2], [0, 1, 2, 3, 4]):
        config = AutonomousSweepConfig(
            model_id="primary",
            cache_mode="offline",
            sample_indices=indices,
            export_dir=export_dir,
            cache_root=cache_dir,
        )
        assert config.sample_indices == indices


def test_autonomous_config_rejects_other_sample_lists(
    export_dir: Path,
    cache_dir: Path,
) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=r"\[0, 1, 2\]"):
        AutonomousSweepConfig(
            model_id="primary",
            cache_mode="offline",
            sample_indices=[0, 1],
            export_dir=export_dir,
            cache_root=cache_dir,
        )


def test_autonomous_from_env_default_is_five_samples(
    export_dir: Path,
    cache_dir: Path,
) -> None:
    config = AutonomousSweepConfig.from_env(export_dir=export_dir, cache_root=cache_dir)
    assert config.sample_indices == [0, 1, 2, 3, 4]


def test_three_sample_autonomous_sweep(fake_seam, autonomous_config) -> None:
    from runners.autonomous.runner import run_autonomous_sweep

    config = autonomous_config.model_copy(update={"sample_indices": [0, 1, 2]})
    result = run_autonomous_sweep(seam=fake_seam, config=config)
    assert len(result.samples) == 3
    assert [sample.sample_index for sample in result.samples] == [0, 1, 2]
    assert len(result.variance.over_erasure.by_sample) == 3


def test_no_hardcoded_model_id_in_autonomous_source(repo_root: Path) -> None:
    for rel in (
        "runners/autonomous/cache.py",
        "runners/autonomous/types.py",
    ):
        source = (repo_root / rel).read_text(encoding="utf-8")
        assert 'model_id="primary"' not in source
        assert "model_id = 'primary'" not in source
        assert "cache_mode = 'offline'" not in source
        assert 'cache_mode="offline"' not in source

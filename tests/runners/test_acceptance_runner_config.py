"""Acceptance tests for env-driven runner configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.model import FakeModelSeam
from runners.spine import run_tier_sweep
from runners.types import SweepConfig


def test_model_id_from_environment(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "custom-model")
    monkeypatch.setenv("CACHE_MODE", "offline")

    config = SweepConfig(
        tier="t1",
        runner_id="t1",
        model_id=os.environ["MODEL_ID"],
        cache_mode=os.environ["CACHE_MODE"],
        sample_indices=[0, 1, 2, 3, 4],
        export_dir=export_dir,
        cache_root=cache_dir,
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

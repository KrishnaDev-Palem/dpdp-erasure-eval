"""Acceptance tests for env-driven gate runner configuration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from core.model import FakeModelSeam
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from tests.gate.conftest import make_gate_sweep_config


def test_model_id_from_environment(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "custom-model")
    monkeypatch.setenv("CACHE_MODE", "offline")

    custom_cache = tmp_path / "cache"
    shutil.copytree(cache_dir / "primary", custom_cache / "custom-model")

    config = make_gate_sweep_config(
        model_id=os.environ["MODEL_ID"],
        cache_mode=os.environ["CACHE_MODE"],
        cache_root=custom_cache,
        slice_path=slice_path,
    )
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    assert result.model_id == "custom-model"


def test_cache_mode_from_environment(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "primary")
    monkeypatch.setenv("CACHE_MODE", "offline")

    config = make_gate_sweep_config(
        cache_root=cache_dir,
        slice_path=slice_path,
    )
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    assert result.cache_mode == "offline"


def test_no_hardcoded_model_id_in_gate_runner_source() -> None:
    runner_path = Path(__file__).resolve().parents[2] / "runners" / "adversarial_gate" / "runner.py"
    source = runner_path.read_text(encoding="utf-8")
    assert 'model_id="primary"' not in source
    assert "model_id = 'primary'" not in source


def test_gate_config_still_requires_exactly_five_samples(slice_path: Path, cache_dir: Path) -> None:
    from pydantic import ValidationError

    from runners.adversarial_gate.types import GateSweepConfig

    with pytest.raises(ValidationError, match="exactly"):
        GateSweepConfig(
            runner_id="adversarial_gate",
            model_id="primary",
            cache_mode="offline",
            sample_indices=[0, 1, 2],
            slice_path=slice_path,
            cache_root=cache_dir,
        )

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

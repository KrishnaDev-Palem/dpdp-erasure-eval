"""Shared fixtures for autonomous acceptance tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.export import load_export
from core.model import FakeModelSeam
from core.scoring import score_adjudication
from core.types import AdjudicationSubject, ExpectedLabel, ModelVerdict, Rate
from runners.autonomous.types import AutonomousSweepConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO_ROOT / "export"
CACHE_DIR = REPO_ROOT / "cache"


@pytest.fixture(autouse=True)
def _offline_cache_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_MODE", "offline")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def export_dir() -> Path:
    return EXPORT_DIR


@pytest.fixture
def cache_dir() -> Path:
    return CACHE_DIR


@pytest.fixture
def fake_seam() -> FakeModelSeam:
    return FakeModelSeam()


@pytest.fixture
def export_bundle(export_dir: Path):
    return load_export(export_dir)


from core.types import AdjudicationSubject, ErasureRequest
from tests.core.conftest import subject_with_tag


@pytest.fixture
def empty_locations_subject() -> AdjudicationSubject:
    return AdjudicationSubject(
        subject_id="synthetic-empty-subject",
        tags=["under_determined"],
        request=ErasureRequest(
            subject_id="synthetic-empty-subject",
            type="erasure",
            basis="explicit_erasure_right",
            as_of="2026-06-01",
        ),
        locations=[],
    )


def make_autonomous_sweep_config(
    *,
    model_id: str | None = None,
    cache_mode: str | None = None,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
) -> AutonomousSweepConfig:
    return AutonomousSweepConfig(
        model_id=model_id or os.environ.get("MODEL_ID", "primary"),
        cache_mode=cache_mode or os.environ.get("CACHE_MODE", "offline"),
        sample_indices=[0, 1, 2, 3, 4],
        export_dir=export_dir,
        cache_root=cache_root,
    )


@pytest.fixture
def autonomous_config(cache_dir: Path, export_dir: Path) -> AutonomousSweepConfig:
    return make_autonomous_sweep_config(export_dir=export_dir, cache_root=cache_dir)


def build_hand_calculated_rates(
    pairs: list[tuple[ModelVerdict, ExpectedLabel]],
) -> dict[str, Rate]:
    """Hand-calculated over-erasure, over-retention, and mis-escalation rates for SC-004."""
    scoring = score_adjudication(pairs)
    return {
        "over_erasure": scoring.over_erasure_rate,
        "over_retention": scoring.over_retention_rate,
        "mis_escalation": scoring.mis_escalation_rate,
    }

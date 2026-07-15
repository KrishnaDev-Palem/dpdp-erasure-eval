"""Shared fixtures for runner acceptance tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.export import load_export
from core.model import FakeModelSeam
from core.types import AdjudicationSubject, Tier

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


def make_sweep_config(
    *,
    tier: Tier = "t1",
    model_id: str | None = None,
    cache_mode: str | None = None,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
):
    """Build a minimal SweepConfig once runner types exist."""
    from runners.types import SweepConfig

    return SweepConfig(
        tier=tier,
        runner_id=tier,
        model_id=model_id or os.environ.get("MODEL_ID", "primary"),
        cache_mode=cache_mode or os.environ.get("CACHE_MODE", "offline"),
        sample_indices=[0, 1, 2, 3, 4],
        export_dir=export_dir,
        cache_root=cache_root,
    )


@pytest.fixture
def sweep_config(cache_dir: Path, export_dir: Path):
    return make_sweep_config(export_dir=export_dir, cache_root=cache_dir)

"""Shared fixtures for adversarial-gate acceptance tests."""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from core.model import FakeModelSeam
from core.types import AdversarialScoringResult, Rate

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO_ROOT / "export"
CACHE_DIR = REPO_ROOT / "cache"
SLICE_DIR = REPO_ROOT / "fixtures" / "adversarial_slice"
SLICE_PATH = SLICE_DIR / "cases.yaml"

ATTACK_FAMILIES = (
    "direct_override",
    "authority_spoof",
    "obfuscated_injection",
    "scope_expansion",
    "exfiltration",
)

WILSON_Z_95 = 1.96
WILSON_TOLERANCE = 1e-9


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
def slice_path() -> Path:
    return SLICE_PATH


@pytest.fixture
def slice_dir() -> Path:
    return SLICE_DIR


@pytest.fixture
def fake_seam() -> FakeModelSeam:
    return FakeModelSeam()


def make_gate_sweep_config(
    *,
    model_id: str | None = None,
    cache_mode: str | None = None,
    slice_path: Path | None = None,
    cache_root: Path | None = None,
    verify_export_seeds: bool = True,
):
    """Build a minimal GateSweepConfig once gate types exist."""
    from runners.adversarial_gate.types import GateSweepConfig

    return GateSweepConfig(
        runner_id="adversarial_gate",
        model_id=model_id or os.environ.get("MODEL_ID", "primary"),
        cache_mode=cache_mode or os.environ.get("CACHE_MODE", "offline"),
        sample_indices=[0, 1, 2, 3, 4],
        slice_path=slice_path or SLICE_PATH,
        cache_root=cache_root,
        verify_export_seeds=verify_export_seeds,
    )


@pytest.fixture
def gate_config(cache_dir: Path, slice_path: Path):
    return make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)


def hand_calculate_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def hand_calculate_wilson_interval(
    rate: Rate,
    *,
    confidence_level: float = 0.95,
    z: float = WILSON_Z_95,
) -> tuple[float | None, float | None]:
    """Independent Wilson score interval for acceptance parity checks."""
    if rate.denominator == 0:
        return None, None
    n = rate.denominator
    p_hat = rate.numerator / n
    z2 = z * z
    center = (p_hat + z2 / (2 * n)) / (1 + z2 / n)
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))) / (1 + z2 / n)
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


def make_hand_crafted_scoring_fixture() -> AdversarialScoringResult:
    """Representative scoring result for Wilson and per-family table tests."""
    return AdversarialScoringResult(
        detection_rate=Rate(numerator=38, denominator=45, value=38 / 45),
        false_alarm_rate=Rate(numerator=3, denominator=45, value=3 / 45),
        per_family={
            "direct_override": Rate(numerator=8, denominator=9, value=8 / 9),
            "authority_spoof": Rate(numerator=7, denominator=9, value=7 / 9),
            "obfuscated_injection": Rate(numerator=8, denominator=9, value=8 / 9),
            "scope_expansion": Rate(numerator=7, denominator=9, value=7 / 9),
            "exfiltration": Rate(numerator=8, denominator=9, value=8 / 9),
        },
    )


def make_zero_attack_scoring_fixture() -> AdversarialScoringResult:
    return AdversarialScoringResult(
        detection_rate=Rate(numerator=0, denominator=0, value=None),
        false_alarm_rate=Rate(numerator=2, denominator=10, value=0.2),
        per_family={},
    )


def make_zero_benign_scoring_fixture() -> AdversarialScoringResult:
    return AdversarialScoringResult(
        detection_rate=Rate(numerator=5, denominator=10, value=0.5),
        false_alarm_rate=Rate(numerator=0, denominator=0, value=None),
        per_family={
            "direct_override": Rate(numerator=5, denominator=10, value=0.5),
        },
    )

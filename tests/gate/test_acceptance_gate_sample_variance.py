"""Acceptance tests for N=5 sampling and cross-sample variance in gate sweeps."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import CacheMissError
from core.model import FakeModelSeam
from core.scoring import score_adversarial
from core.types import ClassifierResult
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from runners.adversarial_gate.slice_loader import load_extended_slice
from tests.gate.conftest import make_gate_sweep_config


def test_five_distinct_per_sample_rollups(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    config = make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    assert len(result.samples) == 5
    for index, sample in enumerate(result.samples):
        assert sample.sample_index == index


def test_variance_summary_has_constancy_flags(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    config = make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    variance = result.variance
    assert hasattr(variance.detection, "constant_across_samples")
    assert hasattr(variance.false_alarm, "constant_across_samples")
    assert len(variance.detection.by_sample) == 5
    assert len(variance.false_alarm.by_sample) == 5


def test_distinct_cache_keys_per_sample_index(
    cache_dir: Path,
    slice_path: Path,
) -> None:
    from runners.adversarial_gate.cache import make_gate_cache_key

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    keys = [
        make_gate_cache_key(
            text=sample_case.text,
            model_id="primary",
            case_id=sample_case.case_id,
            sample_index=index,
        )
        for index in range(5)
    ]
    hashes = {key.prompt_hash for key in keys}
    assert len(hashes) == 1
    sample_indices = {key.sample_index for key in keys}
    assert sample_indices == {0, 1, 2, 3, 4}
    assert len(keys) == len({(key.runner_id, key.case_id, key.sample_index) for key in keys})


@pytest.mark.cache_miss
def test_offline_cache_miss_fails_explicitly(
    fake_seam: FakeModelSeam,
    slice_path: Path,
    tmp_path: Path,
) -> None:
    empty_cache = tmp_path / "cache"
    empty_cache.mkdir()
    config = make_gate_sweep_config(cache_root=empty_cache, slice_path=slice_path)
    with pytest.raises(CacheMissError) as exc_info:
        run_adversarial_gate_sweep(seam=fake_seam, config=config)
    message = str(exc_info.value).lower()
    assert "adversarial_gate" in message
    assert fake_seam.classify_calls == []


def test_hand_calculated_rate_parity(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    """SC-004: rates from raw pairs match embedded Rate values."""
    config = make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    sample = result.samples[0]
    scoring = sample.scoring

    pairs = _pairs_from_cache(slice_path, cache_dir, sample_index=0)
    assert pairs
    hand_scored = score_adversarial(pairs)
    assert hand_scored.detection_rate.numerator == scoring.detection_rate.numerator
    assert hand_scored.detection_rate.denominator == scoring.detection_rate.denominator
    assert hand_scored.false_alarm_rate.numerator == scoring.false_alarm_rate.numerator
    assert hand_scored.false_alarm_rate.denominator == scoring.false_alarm_rate.denominator


def test_variance_rates_match_sample_scoring(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    config = make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    for index, sample in enumerate(result.samples):
        detection_at_sample = result.variance.detection.by_sample[index]
        false_alarm_at_sample = result.variance.false_alarm.by_sample[index]
        assert detection_at_sample.sample_index == index
        assert false_alarm_at_sample.sample_index == index
        assert detection_at_sample.rate.numerator == sample.scoring.detection_rate.numerator
        assert false_alarm_at_sample.rate.numerator == sample.scoring.false_alarm_rate.numerator


def test_constant_across_samples_flags(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    config = make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)
    result = run_adversarial_gate_sweep(seam=fake_seam, config=config)
    assert result.variance.detection.constant_across_samples is True
    assert isinstance(result.variance.false_alarm.constant_across_samples, bool)


def _pairs_from_cache(
    slice_path: Path,
    cache_dir: Path,
    *,
    sample_index: int,
) -> list[tuple[ClassifierResult, object]]:
    from core.cache.store import read_cache
    from core.exceptions import CacheMissError
    from runners.adversarial_gate.cache import make_gate_cache_key

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    pairs: list[tuple[ClassifierResult, object]] = []
    for case in cases:
        key = make_gate_cache_key(
            text=case.text,
            model_id="primary",
            case_id=case.case_id,
            sample_index=sample_index,
        )
        try:
            entry = read_cache(key, cache_dir)
        except CacheMissError:
            continue
        outcome = entry.raw_response.get("outcome")
        pairs.append((ClassifierResult(outcome=outcome), case))
    return pairs

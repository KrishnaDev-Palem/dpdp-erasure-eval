"""Acceptance tests for N=5 sampling and cross-sample variance."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import CacheMissError
from core.export import load_export
from core.model import FakeModelSeam
from core.scoring import score_adjudication
from core.types import ExpectedLabel, ModelVerdict
from runners.t2 import run_t2_sweep


def test_five_per_sample_rollups(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert len(result.samples) == 5
    for index, sample in enumerate(result.samples):
        assert sample.sample_index == index


def test_variance_summary_has_constancy_flags(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    variance = result.variance
    assert hasattr(variance.over_erasure, "constant_across_samples")
    assert hasattr(variance.over_retention, "constant_across_samples")
    assert hasattr(variance.mis_escalation, "constant_across_samples")
    assert len(variance.over_erasure.by_sample) == 5


@pytest.mark.cache_miss
def test_offline_cache_miss_fails_explicitly(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    tmp_path: Path,
) -> None:
    empty_cache = tmp_path / "cache"
    empty_cache.mkdir()
    with pytest.raises(CacheMissError) as exc_info:
        run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=empty_cache)
    message = str(exc_info.value).lower()
    assert "t1" in message or "mixed-fanout" in message or "floor-inside" in message
    assert fake_seam.adjudicate_calls == []


def test_hand_calculated_rate_parity(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    """SC-004: rates from raw pairs match embedded Rate values."""
    result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    sample = result.samples[0]
    scoring = sample.scoring

    pairs: list[tuple[ModelVerdict, ExpectedLabel]] = []
    export = load_export(export_dir)
    for subject in export.subjects:
        for location in subject.locations:
            for verdict_data in _cached_verdicts_for_subject(
                subject.subject_id, location.location_id, cache_dir, sample_index=0, tier="t2"
            ):
                if verdict_data["location_id"] == location.location_id:
                    pairs.append(
                        (
                            ModelVerdict(
                                location_id=location.location_id,
                                verdict=verdict_data["verdict"],
                            ),
                            location.expected,
                        )
                    )

    if pairs:
        hand_scored = score_adjudication(pairs)
        assert hand_scored.over_erasure_rate.numerator == scoring.over_erasure_rate.numerator
        assert hand_scored.over_erasure_rate.denominator == scoring.over_erasure_rate.denominator
        assert hand_scored.over_retention_rate.numerator == scoring.over_retention_rate.numerator
        assert hand_scored.mis_escalation_rate.numerator == scoring.mis_escalation_rate.numerator


def _cached_verdicts_for_subject(
    subject_id: str,
    location_id: str,
    cache_dir: Path,
    *,
    sample_index: int,
    tier: str,
) -> list[dict]:
    from core.cache.store import make_cache_key, read_cache
    from core.context import build_t2
    from core.export import load_export

    export = load_export()
    subject = next(item for item in export.subjects if item.subject_id == subject_id)
    context = build_t2(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id=tier,
        case_id=subject_id,
        sample_index=sample_index,
    )
    try:
        entry = read_cache(key, cache_dir)
    except CacheMissError:
        return []
    return entry.raw_response.get("verdicts", [])


def test_variance_rates_match_sample_scoring(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    for index, sample in enumerate(result.samples):
        rate_at_sample = result.variance.over_erasure.by_sample[index]
        assert rate_at_sample.sample_index == index
        assert rate_at_sample.rate.numerator == sample.scoring.over_erasure_rate.numerator
        assert rate_at_sample.rate.denominator == sample.scoring.over_erasure_rate.denominator


def test_constant_across_samples_flags(
    fake_seam: FakeModelSeam,
    export_dir: Path,
    cache_dir: Path,
) -> None:
    """Sample 1 cache override changes over-retention but not over-erasure."""
    result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    assert result.variance.over_erasure.constant_across_samples is True
    assert result.variance.over_retention.constant_across_samples is False

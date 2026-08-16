"""Acceptance tests for verdict translation at the pairing boundary.

Spec section 5: the inverse is rebuilt per subject and verdicts translate back to real
location ids before `runners/pairing.py` sees them. Two things arrive opaque, not one —
the verdict ids off the model or the cache entry, and the `pairing_location_ids` every
caller derives from `context.locations` — and `score_adjudication_grouped` joins each pair
back to its `LabeledLocation` with a bare lookup, so an untranslated id lands there as a
`KeyError` rather than a soft miss. These cover all three `pair_subject_verdicts` callers.

Round-trip parity against the pre-change pair set is spec criterion 4 and lives with the
isolation suite; what is asserted here is that each site resolves both inputs, that an
identifier with no inverse raises rather than pairing silently, and that the cache entry
itself stays opaque on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cache.store import CacheStore, make_cache_key, write_cache
from core.context import build_t1
from core.model import FakeModelSeam
from core.pseudonymize import opaque_case_id, opaque_location_id
from core.tools import build_retrieval_tool_registry
from core.types import AdjudicationSubject, CacheEntry
from report.retrieval_split import build_retrieval_split_report
from runners.autonomous.cache import resolve_autonomous_entry
from runners.autonomous.runner import run_autonomous_sweep
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID, AutonomousSweepConfig
from runners.spine import run_tier_sweep
from runners.translation import (
    VerdictTranslationError,
    location_id_inverse,
    to_real_location_id,
)
from runners.types import THREE_SAMPLE_INDICES, SweepConfig

MODEL_ID = "primary"
RECORDED_AT = "2026-07-03T12:00:00Z"
UNKNOWN_TOKEN = "loc-ffffffffffff"


def _first_subject_with_locations(bundle) -> AdjudicationSubject:
    return next(subject for subject in bundle.subjects if subject.locations)


def _real_location_ids(subject: AdjudicationSubject) -> list[str]:
    return [location.location_id for location in subject.locations]


def _opaque_verdicts(subject: AdjudicationSubject, *, flip_first: bool = False) -> list[dict]:
    """The verdict list a model that only ever saw opaque ids returns."""
    verdicts = []
    for index, location in enumerate(subject.locations):
        verdict = location.expected.verdict
        if flip_first and index == 0:
            verdict = "erase" if verdict != "erase" else "retain"
        verdicts.append(
            {
                "location_id": opaque_location_id(location.location_id),
                "verdict": verdict,
                "detail": None,
            }
        )
    return verdicts


def _floor_trace(subject: AdjudicationSubject) -> list[dict]:
    """One `get_retention_floors` trace covering every floor the subject cites."""
    floor_ids = sorted(
        {floor_id for location in subject.locations for floor_id in location.expected.cited_floors}
    )
    return [
        {
            "sequence": 0,
            "tool_name": "get_retention_floors",
            "arguments": {},
            "result_summary": {"floor_count": len(floor_ids), "floor_ids": floor_ids},
        }
    ]


def _write_entry(
    cache_root: Path,
    subject: AdjudicationSubject,
    *,
    runner_id: str,
    sample_index: int,
    verdicts: list[dict],
    tool_calls: list[dict] | None = None,
) -> None:
    context = build_t1(subject.request, subject)
    key = make_cache_key(
        context=context,
        model_id=MODEL_ID,
        runner_id=runner_id,
        case_id=subject.subject_id,
        sample_index=sample_index,
    )
    write_cache(
        CacheEntry(
            key=key,
            raw_response={"verdicts": verdicts},
            recorded_at=RECORDED_AT,
            tool_calls=tool_calls or [],
        ),
        cache_root,
    )


def _seed_opaque_cache(
    cache_root: Path,
    bundle,
    *,
    runner_id: str,
    flip_first: bool = False,
    with_traces: bool = False,
) -> None:
    """Seed every subject at three samples the way a post-substitution sweep would."""
    for subject in bundle.subjects:
        if not subject.locations:
            continue
        verdicts = _opaque_verdicts(subject, flip_first=flip_first)
        tool_calls = _floor_trace(subject) if with_traces else []
        for sample_index in THREE_SAMPLE_INDICES:
            _write_entry(
                cache_root,
                subject,
                runner_id=runner_id,
                sample_index=sample_index,
                verdicts=verdicts,
                tool_calls=tool_calls,
            )


def _resolve(subject: AdjudicationSubject, store: CacheStore, bundle, seam=None):
    return resolve_autonomous_entry(
        context=build_t1(subject.request, subject),
        subject=subject,
        sample_index=0,
        model_id=MODEL_ID,
        store=store,
        seam=seam or FakeModelSeam(),
        tool_registry=build_retrieval_tool_registry(bundle),
    )


def test_autonomous_cache_read_translates_both_verdict_lists(
    export_bundle,
    tmp_path: Path,
) -> None:
    """The sweep pairs on `raw_verdicts`, so the parsed list alone is not enough."""
    subject = _first_subject_with_locations(export_bundle)
    cache_root = tmp_path / "cache"
    _write_entry(
        cache_root,
        subject,
        runner_id=AUTONOMOUS_RUNNER_ID,
        sample_index=0,
        verdicts=_opaque_verdicts(subject),
    )

    session = _resolve(subject, CacheStore(root=cache_root, cache_mode="offline"), export_bundle)

    assert [item.location_id for item in session.verdicts] == _real_location_ids(subject)
    assert [item["location_id"] for item in session.raw_verdicts] == _real_location_ids(subject)


@pytest.mark.refresh
def test_autonomous_refresh_translates_and_leaves_the_entry_opaque(
    export_bundle,
    tmp_path: Path,
) -> None:
    """The entry records what the model returned; translation is in-memory, after the write."""
    subject = _first_subject_with_locations(export_bundle)
    cache_root = tmp_path / "cache"
    store = CacheStore(root=cache_root, cache_mode="refresh")

    session = _resolve(subject, store, export_bundle)

    assert [item.location_id for item in session.verdicts] == _real_location_ids(subject)
    assert [item["location_id"] for item in session.raw_verdicts] == _real_location_ids(subject)

    entry = store.get(
        make_cache_key(
            context=build_t1(subject.request, subject),
            model_id=MODEL_ID,
            runner_id=AUTONOMOUS_RUNNER_ID,
            case_id=subject.subject_id,
            sample_index=0,
        )
    )
    assert [item["location_id"] for item in entry.raw_response["verdicts"]] == [
        opaque_location_id(location_id) for location_id in _real_location_ids(subject)
    ]


def test_tier_sweep_over_opaque_cache_pairs_scores_and_groups(
    fake_seam: FakeModelSeam,
    export_bundle,
    export_dir: Path,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache"
    _seed_opaque_cache(cache_root, export_bundle, runner_id="t1")

    result = run_tier_sweep(
        tier="t1",
        seam=fake_seam,
        config=SweepConfig(
            tier="t1",
            runner_id="t1",
            model_id=MODEL_ID,
            cache_mode="offline",
            sample_indices=list(THREE_SAMPLE_INDICES),
            export_dir=export_dir,
            cache_root=cache_root,
        ),
    )

    rollup = result.samples[0]
    expected_pairs = sum(len(subject.locations) for subject in export_bundle.subjects)
    assert rollup.scoring.total_cases == expected_pairs
    # Every seeded verdict is the expected one, so a pair landing on the wrong location
    # would have to show up as a non-zero error rate here.
    assert rollup.scoring.over_erasure_rate.numerator == 0
    assert rollup.scoring.over_retention_rate.numerator == 0
    assert rollup.scoring.mis_escalation_rate.numerator == 0
    # The grouped join is a bare lookup keyed on real ids: an opaque id reaching it is a
    # KeyError, not a soft miss. This table is the canary for translation applied too late.
    assert set(rollup.grouped.by_cell) == {
        location.cell_id
        for subject in export_bundle.subjects
        for location in subject.locations
        if location.cell_id is not None
    }
    assert fake_seam.adjudicate_calls == []


def test_autonomous_sweep_over_opaque_cache_pairs_scores_and_groups(
    fake_seam: FakeModelSeam,
    export_bundle,
    export_dir: Path,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache"
    _seed_opaque_cache(cache_root, export_bundle, runner_id=AUTONOMOUS_RUNNER_ID)

    result = run_autonomous_sweep(
        seam=fake_seam,
        config=AutonomousSweepConfig(
            model_id=MODEL_ID,
            cache_mode="offline",
            sample_indices=list(THREE_SAMPLE_INDICES),
            export_dir=export_dir,
            cache_root=cache_root,
        ),
    )

    rollup = result.samples[0]
    assert rollup.scoring.total_cases == sum(
        len(subject.locations) for subject in export_bundle.subjects
    )
    assert rollup.scoring.over_erasure_rate.numerator == 0
    assert rollup.grouped.by_cell
    assert fake_seam.adjudicate_calls == []


def test_retrieval_split_over_opaque_cache(
    export_bundle,
    export_dir: Path,
    tmp_path: Path,
) -> None:
    """The third `pair_subject_verdicts` caller, on the same two opaque inputs."""
    cache_root = tmp_path / "cache"
    _seed_opaque_cache(
        cache_root,
        export_bundle,
        runner_id=AUTONOMOUS_RUNNER_ID,
        flip_first=True,
        with_traces=True,
    )

    report = build_retrieval_split_report(
        export_dir=export_dir,
        cache_root=cache_root,
        model_id=MODEL_ID,
        cache_mode="offline",
        sample_index=0,
        sample_indices=list(THREE_SAMPLE_INDICES),
    )

    scored_subjects = [subject for subject in export_bundle.subjects if subject.locations]
    assert report.total_incorrect == len(scored_subjects)
    assert (
        report.retrieval_failure.numerator + report.reasoning_failure.numerator
        == report.total_incorrect
    )
    # Every trace returns the floors its subject cites, so no error is a missing fetch.
    assert report.reasoning_failure.numerator == report.total_incorrect
    assert sum(lane.incorrect_count for lane in report.per_lane) == report.total_incorrect


def test_identifier_without_an_inverse_raises(export_bundle) -> None:
    subject = _first_subject_with_locations(export_bundle)
    inverse = location_id_inverse(subject)

    with pytest.raises(VerdictTranslationError):
        to_real_location_id(UNKNOWN_TOKEN, inverse)
    # A real id here is a pre-substitution response, not a shortcut past translation.
    with pytest.raises(VerdictTranslationError):
        to_real_location_id(subject.locations[0].location_id, inverse)
    # The inverse resolves locations only; the subject's own case token is not one.
    with pytest.raises(VerdictTranslationError):
        to_real_location_id(opaque_case_id(subject.subject_id), inverse)


def test_unknown_token_in_a_cache_entry_raises_rather_than_pairing(
    export_bundle,
    tmp_path: Path,
) -> None:
    subject = _first_subject_with_locations(export_bundle)
    verdicts = _opaque_verdicts(subject)
    verdicts[0] = {**verdicts[0], "location_id": UNKNOWN_TOKEN}
    cache_root = tmp_path / "cache"
    _write_entry(
        cache_root,
        subject,
        runner_id=AUTONOMOUS_RUNNER_ID,
        sample_index=0,
        verdicts=verdicts,
    )

    with pytest.raises(VerdictTranslationError) as exc_info:
        _resolve(subject, CacheStore(root=cache_root, cache_mode="offline"), export_bundle)
    assert UNKNOWN_TOKEN in str(exc_info.value)

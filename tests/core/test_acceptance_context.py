"""Acceptance tests for tier context assembly."""

from __future__ import annotations

from core.cache import prompt_hash
from core.context import build_t1, build_t2, build_t3
from core.export import load_export
from core.types import AdjudicationSubject, ErasureRequest
from tests.core.conftest import subject_with_tag


def test_t1_request_only() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t1(subject.request, subject)
    assert bundle.tier == "t1"
    assert bundle.request.subject_id == subject.subject_id
    assert bundle.locations == []
    assert bundle.retention_floors == []
    assert bundle.governance_map == []


def test_t2_records_without_expected() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t2(subject.request, subject)
    assert bundle.tier == "t2"
    assert bundle.locations
    for location in bundle.locations:
        assert "expected" not in location
        assert "location_id" in location


def test_t3_adds_rules_corpus() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t3(subject.request, subject, export.rules)
    assert bundle.tier == "t3"
    assert len(bundle.retention_floors) == 5
    assert bundle.governance_map


def test_adjacent_tier_delta() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    t1 = build_t1(subject.request, subject)
    t2 = build_t2(subject.request, subject)
    t3 = build_t3(subject.request, subject, export.rules)
    assert t1.locations == []
    assert t2.locations and not t2.retention_floors
    assert t2.locations == t3.locations
    assert t3.retention_floors and t3.governance_map


def test_ground_truth_excluded() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    for builder in (build_t2,):
        bundle = builder(subject.request, subject)
        serialized = bundle.model_dump(mode="json")
        assert "expected" not in serialized


def test_zero_locations_subject_does_not_invent_records() -> None:
    subject = AdjudicationSubject(
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
    assert subject.locations == []
    t2 = build_t2(subject.request, subject)
    t3 = build_t3(subject.request, subject, load_export().rules)
    assert t2.locations == []
    assert t3.locations == []


def test_bundles_hash_consistently() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    t1 = build_t1(subject.request, subject)
    assert prompt_hash(t1) == prompt_hash(build_t1(subject.request, subject))

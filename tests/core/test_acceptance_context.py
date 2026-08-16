"""Acceptance tests for tier context assembly."""

from __future__ import annotations

import json

import pytest

from core.cache import prompt_hash
from core.context import build_t1, build_t2, build_t3
from core.export import load_export
from core.pseudonymize import opaque_case_id, opaque_location_id
from core.types import AdjudicationSubject, ErasureRequest
from tests.conftest import ARCHIVE_V1_EXPORT_DIR
from tests.core.conftest import EXPORT_DIR, subject_with_tag


def _archive_export():
    return load_export(ARCHIVE_V1_EXPORT_DIR)


@pytest.fixture(scope="module")
def coverage_export():
    """The committed 350-subject export — the one that names cases after design cells."""
    return load_export(EXPORT_DIR)


def test_t1_request_and_location_ids_only() -> None:
    export = _archive_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t1(subject.request, subject)
    assert bundle.tier == "t1"
    assert bundle.request.subject_id == opaque_case_id(subject.subject_id)
    assert bundle.locations == [
        {"location_id": opaque_location_id(location.location_id)} for location in subject.locations
    ]
    assert bundle.retention_floors == []
    assert bundle.governance_map == []


def test_t2_records_without_expected() -> None:
    export = _archive_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t2(subject.request, subject)
    assert bundle.tier == "t2"
    assert bundle.locations
    for location in bundle.locations:
        assert "expected" not in location
        assert "strata" not in location
        assert "cell_id" not in location
        assert "location_id" in location


def test_t3_adds_rules_corpus() -> None:
    export = _archive_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t3(subject.request, subject, export.rules)
    assert bundle.tier == "t3"
    assert len(bundle.retention_floors) == 5
    assert bundle.governance_map


def test_adjacent_tier_delta() -> None:
    export = _archive_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    t1 = build_t1(subject.request, subject)
    t2 = build_t2(subject.request, subject)
    t3 = build_t3(subject.request, subject, export.rules)
    # T1 carries the location ids and nothing else; T2 adds the record payload.
    assert t1.locations and all(set(item) == {"location_id"} for item in t1.locations)
    assert t2.locations and not t2.retention_floors
    assert [item["location_id"] for item in t1.locations] == [
        item["location_id"] for item in t2.locations
    ]
    assert t2.locations == t3.locations
    assert t3.retention_floors and t3.governance_map


def test_ground_truth_excluded() -> None:
    export = _archive_export()
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
    t3 = build_t3(subject.request, subject, _archive_export().rules)
    assert t2.locations == []
    assert t3.locations == []


def test_bundles_hash_consistently() -> None:
    export = _archive_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    t1 = build_t1(subject.request, subject)
    assert prompt_hash(t1) == prompt_hash(build_t1(subject.request, subject))


def test_t1_carries_one_opaque_location_id_per_export_location(coverage_export) -> None:
    """T1 is no longer request-only: the bundle states the scope the model must adjudicate.

    Previously `build_t1` returned `locations=[]` and the prompt builder reached into the
    export to fill the `Required location_ids` line. The ids are now in the bundle, opaque.
    """
    for subject in coverage_export.subjects:
        bundle = build_t1(subject.request, subject)
        assert len(bundle.locations) == len(subject.locations)
        assert bundle.locations == [
            {"location_id": opaque_location_id(location.location_id)}
            for location in subject.locations
        ]


def test_t2_t3_locations_drop_eval_only_keys_and_cell_names(coverage_export) -> None:
    """The field scrub and the token substitution are both required, and both hold.

    The scrub removes the eval-only keys; substitution removes the design-cell name that
    lives inside identifier strings, which no field list reaches.
    """
    cell_ids = {
        location.cell_id
        for subject in coverage_export.subjects
        for location in subject.locations
        if location.cell_id
    }
    assert cell_ids, "committed export must carry cell_ids for this test to mean anything"

    for subject in coverage_export.subjects:
        for bundle in (
            build_t2(subject.request, subject),
            build_t3(subject.request, subject, coverage_export.rules),
        ):
            serialized = json.dumps(bundle.model_dump(mode="json")["locations"])
            for key in ("expected", "strata", "cell_id"):
                assert f'"{key}"' not in serialized, f"{key} survived in {subject.subject_id}"
            for cell_id in cell_ids:
                assert cell_id not in serialized, (
                    f"cell name {cell_id!r} survived in {subject.subject_id}"
                )


def test_t3_floors_and_governance_are_byte_identical(coverage_export) -> None:
    """Spec section 9: floors and governance entries are domain content, not identifiers.

    They are not routed through `substitute`, and this asserts they came through whole.
    """
    subject = coverage_export.subjects[0]
    bundle = build_t3(subject.request, subject, coverage_export.rules)
    assert bundle.retention_floors == list(coverage_export.rules.retention_floors)
    assert bundle.governance_map == list(coverage_export.rules.governance_map)

    dumped = bundle.model_dump(mode="json")
    assert dumped["retention_floors"] == [
        item.model_dump(mode="json") for item in coverage_export.rules.retention_floors
    ]
    assert dumped["governance_map"] == [
        item.model_dump(mode="json") for item in coverage_export.rules.governance_map
    ]
    assert {item["floor_id"] for item in dumped["retention_floors"]} == {
        "pmla_kyc",
        "gst",
        "income_tax",
        "companies_act",
        "sebi",
    }


def test_bundle_request_stays_an_erasure_request(coverage_export) -> None:
    """`substitute` returns plain dicts; the bundle must still hold a validated model."""
    subject = coverage_export.subjects[0]
    for bundle in (
        build_t1(subject.request, subject),
        build_t2(subject.request, subject),
        build_t3(subject.request, subject, coverage_export.rules),
    ):
        assert isinstance(bundle.request, ErasureRequest)
        assert bundle.request.subject_id == opaque_case_id(subject.subject_id)
        assert bundle.request.basis == subject.request.basis
        assert bundle.request.type == subject.request.type
        assert bundle.request.as_of == subject.request.as_of

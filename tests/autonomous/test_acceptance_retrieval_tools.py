"""Acceptance tests for filesystem-backed retrieval tools (US1)."""

from __future__ import annotations

import json

import pytest

from core.context import build_t2, build_t3
from core.export import load_export
from core.pseudonymize import build_substitution_map, opaque_case_id, substitute
from core.tools import build_retrieval_tool_registry
from tests.autonomous.conftest import EXPORT_DIR
from tests.core.conftest import subject_with_tag


@pytest.fixture(scope="module")
def coverage_export():
    """The committed 350-subject export — the one that names cases after design cells."""
    return load_export(EXPORT_DIR)


def _cell_ids(bundle) -> set[str]:
    return {
        location.cell_id
        for subject in bundle.subjects
        for location in subject.locations
        if location.cell_id
    }


@pytest.mark.parametrize(
    "subject_id",
    ["subj-mixed-fanout", "subj-payment-inside-floors"],
)
def test_get_location_records_matches_t2(subject_id: str, archive_export_bundle) -> None:
    """T2 equivalence still holds, now against the substituted bundle rather than the export.

    The tool and `build_t2` scrub the same eval-only fields and then run the same
    substitution, so their payloads stay interchangeable — which is the property the
    autonomous setting is meant to isolate.
    """
    registry = build_retrieval_tool_registry(archive_export_bundle)
    subject = next(item for item in archive_export_bundle.subjects if item.subject_id == subject_id)
    t2 = build_t2(subject.request, subject)
    result = registry.invoke("get_location_records", {"subject_id": opaque_case_id(subject_id)})
    assert result["locations"] == t2.locations
    assert "expected" not in str(result)
    assert subject_id not in json.dumps(result)


@pytest.mark.skip(reason="real export has no zero-location subjects")
def test_get_location_records_empty_locations(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    result = registry.invoke(
        "get_location_records",
        {"subject_id": opaque_case_id("synthetic-empty-subject")},
    )
    assert result["locations"] == []
    assert "error" not in result


def test_get_location_records_returns_the_right_subject_with_every_identifier_opaque(
    coverage_export,
) -> None:
    """Tool results enter context after the bundle is built, so they carry their own map.

    Asserted over all 350 subjects: the payload is that subject's own, and no design-cell
    name reaches it through any of the eight identifier paths — `location_id`, the derived
    `txn_id` / `doc_id` / `consent_id` / `file_path`, the echoed `subject_id`, or the
    nested `parent_customer.customer_id`.
    """
    registry = build_retrieval_tool_registry(coverage_export)
    cell_ids = _cell_ids(coverage_export)
    assert cell_ids, "committed export must carry cell_ids for this test to mean anything"

    for subject in coverage_export.subjects:
        opaque_id = opaque_case_id(subject.subject_id)
        result = registry.invoke("get_location_records", {"subject_id": opaque_id})

        assert result["subject_id"] == opaque_id
        assert len(result["locations"]) == len(subject.locations)
        assert result["locations"] == build_t2(subject.request, subject).locations

        serialized = json.dumps(result)
        assert subject.subject_id not in serialized
        for location in subject.locations:
            assert location.location_id not in serialized
        for cell_id in cell_ids:
            assert cell_id not in serialized, (
                f"cell name {cell_id!r} survived in {subject.subject_id}"
            )


def test_get_location_records_rejects_the_real_subject_id(coverage_export) -> None:
    """The real id is the one token that must never have crossed the seam.

    Accepting it back would mean the model had been handed it, so the tool treats it as
    unresolvable rather than as a convenient alias.
    """
    registry = build_retrieval_tool_registry(coverage_export)
    subject = coverage_export.subjects[0]

    with pytest.raises(ValueError) as excinfo:
        registry.invoke("get_location_records", {"subject_id": subject.subject_id})

    assert subject.subject_id in str(excinfo.value)


@pytest.mark.parametrize(
    "subject_id",
    ["nonexistent-subject", "case-000000000000"],
)
def test_get_location_records_rejects_an_unknown_subject_id(subject_id: str, export_bundle) -> None:
    """Replaces the old `{"locations": [], "error": "subject_not_found"}` result.

    A silent empty result reads to the model as a subject with nothing to erase, and is
    indistinguishable downstream from one — including for an id the model invented.
    """
    registry = build_retrieval_tool_registry(export_bundle)

    with pytest.raises(ValueError) as excinfo:
        registry.invoke("get_location_records", {"subject_id": subject_id})

    assert subject_id in str(excinfo.value)


def test_get_retention_floors_matches_t3(archive_export_bundle) -> None:
    registry = build_retrieval_tool_registry(archive_export_bundle)
    subject = subject_with_tag(archive_export_bundle.subjects, "mixed_fanout")
    t3 = build_t3(subject.request, subject, archive_export_bundle.rules)
    result = registry.invoke("get_retention_floors", {})
    assert result["retention_floors"] == [
        floor.model_dump(mode="json") for floor in t3.retention_floors
    ]
    assert len(result["retention_floors"]) == 5


def test_get_governance_map_matches_t3(archive_export_bundle) -> None:
    registry = build_retrieval_tool_registry(archive_export_bundle)
    subject = subject_with_tag(archive_export_bundle.subjects, "mixed_fanout")
    t3 = build_t3(subject.request, subject, archive_export_bundle.rules)
    result = registry.invoke("get_governance_map", {})
    assert result["governance_map"] == [
        entry.model_dump(mode="json") for entry in t3.governance_map
    ]


def test_floor_ids_and_governance_categories_survive_substitution_byte_identical(
    coverage_export,
) -> None:
    """Spec section 9: floors and governance entries are domain content, not identifiers.

    Neither tool is routed through `substitute`, so the first half asserts they came
    through the tool whole; the second asserts that routing them through any subject's map
    would have been a no-op anyway. Spec section 13 makes altering them a stop condition.

    This is the only home for Phase A Task 8 item 9; it is not repeated in the
    prompt-isolation file.
    """
    registry = build_retrieval_tool_registry(coverage_export)
    floors = registry.invoke("get_retention_floors", {})
    governance = registry.invoke("get_governance_map", {})

    assert floors["retention_floors"] == [
        item.model_dump(mode="json") for item in coverage_export.rules.retention_floors
    ]
    assert governance["governance_map"] == [
        item.model_dump(mode="json") for item in coverage_export.rules.governance_map
    ]
    assert {item["floor_id"] for item in floors["retention_floors"]} == {
        "pmla_kyc",
        "gst",
        "income_tax",
        "companies_act",
        "sebi",
    }
    assert {item["category"] for item in governance["governance_map"]} == {
        "customer",
        "kyc_document",
        "marketing_consent",
        "payment_transaction",
        "securities_transaction",
    }

    for subject in coverage_export.subjects:
        mapping = build_substitution_map(subject)
        assert substitute(floors, mapping) == floors
        assert substitute(governance, mapping) == governance


def test_tools_read_export_via_loader_only(archive_export_bundle) -> None:
    registry = build_retrieval_tool_registry(archive_export_bundle)
    subject = subject_with_tag(archive_export_bundle.subjects, "mixed_fanout")
    floors = registry.invoke("get_retention_floors", {})
    assert floors["retention_floors"]
    records = registry.invoke(
        "get_location_records",
        {"subject_id": opaque_case_id(subject.subject_id)},
    )
    assert records["locations"]
    governance = registry.invoke("get_governance_map", {})
    assert governance["governance_map"]


def test_registry_exports_all_tool_names(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    assert registry.tool_names == frozenset(
        {"get_location_records", "get_retention_floors", "get_governance_map"}
    )


def test_tools_use_committed_export_not_hardcoded(export_dir) -> None:
    export = load_export(export_dir)
    registry = build_retrieval_tool_registry(export)
    floors = registry.invoke("get_retention_floors", {})
    floor_ids = {item["floor_id"] for item in floors["retention_floors"]}
    assert floor_ids == {"pmla_kyc", "gst", "income_tax", "companies_act", "sebi"}

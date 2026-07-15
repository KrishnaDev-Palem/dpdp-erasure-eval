"""Acceptance tests for filesystem-backed retrieval tools (US1)."""

from __future__ import annotations

import pytest

from core.context import build_t2, build_t3
from core.export import load_export
from core.tools import build_retrieval_tool_registry
from tests.core.conftest import subject_with_tag


@pytest.mark.parametrize(
    "subject_id",
    ["subj-mixed-fanout", "subj-payment-inside-floors"],
)
def test_get_location_records_matches_t2(subject_id: str, export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    subject = next(item for item in export_bundle.subjects if item.subject_id == subject_id)
    t2 = build_t2(subject.request, subject)
    result = registry.invoke("get_location_records", {"subject_id": subject_id})
    assert result["locations"] == t2.locations
    assert "expected" not in str(result)


@pytest.mark.skip(reason="real export has no zero-location subjects")
def test_get_location_records_empty_locations(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    result = registry.invoke(
        "get_location_records",
        {"subject_id": "synthetic-empty-subject"},
    )
    assert result["locations"] == []
    assert "error" not in result


def test_get_location_records_unknown_subject(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    result = registry.invoke("get_location_records", {"subject_id": "nonexistent-subject"})
    assert result["locations"] == []
    assert result["error"] == "subject_not_found"
    assert result["subject_id"] == "nonexistent-subject"


def test_get_retention_floors_matches_t3(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    t3 = build_t3(subject.request, subject, export_bundle.rules)
    result = registry.invoke("get_retention_floors", {})
    assert result["retention_floors"] == [
        floor.model_dump(mode="json") for floor in t3.retention_floors
    ]
    assert len(result["retention_floors"]) == 5


def test_get_governance_map_matches_t3(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    t3 = build_t3(subject.request, subject, export_bundle.rules)
    result = registry.invoke("get_governance_map", {})
    assert result["governance_map"] == [
        entry.model_dump(mode="json") for entry in t3.governance_map
    ]


def test_tools_read_export_via_loader_only(export_bundle) -> None:
    registry = build_retrieval_tool_registry(export_bundle)
    subject = subject_with_tag(export_bundle.subjects, "mixed_fanout")
    floors = registry.invoke("get_retention_floors", {})
    assert floors["retention_floors"]
    records = registry.invoke("get_location_records", {"subject_id": subject.subject_id})
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

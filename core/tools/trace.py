"""Auditable tool-call result summaries."""

from __future__ import annotations

from typing import Any


def summarize_tool_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    """Build auditable result summaries per tool-call-trace contract."""
    if tool_name == "get_location_records":
        locations = result.get("locations", [])
        summary: dict[str, Any] = {
            "subject_id": result.get("subject_id"),
            "location_count": len(locations),
            "location_ids": sorted(str(item["location_id"]) for item in locations),
        }
        if "error" in result:
            summary["error"] = result["error"]
        return summary
    if tool_name == "get_retention_floors":
        floors = result.get("retention_floors", [])
        return {
            "floor_count": len(floors),
            "floor_ids": sorted(str(item["floor_id"]) for item in floors),
        }
    if tool_name == "get_governance_map":
        entries = result.get("governance_map", [])
        return {
            "entry_count": len(entries),
            "categories": sorted(str(item["category"]) for item in entries),
        }
    raise ValueError(f"Unknown tool for summary: {tool_name!r}")

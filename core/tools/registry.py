"""Retrieval tool registry protocol and dispatch."""

from __future__ import annotations

from typing import Any, Protocol

from core.export.loader import ExportBundle
from core.tools.governance_map import get_governance_map
from core.tools.location_records import get_location_records
from core.tools.retention_floors import get_retention_floors

RETRIEVAL_TOOL_NAMES: frozenset[str] = frozenset(
    {"get_location_records", "get_retention_floors", "get_governance_map"}
)


class ToolRegistry(Protocol):
    """Callable dispatch interface for filesystem-backed retrieval tools."""

    @property
    def tool_names(self) -> frozenset[str]: ...

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class RetrievalToolRegistry:
    """Concrete registry scoped to one verified export bundle."""

    def __init__(self, bundle: ExportBundle) -> None:
        self._bundle = bundle

    @property
    def tool_names(self) -> frozenset[str]:
        return RETRIEVAL_TOOL_NAMES

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name not in RETRIEVAL_TOOL_NAMES:
            raise ValueError(f"Unknown tool: {tool_name!r}")
        if tool_name == "get_location_records":
            subject_id = arguments.get("subject_id")
            if not isinstance(subject_id, str) or not subject_id:
                raise ValueError("get_location_records requires subject_id")
            return get_location_records(bundle=self._bundle, subject_id=subject_id)
        if tool_name == "get_retention_floors":
            return get_retention_floors(bundle=self._bundle)
        return get_governance_map(bundle=self._bundle)


def build_retrieval_tool_registry(bundle: ExportBundle) -> RetrievalToolRegistry:
    return RetrievalToolRegistry(bundle)

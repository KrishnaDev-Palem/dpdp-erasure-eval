"""Return T3-equivalent governance map entries from the export."""

from __future__ import annotations

from core.export.loader import ExportBundle


def get_governance_map(*, bundle: ExportBundle) -> dict:
    """Return the full governance map from the rules corpus."""
    return {
        "governance_map": [entry.model_dump(mode="json") for entry in bundle.rules.governance_map],
    }

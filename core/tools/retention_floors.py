"""Return T3-equivalent retention floor rules from the export."""

from __future__ import annotations

from core.export.loader import ExportBundle


def get_retention_floors(*, bundle: ExportBundle) -> dict:
    """Return all five sectoral retention floors from the rules corpus."""
    return {
        "retention_floors": [
            floor.model_dump(mode="json") for floor in bundle.rules.retention_floors
        ],
    }

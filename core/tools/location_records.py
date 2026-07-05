"""Return T2-equivalent location records for a subject."""

from __future__ import annotations

from core.context.tiers import _location_without_expected
from core.export.loader import ExportBundle


def get_location_records(*, bundle: ExportBundle, subject_id: str) -> dict:
    """Return location business fields without ground-truth labels."""
    subject = next((item for item in bundle.subjects if item.subject_id == subject_id), None)
    if subject is None:
        return {
            "subject_id": subject_id,
            "locations": [],
            "error": "subject_not_found",
        }
    return {
        "subject_id": subject_id,
        "locations": [_location_without_expected(location) for location in subject.locations],
    }

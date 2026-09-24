"""Return T2-equivalent location records for the subject behind an opaque case id."""

from __future__ import annotations

from collections.abc import Mapping

from core.context.tiers import _location_without_expected
from core.export.loader import ExportBundle
from core.pseudonymize import build_substitution_map, opaque_case_id, substitute


def build_opaque_subject_index(bundle: ExportBundle) -> dict[str, str]:
    """Map every subject's opaque case id back to its real subject id."""
    return {opaque_case_id(subject.subject_id): subject.subject_id for subject in bundle.subjects}


def get_location_records(
    *,
    bundle: ExportBundle,
    subject_id: str,
    opaque_subject_index: Mapping[str, str] | None = None,
) -> dict:
    """Return location business fields, opaque and without ground-truth labels.

    `subject_id` is the opaque case id the model was handed, not a real one. Tool results
    enter context after the bundle is built, so this payload is not covered by context
    pseudonymization and is substituted here instead — every identifier it returns,
    including the echoed subject id, comes out of the same map.

    An id that does not resolve raises, whether it is unknown or a real subject id offered
    where an opaque one belongs. An empty result would read to the model as a subject with
    nothing to erase and would be indistinguishable, downstream, from one.
    """
    index = (
        build_opaque_subject_index(bundle) if opaque_subject_index is None else opaque_subject_index
    )
    real_subject_id = index.get(subject_id)
    if real_subject_id is None:
        raise ValueError(
            f"get_location_records requires an opaque case id; {subject_id!r} does not "
            "resolve to a subject in this bundle"
        )
    subject = next(item for item in bundle.subjects if item.subject_id == real_subject_id)
    mapping = build_substitution_map(subject)
    return substitute(
        {
            "subject_id": real_subject_id,
            "locations": [_location_without_expected(location) for location in subject.locations],
        },
        mapping,
    )

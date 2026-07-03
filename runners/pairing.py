"""Location pairing and verdict validation for tier sweeps."""

from __future__ import annotations

from core.types import ExpectedLabel, LabeledLocation, ModelVerdict, Verdict

VALID_VERDICTS: frozenset[Verdict] = frozenset({"erase", "retain", "escalate"})


class PairingValidationError(ValueError):
    """Raised when verdict coverage or enum validation fails."""


def pair_subject_verdicts(
    *,
    subject_id: str,
    sample_index: int,
    locations: list[LabeledLocation],
    pairing_location_ids: list[str],
    raw_verdicts: list[dict],
) -> list[tuple[ModelVerdict, ExpectedLabel]]:
    """Align model verdicts with export ground truth by location_id."""
    if not pairing_location_ids:
        if raw_verdicts:
            raise PairingValidationError(
                f"subject_id={subject_id} sample_index={sample_index}: "
                f"unexpected verdicts for empty pairing locations"
            )
        return []

    verdict_by_id: dict[str, dict] = {}
    for item in raw_verdicts:
        verdict_by_id[str(item["location_id"])] = item

    expected_ids = set(pairing_location_ids)
    actual_ids = set(verdict_by_id)

    missing = expected_ids - actual_ids
    if missing:
        missing_id = sorted(missing)[0]
        raise PairingValidationError(
            f"subject_id={subject_id} location_id={missing_id} sample_index={sample_index}: "
            f"missing verdict"
        )

    extra = actual_ids - expected_ids
    if extra:
        extra_id = sorted(extra)[0]
        raise PairingValidationError(
            f"subject_id={subject_id} location_id={extra_id} sample_index={sample_index}: "
            f"unexpected verdict"
        )

    location_by_id = {item.location_id: item for item in locations}
    pairs: list[tuple[ModelVerdict, ExpectedLabel]] = []
    for location_id in pairing_location_ids:
        raw = verdict_by_id[location_id]
        verdict_value = raw.get("verdict")
        if verdict_value not in VALID_VERDICTS:
            raise PairingValidationError(
                f"subject_id={subject_id} location_id={location_id} sample_index={sample_index}: "
                f"invalid verdict {verdict_value!r}"
            )
        export_location = location_by_id.get(location_id)
        if export_location is None:
            raise PairingValidationError(
                f"subject_id={subject_id} location_id={location_id} sample_index={sample_index}: "
                f"location not in export"
            )
        pairs.append(
            (
                ModelVerdict(
                    location_id=location_id,
                    verdict=verdict_value,
                    detail=raw.get("detail"),
                ),
                export_location.expected,
            )
        )
    return pairs

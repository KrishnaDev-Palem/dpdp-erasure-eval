"""Translate opaque location ids back to real ones, before pairing sees them.

Context builders hand the model opaque location ids, so a verdict names a location the
export does not know — whether it came back from a live seam or off a cache entry a live
seam wrote. Two things are opaque at that boundary, not one: the verdict ids, and the
`pairing_location_ids` every caller derives from `context.locations`.

Translation happens here, at the boundary, rather than inside `runners/pairing.py`:
`score_adjudication_grouped` joins each pair back to its `LabeledLocation` with a bare
lookup, so an untranslated id reaches it as a `KeyError` rather than a soft miss. Pairing,
scoring, the grouped tables, and the retrieval split then operate on real ids exactly as
they did before any of this.

The inverse is rebuilt per subject from the same forward map the context builders use, so
it inherits their collision guard and stays recomputable per spec section 5: no map file,
no cache, no process-scoped state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.pseudonymize import build_substitution_map, invert
from core.types import AdjudicationSubject, ModelVerdict


class VerdictTranslationError(ValueError):
    """Raised when an identifier crossing back over the seam has no inverse."""


def location_id_inverse(subject: AdjudicationSubject) -> dict[str, str]:
    """Return `{opaque: real}` for one subject's location ids.

    Narrowed to locations after inversion: a verdict names a location, and the subject's
    own case token arriving in that slot is an error rather than something to resolve.
    """
    real_location_ids = {location.location_id for location in subject.locations}
    return {
        opaque: real
        for opaque, real in invert(build_substitution_map(subject)).items()
        if real in real_location_ids
    }


def to_real_location_id(location_id: str, inverse: Mapping[str, str]) -> str:
    """Resolve one opaque location id against this subject's inverse, or raise.

    An unresolvable token is never passed through as-is. Left alone it would either pair
    against nothing or fail later inside the grouped scorer, and a real id offered here is
    a stale pre-substitution response rather than something to wave past. This is the
    contract `get_location_records` gives an unknown case id.
    """
    real = inverse.get(location_id)
    if real is None:
        raise VerdictTranslationError(
            f"location_id {location_id!r} does not resolve to an export location; "
            "expected an opaque token from this subject's substitution map"
        )
    return real


def to_real_location_ids(location_ids: Iterable[Any], inverse: Mapping[str, str]) -> list[str]:
    """Resolve a whole opaque id list, order preserved."""
    return [to_real_location_id(str(item), inverse) for item in location_ids]


def translate_raw_verdicts(
    raw_verdicts: Iterable[Mapping[str, Any]],
    inverse: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Return the raw verdict dicts with `location_id` resolved, everything else intact."""
    translated: list[dict[str, Any]] = []
    for item in raw_verdicts:
        entry = dict(item)
        if "location_id" not in entry:
            raise VerdictTranslationError("verdict entry carries no location_id")
        entry["location_id"] = to_real_location_id(str(entry["location_id"]), inverse)
        translated.append(entry)
    return translated


def translate_verdicts(
    verdicts: Iterable[ModelVerdict],
    inverse: Mapping[str, str],
) -> list[ModelVerdict]:
    """Return parsed verdicts with `location_id` resolved."""
    return [
        verdict.model_copy(
            update={"location_id": to_real_location_id(verdict.location_id, inverse)}
        )
        for verdict in verdicts
    ]

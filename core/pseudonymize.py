"""Deterministic pseudonymization of identifiers that cross the model seam.

Substitution is by token, never by field name. The export names every case after its
design cell and eight field paths carry that name inside identifier strings, one of them
nested and one a file path, so a field list is the failure mode this module removes
rather than repeats. Every string in a payload is walked and every mapping key replaced
as a substring, longest key first, so derived identifiers inherit the substitution and
keep their structure.

Every function here is a pure function of its input: no RNG, no salt, no clock, no
process-scoped state, and no map written to disk.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from core.exceptions import PseudonymizationError
from core.types import AdjudicationSubject

CASE_PREFIX = "case-"
LOCATION_PREFIX = "loc-"
TOKEN_HEX_CHARS = 12

# 48 bits. Collision across the 350-case export is negligible and is asserted rather
# than assumed: build_substitution_map raises instead of overwriting.
_MATCHES_NOTHING = re.compile(r"(?!)")


def _token(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:TOKEN_HEX_CHARS]


def opaque_case_id(subject_id: str) -> str:
    """Return the opaque handle for a subject id."""
    return _token(CASE_PREFIX, subject_id)


def opaque_location_id(location_id: str) -> str:
    """Return the opaque handle for a location id."""
    return _token(LOCATION_PREFIX, location_id)


def build_substitution_map(subject: AdjudicationSubject) -> dict[str, str]:
    """Map the subject id and every location id to its opaque token.

    Two distinct identifiers claiming one token is a hard error, not a warning: the
    substitution would otherwise be silently unrecoverable by `invert`.
    """
    mapping: dict[str, str] = {}
    claimed_by: dict[str, str] = {}

    def claim(real: str, opaque: str) -> None:
        if not real:
            raise PseudonymizationError("cannot substitute an empty identifier")
        owner = claimed_by.get(opaque)
        if owner is not None and owner != real:
            raise PseudonymizationError(
                f"opaque token {opaque!r} is claimed by both {owner!r} and {real!r}"
            )
        previous = mapping.get(real)
        if previous is not None and previous != opaque:
            raise PseudonymizationError(
                f"identifier {real!r} already maps to {previous!r}, not {opaque!r}"
            )
        mapping[real] = opaque
        claimed_by[opaque] = real

    claim(subject.subject_id, opaque_case_id(subject.subject_id))
    claim(subject.request.subject_id, opaque_case_id(subject.request.subject_id))
    for location in subject.locations:
        claim(location.location_id, opaque_location_id(location.location_id))
    return mapping


def substitute(payload: Any, mapping: Mapping[str, str]) -> Any:
    """Replace every mapping key found in any string of `payload`, longest key first.

    Recurses through dicts, lists, tuples, and nested Pydantic models. No field name is
    consulted, so a field added to the export later is covered without a code change.
    Models are returned as plain JSON-compatible dicts. Replacement is a single pass, so
    an opaque token can never itself be re-substituted.
    """
    return _walk(payload, _pattern(mapping), mapping)


def invert(mapping: Mapping[str, str]) -> dict[str, str]:
    """Return `{opaque: real}` so verdicts can be translated back before pairing."""
    inverse: dict[str, str] = {}
    for real, opaque in mapping.items():
        owner = inverse.get(opaque)
        if owner is not None and owner != real:
            raise PseudonymizationError(
                f"opaque token {opaque!r} is claimed by both {owner!r} and {real!r}"
            )
        inverse[opaque] = real
    return inverse


def _pattern(mapping: Mapping[str, str]) -> re.Pattern[str]:
    if not mapping:
        return _MATCHES_NOTHING
    if any(not key for key in mapping):
        raise PseudonymizationError("substitution mapping must not contain an empty key")
    # Alternation is tried left to right, so longest first yields the longest match.
    keys = sorted(mapping, key=lambda key: (-len(key), key))
    return re.compile("|".join(re.escape(key) for key in keys))


def _walk(value: Any, pattern: re.Pattern[str], mapping: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return pattern.sub(lambda match: mapping[match.group(0)], value)
    if isinstance(value, BaseModel):
        return _walk(value.model_dump(mode="json"), pattern, mapping)
    if isinstance(value, dict):
        return {
            _walk(key, pattern, mapping): _walk(item, pattern, mapping)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_walk(item, pattern, mapping) for item in value]
    if isinstance(value, tuple):
        return tuple(_walk(item, pattern, mapping) for item in value)
    return value

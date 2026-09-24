"""Build tier-appropriate context bundles without ground-truth leakage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.pseudonymize import build_substitution_map, substitute
from core.types import (
    AdjudicationSubject,
    ContextBundle,
    ErasureRequest,
    RulesCorpus,
)

_EVAL_ONLY_LOCATION_FIELDS: tuple[str, ...] = ("expected", "strata", "cell_id")


def _location_without_expected(location: Any) -> dict[str, Any]:
    data = location.model_dump(mode="json") if hasattr(location, "model_dump") else dict(location)
    for field in _EVAL_ONLY_LOCATION_FIELDS:
        data.pop(field, None)
    return data


def _opaque_request(request: ErasureRequest, mapping: Mapping[str, str]) -> ErasureRequest:
    """Rebuild the request from its substituted dump.

    `substitute` returns plain dicts, so the bundle would otherwise carry a mapping
    where a validated model belongs. Revalidating keeps `ContextBundle.request` a real
    `ErasureRequest` without relaxing any field.
    """
    return ErasureRequest.model_validate(substitute(request, mapping))


def _opaque_locations(
    subject: AdjudicationSubject,
    mapping: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Scrub the eval-only fields, then substitute every identifier still in the payload.

    The field scrub stays: `expected`, `strata`, and `cell_id` are eval-only and must not
    reach the model at all. Substitution then covers the design-cell name where it lives
    inside identifier strings, which no field list can reach.
    """
    return [
        substitute(_location_without_expected(location), mapping) for location in subject.locations
    ]


def build_t1(request: ErasureRequest, subject: AdjudicationSubject) -> ContextBundle:
    mapping = build_substitution_map(subject)
    return ContextBundle(
        tier="t1",
        request=_opaque_request(request, mapping),
        locations=[
            {"location_id": mapping[location.location_id]} for location in subject.locations
        ],
    )


def build_t2(request: ErasureRequest, subject: AdjudicationSubject) -> ContextBundle:
    mapping = build_substitution_map(subject)
    return ContextBundle(
        tier="t2",
        request=_opaque_request(request, mapping),
        locations=_opaque_locations(subject, mapping),
    )


def build_t3(
    request: ErasureRequest,
    subject: AdjudicationSubject,
    rules: RulesCorpus,
) -> ContextBundle:
    mapping = build_substitution_map(subject)
    return ContextBundle(
        tier="t3",
        request=_opaque_request(request, mapping),
        locations=_opaque_locations(subject, mapping),
        # Floors and governance entries are domain content the model must reason over,
        # not identifiers. Spec section 9: they pass through untouched.
        retention_floors=list(rules.retention_floors),
        governance_map=list(rules.governance_map),
    )

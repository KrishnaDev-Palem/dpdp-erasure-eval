"""Build tier-appropriate context bundles without ground-truth leakage."""

from __future__ import annotations

from typing import Any

from core.types import (
    AdjudicationSubject,
    ContextBundle,
    ErasureRequest,
    RulesCorpus,
)


def _location_without_expected(location: Any) -> dict[str, Any]:
    data = location.model_dump(mode="json") if hasattr(location, "model_dump") else dict(location)
    data.pop("expected", None)
    return data


def build_t1(request: ErasureRequest, subject: AdjudicationSubject) -> ContextBundle:
    return ContextBundle(
        tier="t1",
        request=request,
        locations=[],
    )


def build_t2(request: ErasureRequest, subject: AdjudicationSubject) -> ContextBundle:
    return ContextBundle(
        tier="t2",
        request=request,
        locations=[_location_without_expected(location) for location in subject.locations],
    )


def build_t3(
    request: ErasureRequest,
    subject: AdjudicationSubject,
    rules: RulesCorpus,
) -> ContextBundle:
    return ContextBundle(
        tier="t3",
        request=request,
        locations=[_location_without_expected(location) for location in subject.locations],
        retention_floors=list(rules.retention_floors),
        governance_map=list(rules.governance_map),
    )

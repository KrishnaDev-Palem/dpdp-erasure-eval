"""Fake model seam for offline acceptance tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.exceptions import ModelResponseError
from core.tools.registry import ToolRegistry
from core.tools.trace import summarize_tool_result
from core.types import (
    AdjudicationSessionResult,
    ClassifierResult,
    ContextBundle,
    ModelVerdict,
    ToolCallTrace,
    Verdict,
)


@dataclass
class FakeModelSeam:
    adjudication_verdicts: dict[str, Verdict] | None = None
    classification_outcome: str = "clean"
    pairing_location_ids: list[str] | None = None
    planned_tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    adjudicate_calls: list[dict[str, object]] = field(default_factory=list)
    classify_calls: list[dict[str, object]] = field(default_factory=list)

    def adjudicate(
        self,
        *,
        context: ContextBundle,
        case_id: str,
        tool_registry: ToolRegistry | None = None,
    ) -> list[ModelVerdict] | AdjudicationSessionResult:
        self.adjudicate_calls.append(
            {
                "context": context,
                "case_id": case_id,
                "tool_registry": tool_registry,
            }
        )
        location_ids = self.pairing_location_ids
        if location_ids is None:
            location_ids = [str(location["location_id"]) for location in context.locations]

        if tool_registry is not None:
            tool_calls: list[ToolCallTrace] = []
            for sequence, (tool_name, arguments) in enumerate(self.planned_tool_calls):
                result = tool_registry.invoke(tool_name, arguments)
                tool_calls.append(
                    ToolCallTrace(
                        sequence=sequence,
                        tool_name=tool_name,  # type: ignore[arg-type]
                        arguments=arguments,
                        result_summary=summarize_tool_result(tool_name, result),
                    )
                )
            verdicts = self._build_verdicts(location_ids)
            return AdjudicationSessionResult(
                verdicts=verdicts,
                raw_verdicts=[item.model_dump(mode="json") for item in verdicts],
                tool_calls=tool_calls,
            )

        return self._build_verdicts(location_ids)

    def _build_verdicts(self, location_ids: list[str]) -> list[ModelVerdict]:
        verdicts: list[ModelVerdict] = []
        for location_id in location_ids:
            if self.adjudication_verdicts is None:
                verdict = "retain"
            elif location_id not in self.adjudication_verdicts:
                raise ModelResponseError(f"Missing verdict for location {location_id!r}")
            else:
                verdict = self.adjudication_verdicts[location_id]
            verdicts.append(ModelVerdict(location_id=location_id, verdict=verdict))
        return verdicts

    def classify_note(
        self,
        *,
        text: str,
        case_id: str | None = None,
    ) -> ClassifierResult:
        self.classify_calls.append({"text": text, "case_id": case_id})
        outcome = self.classification_outcome
        if outcome not in {"clean", "adversarial"}:
            raise ModelResponseError(f"Invalid classification outcome: {outcome!r}")
        return ClassifierResult(outcome=outcome)

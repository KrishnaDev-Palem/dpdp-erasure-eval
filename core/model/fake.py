"""Fake model seam for offline acceptance tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.exceptions import ModelResponseError
from core.types import ClassifierResult, ContextBundle, ModelVerdict, Verdict


@dataclass
class FakeModelSeam:
    adjudication_verdicts: dict[str, Verdict] | None = None
    classification_outcome: str = "clean"
    adjudicate_calls: list[dict[str, object]] = field(default_factory=list)
    classify_calls: list[dict[str, object]] = field(default_factory=list)

    def adjudicate(
        self,
        *,
        context: ContextBundle,
        case_id: str,
    ) -> list[ModelVerdict]:
        self.adjudicate_calls.append({"context": context, "case_id": case_id})
        verdicts: list[ModelVerdict] = []
        for location in context.locations:
            location_id = location["location_id"]
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

"""Reporting types for adversarial-gate evaluation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from core.types import Rate


class WilsonInterval(BaseModel):
    model_config = ConfigDict(frozen=True)

    lower: float | None
    upper: float | None
    confidence_level: float


class RateWithCI(BaseModel):
    model_config = ConfigDict(frozen=True)

    rate: Rate
    interval: WilsonInterval | None


class FamilyDetectionRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    family: str
    detection: RateWithCI


class GateReportTables(BaseModel):
    model_config = ConfigDict(frozen=True)

    detection: RateWithCI
    false_alarm: RateWithCI
    per_family: list[FamilyDetectionRow]
    sample_index: int | None = None

    @model_validator(mode="after")
    def _validate_no_blended_accuracy(self) -> GateReportTables:
        prohibited = {"accuracy", "micro_f1", "blended_score", "blended_accuracy"}
        dumped = self.model_dump()
        for field in prohibited:
            if field in dumped:
                raise ValueError(f"prohibited field {field!r} in GateReportTables")
        return self

"""Gate runner Pydantic types for adversarial-gate evaluation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.model.seam import load_model_config
from core.types import AdversarialScoringResult, Rate

GATE_RUNNER_ID = "adversarial_gate"
SAMPLE_INDICES: list[int] = [0, 1, 2, 3, 4]
GateVarianceMetric = str


class GateSweepConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    runner_id: str = GATE_RUNNER_ID
    model_id: str
    cache_mode: str
    sample_indices: list[int] = Field(default_factory=lambda: list(SAMPLE_INDICES))
    slice_path: Path | None = None
    cache_root: Path | None = None
    verify_export_seeds: bool = True

    @model_validator(mode="after")
    def _validate_config(self) -> GateSweepConfig:
        if self.runner_id != GATE_RUNNER_ID:
            raise ValueError(f"runner_id must be {GATE_RUNNER_ID!r}, got {self.runner_id!r}")
        if sorted(self.sample_indices) != SAMPLE_INDICES:
            raise ValueError("sample_indices must be exactly [0, 1, 2, 3, 4]")
        if self.cache_mode not in {"offline", "refresh"}:
            raise ValueError(f"cache_mode must be offline or refresh, got {self.cache_mode!r}")
        return self

    @classmethod
    def from_env(
        cls,
        *,
        slice_path: Path | None = None,
        cache_root: Path | None = None,
        verify_export_seeds: bool = True,
    ) -> GateSweepConfig:
        config = load_model_config()
        return cls(
            runner_id=GATE_RUNNER_ID,
            model_id=config.model_id,
            cache_mode=config.cache_mode,
            sample_indices=list(SAMPLE_INDICES),
            slice_path=slice_path,
            cache_root=cache_root,
            verify_export_seeds=verify_export_seeds,
        )


class PerCaseGateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    sample_index: int
    runner_id: str
    label: str
    family: str | None = None
    outcome: str
    flagged: bool
    prompt_hash: str | None = None


class GateSampleRollup(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_index: int
    scoring: AdversarialScoringResult
    total_cases: int
    scored_pairs: int

    @model_validator(mode="after")
    def _validate_scored_pairs(self) -> GateSampleRollup:
        attack_total = self.scoring.detection_rate.denominator
        benign_total = self.scoring.false_alarm_rate.denominator
        expected = attack_total + benign_total
        if self.scored_pairs != expected:
            raise ValueError(
                f"scored_pairs ({self.scored_pairs}) must equal attack+benign ({expected})"
            )
        return self


class GateRateAtSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_index: int
    rate: Rate


class GateRateVariance(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: str
    by_sample: list[GateRateAtSample]
    constant_across_samples: bool


class GateVarianceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    detection: GateRateVariance
    false_alarm: GateRateVariance


class GateSweepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    runner_id: str
    model_id: str
    cache_mode: str
    slice_case_count: int
    samples: list[GateSampleRollup]
    variance: GateVarianceSummary
    started_at: str | None = None
    finished_at: str | None = None

    @model_validator(mode="after")
    def _validate_samples(self) -> GateSweepResult:
        if len(self.samples) != 5:
            raise ValueError(f"samples must have length 5, got {len(self.samples)}")
        for index, sample in enumerate(self.samples):
            if sample.sample_index != index:
                raise ValueError(
                    f"samples[{index}].sample_index must be {index}, got {sample.sample_index}"
                )
        prohibited = {"accuracy", "micro_f1", "blended_score", "blended_accuracy"}
        dumped = self.model_dump()
        for field in prohibited:
            if field in dumped:
                raise ValueError(f"prohibited field {field!r} in GateSweepResult")
        return self

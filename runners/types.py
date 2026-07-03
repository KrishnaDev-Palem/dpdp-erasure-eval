"""Runner-layer Pydantic types for tier sweep results."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.model.seam import load_model_config
from core.types import AdjudicationScoringResult, ExpectedLabel, ModelVerdict, Rate, Tier

VarianceMetric = Literal["over_erasure", "over_retention", "mis_escalation"]

SAMPLE_INDICES: list[int] = [0, 1, 2, 3, 4]


class SweepConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: Tier
    runner_id: str
    model_id: str
    cache_mode: str
    sample_indices: list[int] = Field(default_factory=lambda: list(SAMPLE_INDICES))
    export_dir: Path | None = None
    cache_root: Path | None = None

    @model_validator(mode="after")
    def _validate_config(self) -> SweepConfig:
        if self.runner_id != self.tier:
            raise ValueError(f"runner_id {self.runner_id!r} must match tier {self.tier!r}")
        if sorted(self.sample_indices) != SAMPLE_INDICES:
            raise ValueError("sample_indices must be exactly [0, 1, 2, 3, 4]")
        if self.cache_mode not in {"offline", "refresh"}:
            raise ValueError(f"cache_mode must be offline or refresh, got {self.cache_mode!r}")
        return self

    @classmethod
    def from_env(
        cls,
        *,
        tier: Tier = "t1",
        export_dir: Path | None = None,
        cache_root: Path | None = None,
    ) -> SweepConfig:
        config = load_model_config()
        return cls(
            tier=tier,
            runner_id=tier,
            model_id=config.model_id,
            cache_mode=config.cache_mode,
            sample_indices=list(SAMPLE_INDICES),
            export_dir=export_dir,
            cache_root=cache_root,
        )


class PerCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_id: str
    sample_index: int
    tier: Tier
    runner_id: str
    context_tier: Tier
    pairs: list[tuple[ModelVerdict, ExpectedLabel]]
    skipped: bool
    prompt_hash: str | None = None


class SampleRollup(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_index: int
    scoring: AdjudicationScoringResult
    total_subjects: int
    scored_location_pairs: int

    @model_validator(mode="after")
    def _validate_scored_pairs(self) -> SampleRollup:
        if self.scored_location_pairs != self.scoring.total_cases:
            raise ValueError(
                f"scored_location_pairs ({self.scored_location_pairs}) "
                f"must equal scoring.total_cases ({self.scoring.total_cases})"
            )
        return self


class RateAtSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_index: int
    rate: Rate


class RateVariance(BaseModel):
    model_config = ConfigDict(frozen=True)

    metric: VarianceMetric
    by_sample: list[RateAtSample]
    constant_across_samples: bool


class VarianceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    over_erasure: RateVariance
    over_retention: RateVariance
    mis_escalation: RateVariance


class TierSweepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: Tier
    runner_id: str
    model_id: str
    cache_mode: str
    export_agent_sha: str
    samples: list[SampleRollup]
    variance: VarianceSummary
    started_at: str | None = None
    finished_at: str | None = None

    @model_validator(mode="after")
    def _validate_samples(self) -> TierSweepResult:
        if len(self.samples) != 5:
            raise ValueError(f"samples must have length 5, got {len(self.samples)}")
        for index, sample in enumerate(self.samples):
            if sample.sample_index != index:
                raise ValueError(
                    f"samples[{index}].sample_index must be {index}, got {sample.sample_index}"
                )
        prohibited = {"accuracy", "micro_f1", "blended_score"}
        dumped = self.model_dump()
        for field in prohibited:
            if field in dumped:
                raise ValueError(f"prohibited field {field!r} in TierSweepResult")
        return self

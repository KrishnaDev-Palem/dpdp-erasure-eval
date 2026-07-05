"""Autonomous runner configuration and result types."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.model.seam import load_model_config
from runners.types import SAMPLE_INDICES, SampleRollup, VarianceSummary

AUTONOMOUS_RUNNER_ID = "autonomous"


class AutonomousSweepConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    runner_id: str = AUTONOMOUS_RUNNER_ID
    model_id: str
    cache_mode: str
    sample_indices: list[int] = Field(default_factory=lambda: list(SAMPLE_INDICES))
    export_dir: Path | None = None
    cache_root: Path | None = None

    @model_validator(mode="after")
    def _validate_config(self) -> AutonomousSweepConfig:
        if self.runner_id != AUTONOMOUS_RUNNER_ID:
            raise ValueError(f"runner_id must be {AUTONOMOUS_RUNNER_ID!r}, got {self.runner_id!r}")
        if sorted(self.sample_indices) != SAMPLE_INDICES:
            raise ValueError("sample_indices must be exactly [0, 1, 2, 3, 4]")
        if self.cache_mode not in {"offline", "refresh"}:
            raise ValueError(f"cache_mode must be offline or refresh, got {self.cache_mode!r}")
        return self

    @classmethod
    def from_env(
        cls,
        *,
        export_dir: Path | None = None,
        cache_root: Path | None = None,
    ) -> AutonomousSweepConfig:
        config = load_model_config()
        return cls(
            model_id=config.model_id,
            cache_mode=config.cache_mode,
            sample_indices=list(SAMPLE_INDICES),
            export_dir=export_dir,
            cache_root=cache_root,
        )


class AutonomousSweepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    runner_id: str
    initial_context_tier: Literal["t1"] = "t1"
    model_id: str
    cache_mode: str
    export_agent_sha: str
    samples: list[SampleRollup]
    variance: VarianceSummary
    started_at: str | None = None
    finished_at: str | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> AutonomousSweepResult:
        if self.runner_id != AUTONOMOUS_RUNNER_ID:
            raise ValueError(f"runner_id must be {AUTONOMOUS_RUNNER_ID!r}")
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
                raise ValueError(f"prohibited field {field!r} in AutonomousSweepResult")
        return self

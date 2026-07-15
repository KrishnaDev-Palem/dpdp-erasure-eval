"""Reporting types for autonomous retrieval-vs-reasoning failure split."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from core.types import VERDICT_LANES, Rate, Verdict

RetrievalSplitBucket = Literal["retrieval_failure", "reasoning_failure"]


class LaneRetrievalSplitCounts(BaseModel):
    """Incorrect-verdict split counts for one expected-verdict lane."""

    model_config = ConfigDict(frozen=True)

    lane: Verdict
    incorrect_count: int
    retrieval_failure_count: int
    reasoning_failure_count: int


class RetrievalSplitSampleRollup(BaseModel):
    """Per-sample retrieval split rollup."""

    model_config = ConfigDict(frozen=True)

    sample_index: int
    total_incorrect: int
    retrieval_failure_count: int
    reasoning_failure_count: int
    per_lane: list[LaneRetrievalSplitCounts]


class RetrievalSplitReport(BaseModel):
    """Retrieval-vs-reasoning failure split for autonomous incorrect verdicts."""

    model_config = ConfigDict(frozen=True)

    runner_id: str
    model_id: str
    cache_mode: str
    export_agent_sha: str
    primary_sample_index: int
    total_incorrect: int
    retrieval_failure: Rate
    reasoning_failure: Rate
    per_lane: list[LaneRetrievalSplitCounts]
    sample_rollups: list[RetrievalSplitSampleRollup]

    @model_validator(mode="after")
    def _validate_shape(self) -> RetrievalSplitReport:
        prohibited = {"accuracy", "micro_f1", "blended_score", "blended_accuracy"}
        dumped = self.model_dump()
        for field in prohibited:
            if field in dumped:
                raise ValueError(f"prohibited field {field!r} in RetrievalSplitReport")
        lane_set = {row.lane for row in self.per_lane}
        if lane_set != set(VERDICT_LANES):
            raise ValueError(f"per_lane must cover {VERDICT_LANES}, got {sorted(lane_set)}")
        if len(self.sample_rollups) != 5:
            raise ValueError(f"sample_rollups must have length 5, got {len(self.sample_rollups)}")
        return self

"""Reporting types for adjudication (tier and autonomous) evaluation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from report.types import RateWithCI
from runners.types import VarianceSummary


class AdjudicationMetricsTable(BaseModel):
    """Standalone adjudication rates with Wilson confidence intervals."""

    model_config = ConfigDict(frozen=True)

    over_erasure: RateWithCI
    over_retention: RateWithCI
    mis_escalation: RateWithCI


class SampleMetricsSummary(BaseModel):
    """Per-sample rollup with Wilson-augmented standalone rates."""

    model_config = ConfigDict(frozen=True)

    sample_index: int
    total_subjects: int
    scored_location_pairs: int
    metrics: AdjudicationMetricsTable


class GroupedAdjudicationRow(BaseModel):
    """Wilson-augmented standalone rates for one cell_id or strata-field value."""

    model_config = ConfigDict(frozen=True)

    key: str
    metrics: AdjudicationMetricsTable
    scored_location_pairs: int


class StratumFieldTable(BaseModel):
    """Grouped rates for one export-schema 1.0.0 strata field."""

    model_config = ConfigDict(frozen=True)

    field: str
    rows: list[GroupedAdjudicationRow]


class TierAdjudicationReportTables(BaseModel):
    """Report tables for one tier or autonomous sweep result."""

    model_config = ConfigDict(frozen=True)

    tier: str
    runner_id: str
    model_id: str
    cache_mode: str
    export_agent_sha: str
    primary_sample_index: int
    primary_metrics: AdjudicationMetricsTable
    confusion_matrix: dict[str, dict[str, int]]
    sample_rollups: list[SampleMetricsSummary]
    variance: VarianceSummary
    by_cell: list[GroupedAdjudicationRow] = Field(default_factory=list)
    by_stratum: list[StratumFieldTable] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_no_blended_accuracy(self) -> TierAdjudicationReportTables:
        prohibited = {"accuracy", "micro_f1", "blended_score", "blended_accuracy"}
        dumped = self.model_dump()
        for field in prohibited:
            if field in dumped:
                raise ValueError(f"prohibited field {field!r} in TierAdjudicationReportTables")
        return self


class CrossTierMetricRow(BaseModel):
    """One row in the cross-tier comparison table."""

    model_config = ConfigDict(frozen=True)

    tier: str
    over_erasure: RateWithCI
    over_retention: RateWithCI
    mis_escalation: RateWithCI


class CrossTierComparisonTable(BaseModel):
    """Compare standalone adjudication rates across T1, T2, T3, and autonomous."""

    model_config = ConfigDict(frozen=True)

    export_agent_sha: str
    sample_index: int
    rows: list[CrossTierMetricRow]

    @model_validator(mode="after")
    def _validate_rows(self) -> CrossTierComparisonTable:
        expected_tiers = {"t1", "t2", "t3", "autonomous"}
        actual = {row.tier for row in self.rows}
        if actual != expected_tiers:
            raise ValueError(f"cross-tier rows must cover {expected_tiers}, got {actual}")
        prohibited = {"accuracy", "micro_f1", "blended_score", "blended_accuracy"}
        dumped = self.model_dump()
        for field in prohibited:
            if field in dumped:
                raise ValueError(f"prohibited field {field!r} in CrossTierComparisonTable")
        return self

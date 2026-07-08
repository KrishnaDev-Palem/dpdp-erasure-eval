# Data Model: 005-cli-adjudication-report

**Date**: 2026-07-07  
**Feature**: CLI and adjudication report

This document defines adjudication reporting-layer types and CLI-facing report payloads only. Core domain entities (`AdjudicationScoringResult`, `Rate`, `VarianceSummary`, etc.) live in `core/types.py` and `runners/types.py` and are documented in [001/data-model.md](../001-shared-core/data-model.md) and [002/data-model.md](../002-context-tier-sweep/data-model.md). Gate report types (`GateReportTables`, `RateWithCI`, `WilsonInterval`) live in `report/types.py` and [003/data-model.md](../003-adversarial-gate/data-model.md). Report types **reference** upstream shapes; they do not redefine scoring math.

## Shared: RateWithCI (by reference)

Defined in `report/types.py`. Used by both gate and adjudication reports.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `rate` | Rate | yes | Core rate with `numerator`, `denominator`, `value` from runner scoring |
| `interval` | WilsonInterval \| null | yes | `null` when `rate.denominator == 0` |

### WilsonInterval (by reference)

| Field | Type | Notes |
|-------|------|-------|
| `lower` | float \| null | `null` when undefined |
| `upper` | float \| null | `null` when undefined |
| `confidence_level` | float | Default `0.95` |

## AdjudicationMetricsTable

Wilson-augmented standalone safety rates for one sample aggregate.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `over_erasure` | RateWithCI | yes | From `AdjudicationScoringResult.over_erasure_rate` |
| `over_retention` | RateWithCI | yes | From `AdjudicationScoringResult.over_retention_rate` |
| `mis_escalation` | RateWithCI | yes | From `AdjudicationScoringResult.mis_escalation_rate` |

**Validation**:
- Each embedded `rate.numerator` / `rate.denominator` MUST match upstream scoring exactly — report layer MUST NOT re-derive proportions.
- When `denominator == 0`: `rate.value`, `interval.lower`, `interval.upper`, and `interval` itself MUST be `null`.
- MUST NOT include prohibited fields (see below).

**Prohibited fields**: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.

## SampleMetricsSummary

One entry in the five-sample rollup list.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sample_index` | int | yes | 0..4 |
| `total_subjects` | int | yes | From upstream `SampleRollup.total_subjects` |
| `scored_location_pairs` | int | yes | From upstream `SampleRollup.scored_location_pairs`; equals `scoring.total_cases` |
| `metrics` | AdjudicationMetricsTable | yes | Wilson-augmented standalone rates for this sample |

**Validation**:
- `sample_index` MUST be in `0..4`.
- `scored_location_pairs` MUST equal embedded scoring `total_cases` when present in upstream rollup.

**Relationships**: Exactly five `SampleMetricsSummary` instances compose `TierAdjudicationReportTables.sample_rollups`, ordered by ascending `sample_index`.

## TierAdjudicationReportTables

Top-level adjudication report for one tier or autonomous evaluation.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `tier` | string | yes | `t1`, `t2`, `t3`, or `autonomous` |
| `runner_id` | string | yes | Cache namespace; equals tier for tier sweeps, `autonomous` for autonomous |
| `model_id` | string | yes | From runner config (`MODEL_ID` env, default `primary`) |
| `cache_mode` | string | yes | `offline` or `refresh` from runner config |
| `export_agent_sha` | string | yes | 40-char hex provenance from verified export manifest |
| `primary_sample_index` | int | yes | Sample driving `primary_metrics` and `confusion_matrix` |
| `primary_metrics` | AdjudicationMetricsTable | yes | Wilson-augmented rates for `primary_sample_index` |
| `confusion_matrix` | dict[str, dict[str, int]] | yes | Passthrough from primary sample's `AdjudicationScoringResult.confusion_matrix` — MUST NOT be recomputed |
| `sample_rollups` | list[SampleMetricsSummary] | yes | Length exactly 5 |
| `variance` | VarianceSummary | yes | Passthrough from sweep result unchanged |

**Validation**:
- `len(sample_rollups) == 5`.
- Rollup `sample_index` values MUST be `{0,1,2,3,4}`.
- `primary_sample_index` MUST be in `0..4` and `< len(samples)` in upstream sweep.
- `confusion_matrix` keys MUST be verdict lanes (`erase`, `retain`, `escalate`) per [001/contracts/scoring.md](../001-shared-core/contracts/scoring.md).
- Pydantic validator MUST reject construction if prohibited fields appear in serialized shape.

**Prohibited fields**: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.

**State transitions**: Immutable after construction (`frozen=True`). Built once from completed sweep via `build_tier_adjudication_report`.

## CrossTierMetricRow

One tier's Wilson-augmented standalone rates at a selected sample index.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `tier` | string | yes | `t1`, `t2`, `t3`, or `autonomous` |
| `over_erasure` | RateWithCI | yes | From selected sample scoring |
| `over_retention` | RateWithCI | yes | From selected sample scoring |
| `mis_escalation` | RateWithCI | yes | From selected sample scoring |

**Validation**:
- Rate numerators/denominators MUST match embedded scoring for the selected `sample_index`.
- Zero-denominator rule applies per rate (same as `AdjudicationMetricsTable`).

**Prohibited fields**: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.

## CrossTierComparisonTable

Four-row side-by-side comparison across the ablation ladder.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sample_index` | int | yes | Sample used for all four rows (0..4) |
| `rows` | list[CrossTierMetricRow] | yes | Length exactly 4 |

**Validation**:
- `rows` MUST contain exactly one row per tier: `t1`, `t2`, `t3`, `autonomous` (set equality).
- Row order in serialized JSON is not semantically constrained; acceptance tests verify tier set and rate fidelity.
- Pydantic validator MUST reject construction if tier set is incomplete or prohibited fields present.

**Prohibited fields**: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.

**Library-only**: Not emitted by CLI in v1. Built via `build_cross_tier_comparison(t1, t2, t3, autonomous, sample_index=N)`.

## VarianceSummary (by reference)

Embedded unchanged from runner output. See [002/contracts/sweep-result.md](../002-context-tier-sweep/contracts/sweep-result.md).

| Field | Type | Notes |
|-------|------|-------|
| `over_erasure` | RateVariance | Cross-sample comparison for over-erasure |
| `over_retention` | RateVariance | Cross-sample comparison for over-retention |
| `mis_escalation` | RateVariance | Cross-sample comparison for mis-escalation |

Report layer MUST NOT recompute variance; passthrough only.

## GateReportTables (CLI gate subcommand output, by reference)

When `dpdp-eval adversarial-gate` runs, JSON/`--output` payload is `GateReportTables` from Feature 003 — not an adjudication type. See [003/contracts/gate-report.md](../003-adversarial-gate/contracts/gate-report.md).

## Type location map

| Type | Module |
|------|--------|
| `AdjudicationMetricsTable` | `report/adjudication_types.py` |
| `SampleMetricsSummary` | `report/adjudication_types.py` |
| `TierAdjudicationReportTables` | `report/adjudication_types.py` |
| `CrossTierMetricRow` | `report/adjudication_types.py` |
| `CrossTierComparisonTable` | `report/adjudication_types.py` |
| `RateWithCI`, `WilsonInterval` | `report/types.py` |
| `GateReportTables` | `report/types.py` |

## Builder functions

| Function | Input | Output |
|----------|-------|--------|
| `build_tier_adjudication_report(sweep, *, sample_index=0, confidence_level=0.95)` | `TierSweepResult` \| `AutonomousSweepResult` | `TierAdjudicationReportTables` |
| `build_cross_tier_comparison(t1, t2, t3, autonomous, *, sample_index=0, confidence_level=0.95)` | Four sweep results | `CrossTierComparisonTable` |
| `format_adjudication_report(tables)` | `TierAdjudicationReportTables` | `str` (human stdout) |
| `format_cross_tier_comparison(table)` | `CrossTierComparisonTable` | `str` (human/debug) |

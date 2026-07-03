# Data Model: 002-context-tier-sweep

**Date**: 2026-07-02  
**Feature**: Context-tier adjudication sweep

This document defines runner-layer types only. Core domain entities (`AdjudicationSubject`, `ModelVerdict`, `ExpectedLabel`, `ContextBundle`, `CacheKey`, `AdjudicationScoringResult`, `Rate`, `Tier`, etc.) live in `core/types.py` and are documented in [001/data-model.md](../001-shared-core/data-model.md). Runner types **reference** those shapes; they do not redefine them.

## SweepConfig

Runtime configuration assembled at runner initialization.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `tier` | `Tier` (`t1` \| `t2` \| `t3`) | yes | Selects builder and cache `runner_id` |
| `runner_id` | string | yes | Must equal `tier` (`t1`, `t2`, `t3`) |
| `model_id` | string | yes | From `MODEL_ID` env (default `primary`) |
| `cache_mode` | string | yes | From `CACHE_MODE` env (`offline` default) |
| `sample_indices` | list[int] | yes | Fixed `[0, 1, 2, 3, 4]` for N=5 |
| `export_dir` | path | optional | Default repo `export/` |
| `cache_root` | path | optional | Default repo `cache/` |

**Validation**:
- `sample_indices` MUST be exactly `{0,1,2,3,4}` in this feature.
- `runner_id` MUST match `tier`.
- `cache_mode` MUST be `offline` or `refresh`.

## ContextBuilderRef

Logical reference (not necessarily a persisted type) mapping tier to Feature 001 builder:

| Tier | Callable | Extra inputs |
|------|----------|--------------|
| `t1` | `build_t1` | `request`, `subject` |
| `t2` | `build_t2` | `request`, `subject` |
| `t3` | `build_t3` | `request`, `subject`, `rules: RulesCorpus` |

See [001/contracts/context-tiers.md](../001-shared-core/contracts/context-tiers.md).

## PerCaseResult

Intermediate result for one subject at one sample index (audit/debug; optional in final serialized output).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subject_id` | string | yes | Export `subject_id` |
| `sample_index` | int | yes | 0..4 |
| `tier` | `Tier` | yes | |
| `runner_id` | string | yes | |
| `context_tier` | `Tier` | yes | Echo of bundle.tier |
| `pairs` | list[tuple[ModelVerdict, ExpectedLabel]] | yes | Aligned by `location_id`; may be empty |
| `skipped` | boolean | yes | `true` when subject has no scorable locations |
| `prompt_hash` | string | optional | From cache key; aids cache audit |

**Validation**:
- Each pair's `ModelVerdict.location_id` MUST match an export location's `location_id`.
- Ground truth MUST come from `LabeledLocation.expected` only.
- When `skipped` is `false` and context has N locations, `pairs` MUST have length N.

## SampleRollup

One full subject sweep at a fixed sample index.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sample_index` | int | yes | 0..4 |
| `scoring` | `AdjudicationScoringResult` | yes | From `score_adjudication` over all pairs in the sweep |
| `total_subjects` | int | yes | Count of export subjects visited |
| `scored_location_pairs` | int | yes | Equals `scoring.total_cases` |

**Relationships**: Five `SampleRollup` instances compose one `TierSweepResult`.

## RateAtSample

Single standalone rate at one sample index (building block for variance).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sample_index` | int | yes | 0..4 |
| `rate` | `Rate` | yes | Reuses core `Rate` type |

## RateVariance

Cross-sample comparison for one standalone metric.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metric` | enum | yes | `over_erasure` \| `over_retention` \| `mis_escalation` |
| `by_sample` | list[RateAtSample] | yes | Length 5, ordered by `sample_index` |
| `constant_across_samples` | boolean | yes | `true` iff all five `rate.value` fields are equal (including all `null`) |

## VarianceSummary

Runner-level rollup across the five sample runs.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `over_erasure` | `RateVariance` | yes | |
| `over_retention` | `RateVariance` | yes | |
| `mis_escalation` | `RateVariance` | yes | |

**Prohibited fields**: blended accuracy, micro-F1, or any single headline score (inherits [001/contracts/scoring.md](../001-shared-core/contracts/scoring.md) prohibition).

## TierSweepResult (Runner output)

Complete result for one tier execution.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `tier` | `Tier` | yes | |
| `runner_id` | string | yes | |
| `model_id` | string | yes | |
| `cache_mode` | string | yes | Mode used for this run |
| `export_agent_sha` | string | yes | From verified manifest |
| `samples` | list[SampleRollup] | yes | Exactly five entries |
| `variance` | `VarianceSummary` | yes | |
| `started_at` | string (ISO datetime) | optional | Audit metadata |
| `finished_at` | string (ISO datetime) | optional | Audit metadata |

**Validation**:
- `len(samples) == 5`.
- Each `samples[i].sample_index == i`.
- No field named `accuracy`, `f1`, or equivalent blended metric.

## Relationships

```text
SweepConfig 1 — 1 TierRunner session
ExportBundle 1 — * PerCaseResult (subjects × samples)
PerCaseResult * — * pairs (ModelVerdict, ExpectedLabel)

SampleRollup 1 — 1 AdjudicationScoringResult (core type)
TierSweepResult 1 — 5 SampleRollup
TierSweepResult 1 — 1 VarianceSummary
VarianceSummary 1 — 3 RateVariance

CacheKey (core) ← make_cache_key(context, model_id, runner_id, case_id=subject_id, sample_index)
```

## Type placement (implementation guidance)

| Type | Suggested module | Notes |
|------|------------------|-------|
| `SweepConfig`, `PerCaseResult`, `SampleRollup`, `RateAtSample`, `RateVariance`, `VarianceSummary`, `TierSweepResult` | `runners/types.py` or inline in `runners/spine.py` | Pydantic models mirroring `core/types.py` style |
| Core entities | `core/types.py` | Do not duplicate |

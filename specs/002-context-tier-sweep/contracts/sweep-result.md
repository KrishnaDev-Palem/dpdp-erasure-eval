# Sweep Result Contract

**Version**: 1.0.0  
**Feature**: 002-context-tier-sweep  
**Authority**: Spec FR-010–FR-013, FR-011; planning section 5 scoring semantics

## Purpose

Define the runner output schema for a completed tier sweep: five per-sample aggregate adjudication results plus a cross-sample variance summary.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Adjudication scoring shape | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |
| Core result types | [001/data-model.md](../../001-shared-core/data-model.md) (`AdjudicationScoringResult`, `Rate`) |
| Runner data model extensions | [../data-model.md](../data-model.md) |

## Top-level: TierSweepResult

One object returned by `run_t1_sweep`, `run_t2_sweep`, or `run_t3_sweep`.

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `tier` | `"t1"` \| `"t2"` \| `"t3"` | Context tier executed |
| `runner_id` | string | Cache namespace; equals `tier` |
| `model_id` | string | Model role used for cache keys |
| `cache_mode` | string | `offline` or `refresh` |
| `export_agent_sha` | string | 40-char hex from verified manifest |
| `samples` | array[SampleRollup] | Length exactly 5 |
| `variance` | VarianceSummary | Cross-sample rate comparison |

### Optional audit fields

| Field | Type | Description |
|-------|------|-------------|
| `started_at` | ISO 8601 datetime | Run start |
| `finished_at` | ISO 8601 datetime | Run end |

### Prohibited fields

MUST NOT include: `accuracy`, `micro_f1`, `blended_score`, or any single headline metric substituting for over-erasure (inherits scoring contract prohibition).

## SampleRollup

One entry per `sample_index` in `samples`, ordered 0 → 4.

| Field | Type | Description |
|-------|------|-------------|
| `sample_index` | int | 0..4 |
| `scoring` | AdjudicationScoringResult | Aggregate over **all** subjects in the sweep |
| `total_subjects` | int | Subjects visited |
| `scored_location_pairs` | int | Must equal `scoring.total_cases` |

### AdjudicationScoringResult (embedded)

Reuses core shape without modification:

| Field | Description |
|-------|-------------|
| `confusion_matrix` | 3×3 counts; rows=predicted, cols=actual (`erase`, `retain`, `escalate`) |
| `over_erasure_rate` | Standalone `Rate` |
| `over_retention_rate` | Standalone `Rate` |
| `mis_escalation_rate` | Standalone `Rate` |
| `total_cases` | Total graded location pairs |

See [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) for numerators/denominators.

## VarianceSummary

Compares the three standalone rates across the five sample rollups.

| Field | Type | Description |
|-------|------|-------------|
| `over_erasure` | RateVariance | |
| `over_retention` | RateVariance | |
| `mis_escalation` | RateVariance | |

## RateVariance

| Field | Type | Description |
|-------|------|-------------|
| `metric` | string | `over_erasure`, `over_retention`, or `mis_escalation` |
| `by_sample` | array[RateAtSample] | Length 5; ordered by `sample_index` |
| `constant_across_samples` | boolean | See rule below |

### RateAtSample

| Field | Type |
|-------|------|
| `sample_index` | int |
| `rate` | Rate |

### Constancy rule

`constant_across_samples` is `true` when, for all five entries in `by_sample`, the `rate.value` fields are equal (including the case where all are `null` because denominators are zero).

When `false`, acceptance tests and human reviewers MUST treat sample variance as present for that metric — without collapsing to a single blended number.

## Example shape (illustrative)

```json
{
  "tier": "t1",
  "runner_id": "t1",
  "model_id": "primary",
  "cache_mode": "offline",
  "export_agent_sha": "abc123...",
  "samples": [
    {
      "sample_index": 0,
      "total_subjects": 12,
      "scored_location_pairs": 38,
      "scoring": {
        "confusion_matrix": { "...": "..." },
        "over_erasure_rate": { "numerator": 1, "denominator": 38, "value": 0.02631578947368421 },
        "over_retention_rate": { "numerator": 2, "denominator": 38, "value": 0.05263157894736842 },
        "mis_escalation_rate": { "numerator": 0, "denominator": 38, "value": 0.0 },
        "total_cases": 38
      }
    }
  ],
  "variance": {
    "over_erasure": {
      "metric": "over_erasure",
      "by_sample": [
        { "sample_index": 0, "rate": { "numerator": 1, "denominator": 38, "value": 0.02631578947368421 } }
      ],
      "constant_across_samples": true
    },
    "over_retention": { "...": "..." },
    "mis_escalation": { "...": "..." }
  }
}
```

(Full `samples` array omitted for brevity; production output MUST include all five indices.)

## Validation rules

1. `len(samples) == 5` and `samples[i].sample_index == i` for all i.
2. Each sample's scoring MUST be reproducible from the same committed cache in offline mode (SC-008).
3. Hand-calculated rates from underlying pairs MUST match embedded `Rate` values (SC-004).
4. Variance `by_sample` entries MUST reference the corresponding sample's scoring rates — not recomputed from a different pair set.

## Serialization

Runners MAY expose `TierSweepResult.model_dump(mode="json")` when implemented as Pydantic models. CLI/report writers (future features) consume this contract; this feature does not require a persisted JSON artifact on disk.

## Non-goals

- Per-subject variance tables
- Wilson confidence intervals
- Cross-tier merged metrics
- Blended accuracy reporting

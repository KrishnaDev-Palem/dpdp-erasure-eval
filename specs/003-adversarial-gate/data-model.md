# Data Model: 003-adversarial-gate

**Date**: 2026-07-03  
**Feature**: Adversarial gate evaluation

This document defines gate-runner and reporting-layer types only. Core domain entities (`AdversarialSeedCase`, `ClassifierResult`, `AdversarialScoringResult`, `Rate`, `CacheKey`, `CacheEntry`, etc.) live in `core/types.py` and are documented in [001/data-model.md](../001-shared-core/data-model.md). Feature 002 runner types (`SweepConfig`, `TierSweepResult`, `VarianceSummary`, etc.) live in `runners/types.py` and [002/data-model.md](../002-context-tier-sweep/data-model.md). Gate and report types **reference** those shapes; they do not redefine them.

## AttackFamily (taxonomy)

Stable identifier for per-family detection breakdown. Not a persisted Pydantic model in core — fixture `family` field uses these string values.

| ID | Required on | Notes |
|----|-------------|-------|
| `direct_override` | attack cases | Matches frozen seed `adv-erase-all` |
| `authority_spoof` | attack cases | Authority or role claim; matches seed `adv-admin-claim` |
| `obfuscated_injection` | attack cases | Encoded/obfuscated instruction |
| `scope_expansion` | attack cases | Scope-expansion smuggling |
| `exfiltration` | attack cases | Exfiltration-style prompts |

Benign cases MUST NOT set `family` (optional `null` / omitted).

## ExtendedAdversarialSlice (logical)

Loaded corpus for gate sweeps. Not a separate core type — a list of `AdversarialSeedCase` plus loader metadata.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `cases` | list[AdversarialSeedCase] | yes | Stable fixture order |
| `source_path` | path | optional | Audit: `fixtures/adversarial_slice/cases.yaml` |
| `seed_check_passed` | boolean | optional | True when export seed cross-check succeeded |

**Validation** (see [contracts/adversarial-slice.md](./contracts/adversarial-slice.md)):
- `len(cases)` ∈ [80, 100].
- Attack and benign counts each approximately 40–50.
- Three frozen seed `case_id`s present with byte-identical content to export.
- Each attack case has `family` ∈ taxonomy above.
- `case_id` values unique within slice.

## GateSweepConfig

Runtime configuration assembled at gate runner initialization. Analogous to Feature 002 `SweepConfig`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `runner_id` | string | yes | Fixed `adversarial_gate` |
| `model_id` | string | yes | From `MODEL_ID` env (default `primary`) |
| `cache_mode` | string | yes | From `CACHE_MODE` env (`offline` default) |
| `sample_indices` | list[int] | yes | Fixed `[0, 1, 2, 3, 4]` for N=5 |
| `slice_path` | path | optional | Default `fixtures/adversarial_slice/cases.yaml` |
| `cache_root` | path | optional | Default repo `cache/` |
| `verify_export_seeds` | boolean | optional | Default `true`; cross-check frozen seeds |

**Validation**:
- `runner_id` MUST be `adversarial_gate`.
- `sample_indices` MUST be exactly `{0,1,2,3,4}`.
- `cache_mode` MUST be `offline` or `refresh`.

## PerCaseGateResult

Intermediate result for one slice case at one sample index (audit/debug; optional in final serialized output).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `case_id` | string | yes | From slice case |
| `sample_index` | int | yes | 0..4 |
| `runner_id` | string | yes | `adversarial_gate` |
| `label` | SeedLabel | yes | Ground truth from fixture only |
| `family` | string \| null | optional | From fixture; attack cases only |
| `outcome` | ClassifierOutcome | yes | From classifier/cache |
| `flagged` | boolean | yes | `outcome == adversarial` |
| `prompt_hash` | string | optional | From cache key |

**Validation**:
- `label` MUST come from fixture metadata, never from model output.
- Seam/cache canonical payload MUST NOT include `label` or `family`.

## GateSampleRollup

One full slice sweep at a fixed sample index.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sample_index` | int | yes | 0..4 |
| `scoring` | AdversarialScoringResult | yes | From `score_adversarial` over all pairs |
| `total_cases` | int | yes | Count of slice cases visited |
| `scored_pairs` | int | yes | Equals `len(pairs)`; attack + benign |

**Relationships**: Five `GateSampleRollup` instances compose one `GateSweepResult`.

## GateRateAtSample

Single adversarial rate at one sample index (building block for gate variance).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sample_index` | int | yes | 0..4 |
| `rate` | Rate | yes | Reuses core `Rate` |

## GateRateVariance

Cross-sample comparison for one adversarial metric.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `metric` | enum | yes | `detection` \| `false_alarm` |
| `by_sample` | list[GateRateAtSample] | yes | Length 5, ordered by `sample_index` |
| `constant_across_samples` | boolean | yes | `true` iff all five `rate.value` fields equal (including all `null`) |

## GateVarianceSummary

Gate-level rollup across five sample runs.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `detection` | GateRateVariance | yes | |
| `false_alarm` | GateRateVariance | yes | |

**Prohibited fields**: blended accuracy, single headline score (inherits [001/contracts/scoring.md](../001-shared-core/contracts/scoring.md)).

## GateSweepResult (Runner output)

Complete result for one gate execution.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `runner_id` | string | yes | `adversarial_gate` |
| `model_id` | string | yes | |
| `cache_mode` | string | yes | Mode used for this run |
| `slice_case_count` | int | yes | Total cases in slice |
| `samples` | list[GateSampleRollup] | yes | Exactly five entries |
| `variance` | GateVarianceSummary | yes | |
| `started_at` | string (ISO datetime) | optional | Audit metadata |
| `finished_at` | string (ISO datetime) | optional | Audit metadata |

**Validation**:
- `len(samples) == 5`.
- Each `samples[i].sample_index == i`.
- No blended accuracy field.

## WilsonInterval (report layer)

Confidence interval bounds on a proportion. Lives in `report/types.py` — not in `core/types.py`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `lower` | float \| null | yes | Null when undefined (zero denominator) |
| `upper` | float \| null | yes | Null when undefined |
| `confidence_level` | float | yes | Default `0.95` |

**Validation**:
- When both bounds non-null, `0.0 <= lower <= upper <= 1.0` (within floating tolerance in tests).

## RateWithCI (report layer)

Core rate augmented with Wilson interval for table emission.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `rate` | Rate | yes | Reuses core `Rate`; point estimate from numerator/denominator |
| `interval` | WilsonInterval \| null | yes | Null when `rate.denominator == 0` |

**Note**: Does not replace or extend core `Rate` in `core/types.py`. Reporting layer wraps it.

## FamilyDetectionRow (report layer)

One row in the per-family detection breakdown table.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `family` | string | yes | Attack family ID |
| `detection` | RateWithCI | yes | Detection rate over attack cases in family only |

Families with zero attack cases in the scored pair set MUST be omitted from the table (not a zero rate from empty denominator).

## GateReportTables (report output)

Structured report emitted by `report/adversarial_tables.py`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `detection` | RateWithCI | yes | Overall detection rate + Wilson CI |
| `false_alarm` | RateWithCI | yes | Overall false-alarm rate + Wilson CI |
| `per_family` | list[FamilyDetectionRow] | yes | Ordered by stable family ID sort |
| `sample_index` | int \| null | optional | When report targets one sample rollup; null for aggregated view |

**Prohibited fields**: blended accuracy, micro-F1.

## Relationships

```text
GateSweepConfig 1 — 1 gate runner session
ExtendedAdversarialSlice 1 — * AdversarialSeedCase (core type)
PerCaseGateResult * — pairs (ClassifierResult, AdversarialSeedCase) at case × sample

GateSampleRollup 1 — 1 AdversarialScoringResult (core type)
GateSweepResult 1 — 5 GateSampleRollup
GateSweepResult 1 — 1 GateVarianceSummary
GateVarianceSummary 1 — 2 GateRateVariance

GateSampleRollup.scoring ──► GateReportTables (via report layer)
Rate (core) ──► RateWithCI ──► WilsonInterval

CacheKey (core) ← make_gate_cache_key(text, model_id, runner_id, case_id, sample_index)
  prompt_hash = prompt_hash({"text": note_text})
```

## Type placement (implementation guidance)

| Type | Suggested module | Notes |
|------|------------------|-------|
| `GateSweepConfig`, `PerCaseGateResult`, `GateSampleRollup`, `GateRateAtSample`, `GateRateVariance`, `GateVarianceSummary`, `GateSweepResult` | `runners/adversarial_gate/types.py` | Pydantic models mirroring `runners/types.py` style |
| `WilsonInterval`, `RateWithCI`, `FamilyDetectionRow`, `GateReportTables` | `report/types.py` | Reporting-only; do not add to `core/types.py` |
| `AdversarialSeedCase`, `ClassifierResult`, `AdversarialScoringResult`, `Rate`, `CacheKey` | `core/types.py` | Do not duplicate or extend |

## Scoring pair contract (unchanged from core)

Gate runner produces pairs for `score_adversarial`:

```text
list[tuple[ClassifierResult, AdversarialSeedCase]]
```

Flagged = `ClassifierResult.outcome == "adversarial"`. Detection and false-alarm numerators/denominators follow [001/contracts/scoring.md](../001-shared-core/contracts/scoring.md). Wilson intervals consume those numerators/denominators in the report layer only.

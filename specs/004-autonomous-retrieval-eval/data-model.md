# Data Model: 004-autonomous-retrieval-eval

**Date**: 2026-07-04  
**Feature**: Autonomous retrieval evaluation

This document defines retrieval-tool and autonomous-runner types only. Core domain entities (`AdjudicationSubject`, `ModelVerdict`, `ExpectedLabel`, `AdjudicationScoringResult`, `CacheKey`, `CacheEntry`, `ContextBundle`, etc.) live in `core/types.py` and are documented in [001/data-model.md](../001-shared-core/data-model.md). Feature 002 runner types (`SampleRollup`, `VarianceSummary`, etc.) live in `runners/types.py` and [002/data-model.md](../002-context-tier-sweep/data-model.md). This feature **references** those shapes; it does not redefine them.

## ToolCallTrace

Ordered record of one retrieval tool invocation during autonomous adjudication. Persisted in `CacheEntry.tool_calls`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sequence` | int | yes | 0-based order within session |
| `tool_name` | string | yes | `get_location_records`, `get_retention_floors`, or `get_governance_map` |
| `arguments` | dict[str, Any] | yes | JSON-serializable tool arguments |
| `result_summary` | dict[str, Any] | yes | Auditable summary per [tool-call-trace.md](./contracts/tool-call-trace.md) |

**Validation**:
- `sequence >= 0`; contiguous within session.
- `tool_name` MUST be one of the three registered retrieval tools.
- `arguments` and `result_summary` MUST NOT contain `expected` or ground-truth keys.

## AdjudicationSessionResult

Return type from `ModelSeam.adjudicate` when `tool_registry` is provided.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `verdicts` | list[ModelVerdict] | yes | One per pairing location |
| `tool_calls` | list[ToolCallTrace] | yes | Possibly empty |

**Relationships**: On refresh, `verdicts` → `CacheEntry.raw_response`; `tool_calls` → `CacheEntry.tool_calls`.

## ToolRegistry (protocol)

Runtime registry of filesystem-backed retrieval callables scoped to one `ExportBundle`.

| Method / property | Description |
|-------------------|-------------|
| `invoke(tool_name, arguments)` | Dispatch to registered tool; return JSON-serializable result |
| `tool_names` | Fixed set of three retrieval tool names |

Built via `build_retrieval_tool_registry(bundle: ExportBundle)`.

## LocationRecordsResult (logical tool response)

Not a separate persisted type — shape returned by `get_location_records`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subject_id` | string | yes | Requested subject |
| `locations` | list[dict] | yes | T2-equivalent business fields; no `expected` |
| `error` | string | optional | e.g. `subject_not_found` |

## RetentionFloorsResult (logical tool response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `retention_floors` | list[RetentionFloorRule] | yes | All five sectoral floors |

## GovernanceMapResult (logical tool response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `governance_map` | list[GovernanceMapEntry] | yes | Full export governance map |

## AutonomousSweepConfig

Runtime configuration assembled at autonomous runner initialization. Analogous to Feature 002 `SweepConfig` without a tier field.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `runner_id` | string | yes | Fixed `autonomous` |
| `model_id` | string | yes | From `MODEL_ID` env (default `primary`) |
| `cache_mode` | string | yes | From `CACHE_MODE` env (`offline` default) |
| `sample_indices` | list[int] | yes | Fixed `[0, 1, 2, 3, 4]` for N=5 |
| `export_dir` | path | optional | Default repo `export/` |
| `cache_root` | path | optional | Default repo `cache/` |

**Validation**:
- `runner_id` MUST be `autonomous`.
- `sample_indices` MUST be exactly `{0,1,2,3,4}`.
- `cache_mode` MUST be `offline` or `refresh`.

## PerSubjectAutonomousResult (optional audit)

Intermediate result for one subject at one sample index (debug/audit; optional in final output).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subject_id` | string | yes | Export subject |
| `sample_index` | int | yes | 0..4 |
| `runner_id` | string | yes | `autonomous` |
| `pairs` | list[tuple[ModelVerdict, ExpectedLabel]] | yes | Graded pairs |
| `tool_calls` | list[ToolCallTrace] | yes | From cache entry or live session |
| `prompt_hash` | string | optional | T1-canonicalized hash |
| `skipped` | boolean | yes | True when zero pairing locations |

## AutonomousSweepResult

Top-level output from `run_autonomous_sweep`. Reuses Feature 002 sample and variance types.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `runner_id` | string | yes | `autonomous` |
| `initial_context_tier` | `"t1"` | yes | Documents request-only pre-load |
| `model_id` | string | yes | Cache namespace component |
| `cache_mode` | string | yes | `offline` or `refresh` |
| `export_agent_sha` | string | yes | 40-char hex from verified manifest |
| `samples` | list[SampleRollup] | yes | Length exactly 5 |
| `variance` | VarianceSummary | yes | Reuses `runners/types.py` |
| `started_at` | ISO 8601 string | optional | Run start |
| `finished_at` | ISO 8601 string | optional | Run end |

**Validation**:
- `len(samples) == 5` and `samples[i].sample_index == i`.
- Each sample's `scored_location_pairs` equals `scoring.total_cases`.
- MUST NOT include `accuracy`, `micro_f1`, or `blended_score`.
- `runner_id` MUST NOT be `t1`, `t2`, `t3`, or `adversarial_gate`.

**Relationships**:
- Five `SampleRollup` entries aggregate all export subjects at each sample index.
- `VarianceSummary` compares over-erasure, over-retention, mis-escalation across samples.

## Cache entry (autonomous namespace)

Autonomous entries extend the shared [001 cache contract](../001-shared-core/contracts/cache.md):

| Component | Autonomous value |
|-----------|------------------|
| `runner_id` | `autonomous` |
| `prompt_hash` | SHA-256 of canonicalized T1 `ContextBundle` |
| `tool_calls` | Non-empty when model invoked tools; `[]` otherwise |
| `raw_response.verdicts` | list[ModelVerdict] JSON |

**Cardinality**: 6 export subjects × 5 sample indices = 30 committed entries for full offline CI (research R7).

## Entity relationship diagram

```text
ExportBundle
  ├── subjects[] ──► build_t1() ──► ContextBundle (initial context)
  │                      │
  │                      └──► make_cache_key(runner_id=autonomous)
  │
  └── rules ──► ToolRegistry
                  ├── get_location_records(subject_id)
                  ├── get_retention_floors()
                  └── get_governance_map()

ModelSeam.adjudicate(context, tool_registry=registry)
  └──► AdjudicationSessionResult
         ├── verdicts ──► pair_subject_verdicts ──► score_adjudication
         └── tool_calls ──► CacheEntry.tool_calls

AutonomousSweepResult
  ├── samples[0..4]: SampleRollup (scoring per sample)
  └── variance: VarianceSummary
```

## State transitions

### Cache resolve (per subject, per sample)

```text
[miss + offline] ──► CacheMissError (fail)
[miss + refresh] ──► live adjudicate with tools ──► write CacheEntry ──► replay
[hit]            ──► read CacheEntry ──► parse verdicts (no tool re-exec)
```

### Subject with empty locations

```text
visit subject ──► zero pairing IDs ──► skip model call ──► zero pairs appended ──► continue sweep
```

## Non-goals

- New scoring rate types (reuse `AdjudicationScoringResult`, `Rate`).
- Per-tool caching layers.
- Extending `Tier` literal with `autonomous` (autonomous is a runner, not a context tier).

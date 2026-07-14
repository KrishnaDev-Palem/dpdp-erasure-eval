# Data Model: 007-live-role-cache-seed

**Date**: 2026-07-12
**Feature**: Live role cache seeding

Feature 007 introduces **no new runtime types**. All entities below are data artifacts
(committed JSON files) or documented workflow states, shaped by existing types in
`core/types.py` ([001/data-model.md](../001-shared-core/data-model.md)) and Feature 006
adapters ([006/data-model.md](../006-live-model-seam/data-model.md)).

## LiveRoleCacheNamespace

A committed cache subtree keyed by live `MODEL_ID`. Exactly three exist after this feature:

| Namespace path | Role | Runner | Cases | Samples | Entries |
|----------------|------|--------|-------|---------|---------|
| `cache/claude-sonnet-5/t2/` | `claude-sonnet-5` | `t2` | 2 subjects | 0–4 | 10 |
| `cache/claude-sonnet-5/autonomous/` | `claude-sonnet-5` | `autonomous` | 2 subjects | 0–4 | 10 |
| `cache/gemini-3.5-flash/adversarial_gate/` | `gemini-3.5-flash` | `adversarial_gate` | 90 slice cases | 0–4 | 450 |

**Validation rules**:
- Namespace root MUST equal a registered live `role_id` from `core/model/roles.py`.
- No other live-role/runner combinations may be created (FR-001; research R1).
- `cache/primary/` and `export/` MUST show an empty diff on the feature branch — no
  modification, overwrite, deletion, or addition (FR-002; research R7).

## CommittedCacheEntry (existing schema, new instances)

Persisted at `{model_id}/{runner_id}/{case_id}/{prompt_hash}/{sample_index}.json` per
Feature 001 cache contract. Written by existing helpers during operator refresh; read by
offline replay. No schema changes (FR-014).

| Field | Type | Constraint for committed live-role entries |
|-------|------|--------------------------------------------|
| `model_id` | string | `claude-sonnet-5` or `gemini-3.5-flash`; matches directory segment |
| `runner_id` | string | `t2`, `autonomous`, or `adversarial_gate`; matches role binding |
| `case_id` | string | Subject id (tier/autonomous) or slice case id (gate) |
| `prompt_hash` | string | Canonical hash; matches directory segment |
| `sample_index` | int | 0–4 |
| `recorded_at` | ISO-8601 Z string | Refresh timestamp (informational; not compared in replay) |
| `raw_response` | object | Tier/autonomous: `{"verdicts": [{location_id, verdict, detail?}]}`; gate: `ClassifierResult` dump (`{"outcome", "detail"?}`) |
| `tool_calls` | list | Empty for `t2`/`adversarial_gate`; ordered `ToolCallTrace` dumps for `autonomous` |

**Validation rules**:
- Verdicts ∈ `{erase, retain, escalate}`, one per context location (adapter-enforced at
  refresh; replay parsers re-check).
- Gate outcome ∈ `{clean, adversarial}`.
- Autonomous `tool_calls` items MUST validate as `ToolCallTrace` with contiguous `sequence`;
  empty traces are schema-valid but flagged for human review (research R6).

## RunnerRoleBinding

Fixed mapping of in-scope runner path → live role (spec Key Entities; CHK029). Documented,
not coded — enforced by which namespaces are committed and which tests exist.

| Runner path | Live role | Credential (refresh only) |
|-------------|-----------|---------------------------|
| T2 tier sweep | `claude-sonnet-5` | `ANTHROPIC_API_KEY` |
| Adversarial gate | `gemini-3.5-flash` | `GEMINI_API_KEY` |
| Autonomous | `claude-sonnet-5` | `ANTHROPIC_API_KEY` |

Cross-combinations (e.g., `gemini-3.5-flash` T2) are out of scope; offline runs with an
unseeded combination fail with `CacheMissError` (no fallback).

## RefreshSweep (workflow state)

Operator opt-in run: `CACHE_MODE=refresh` + bound `MODEL_ID` + provider key → one CLI sweep
invocation per runner path (research R2).

**State transitions**:

```text
cold namespace ──refresh sweep──▶ fully seeded (10 | 450 | 10 entries)
partially seeded (interrupted) ──re-run refresh──▶ fully seeded
        (hits replay; only misses invoke the live adapter)
fully seeded ──offline parity check──▶ commit-ready (operator + reviewer checklist)
```

**Commit-readiness criteria** (quickstart Feature 006 SC-002 checklist):
1. Entry counts match the coverage matrix exactly.
2. Offline re-run of the same sweep exits 0 with byte-equal `--json` payload.
3. `git diff` touches only the two live-role namespaces (+ tests/docs).
4. Autonomous entries reviewed for tool-call traces.

## OfflineReplaySweep (workflow state)

Default run: `CACHE_MODE=offline` + live `MODEL_ID`, zero keys, zero network. Any missing
entry raises `CacheMissError` naming runner, case, and sample — no silent skip, no fallback
to `cache/primary/` or live calls (research R7).

**Relationships**: `RunnerRoleBinding` selects the namespace → `OfflineReplaySweep` reads
`CommittedCacheEntry` instances → existing replay parsers reconstruct
`ModelVerdict` / `ClassifierResult` / `AdjudicationSessionResult` → scoring and reports
unchanged from Features 002–005.

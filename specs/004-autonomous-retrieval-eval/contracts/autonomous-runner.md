# Autonomous Runner Contract

**Version**: 1.0.0  
**Feature**: 004-autonomous-retrieval-eval  
**Authority**: Spec FR-004–FR-019; planning section 4, section 7

## Purpose

Define the autonomous retrieval evaluation runner: sweep all export subjects with request-only initial context, enable tool-use during adjudication, persist tool-call traces in cache, pair verdicts against `expected` only, and aggregate via shared adjudication scoring. Mirrors Feature 002 runner spine patterns without modifying tier modules.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Frozen export loader | [001/contracts/frozen-export.md](../../001-shared-core/contracts/frozen-export.md) |
| Context tier builders (T1 initial context) | [001/contracts/context-tiers.md](../../001-shared-core/contracts/context-tiers.md) |
| Model seam | [001/contracts/model-seam.md](../../001-shared-core/contracts/model-seam.md) |
| Cache keying & modes | [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) |
| Adjudication scoring | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |
| Retrieval tools | [retrieval-tools.md](./retrieval-tools.md) |
| Tool-call traces | [tool-call-trace.md](./tool-call-trace.md) |
| Runner spine patterns (reference) | [002/contracts/runner-spine.md](../../002-context-tier-sweep/contracts/runner-spine.md) |
| Sweep result shape (reference) | [002/contracts/sweep-result.md](../../002-context-tier-sweep/contracts/sweep-result.md) |

## Model seam extension (autonomous only)

When `tool_registry` is provided to `ModelSeam.adjudicate`, the seam returns `AdjudicationSessionResult`:

| Field | Type | Description |
|-------|------|-------------|
| `verdicts` | list[ModelVerdict] | Per-location adjudication outcomes |
| `tool_calls` | list[ToolCallTrace] | Ordered retrieval invocations (possibly empty) |

When `tool_registry` is omitted (tier/gate default), return type remains `list[ModelVerdict]` — unchanged behavior.

Tier and gate runners MUST NOT pass `tool_registry`.

## Entry point

```text
run_autonomous_sweep(
  *,
  seam: ModelSeam,
  config: AutonomousSweepConfig | None = None,
  export_dir: Path | None = None,
  cache_root: Path | None = None,
) -> AutonomousSweepResult
```

Exposed from `runners/autonomous/runner.py`.

## Orchestration steps

### 1. Load and verify export

- Call `core.export.load_export(export_dir)`.
- Call `bundle.verify_provenance()` before any subject processing.
- On `ProvenanceError` or `ExportLoadError`, abort; do not partial-run.

### 2. Initialize configuration and tools

- Read `MODEL_ID`, `CACHE_MODE` via `core.model.load_model_config()` unless overridden in `AutonomousSweepConfig`.
- Construct `CacheStore(root=cache_root, cache_mode=...)`.
- Build `tool_registry = build_retrieval_tool_registry(bundle)`.
- `runner_id` MUST be `autonomous`.
- MUST NOT hardcode model identity or cache mode (FR-010).

### 3. Sample loop (outer)

For each `sample_index` in the configured list (`[0, 1, 2]` or `[0, 1, 2, 3, 4]`; default five):

1. Initialize empty list `all_pairs: list[tuple[ModelVerdict, ExpectedLabel]]`.
2. Execute subject loop (below).
3. Call `core.scoring.score_adjudication(all_pairs)` → `AdjudicationScoringResult`.
4. Append `SampleRollup` to results.

### 4. Subject loop (inner)

For each `AdjudicationSubject` in export order (stable, no silent skips):

1. **Build initial context** — `build_t1(request=subject.request, subject=subject)` only. MUST NOT pre-load records, retention floors, or governance map (FR-006).
2. **Pairing location IDs** — use export `subject.locations` IDs when context has empty locations (same rule as tier spine T1):
   ```text
   pairing_location_ids = export_location_ids if context.locations empty else context_location_ids
   ```
3. **Empty locations** — if no pairing IDs, append no pairs; continue (no model call).
4. **Cache key** — `make_cache_key(context=..., model_id=..., runner_id=autonomous, case_id=subject.subject_id, sample_index=...)`. Prompt hash is T1-canonicalized request-only context (FR-014).
5. **Resolve adjudication** — `resolve_autonomous_entry(...)` in `runners/autonomous/cache.py`:
   - Offline hit → parse `raw_response.verdicts`; read `tool_calls` from entry (no re-execution).
   - Offline miss → `CacheMissError` with identifying path (FR-011).
   - Refresh miss → `seam.adjudicate(context=..., case_id=..., tool_registry=registry)` → persist entry with `verdicts` and `tool_calls`.
6. **Validate coverage** — every `location_id` in `pairing_location_ids` MUST have exactly one verdict.
7. **Validate enum** — verdict ∈ {`erase`, `retain`, `escalate`}; otherwise validation error naming `subject_id`, `location_id`, `sample_index`.
8. **Pair** — `pair_subject_verdicts(...)` appends `(ModelVerdict, location.expected)` to `all_pairs`. Ground truth from `expected` block only (FR-008).

### 5. Variance summary

Call `runners.variance.compute_variance_summary(sample_rollups)` → `VarianceSummary` (FR-018).

### 6. Return

Assemble `AutonomousSweepResult` with metadata (`runner_id=autonomous`, `model_id`, `cache_mode`, `export_agent_sha`, `initial_context_tier=t1`).

## Ground-truth isolation

- Initial context MUST NOT include `expected`, `strata`, or `cell_id` (enforced by `build_t1` and the T2-equivalent location dump used by retrieval tools). `parent_customer` and `latest_txn_date` stay when present.
- Tool responses MUST NOT include `expected`, `strata`, or `cell_id` (enforced by retrieval tools contract).
- Runners MUST NOT infer labels from tool outputs or model outputs.
- Cache-canonicalized context for prompt hash MUST NOT include tool-call payloads (FR-014).

## Determinism

Re-running the same autonomous sweep in offline mode with the same committed cache MUST yield identical per-sample scoring results (SC-009).

## Error taxonomy

| Error | When | Behavior |
|-------|------|----------|
| `ProvenanceError` | Export pin mismatch | Abort before sweep |
| `ExportLoadError` | Malformed/missing export | Abort before sweep |
| `CacheMissError` | Offline cache miss | Fail at first miss; include `runner_id`, `subject_id`, `sample_index` |
| Validation error | Bad/missing verdict | Fail at offending location |
| `ModelResponseError` | Seam rejects response (refresh) | Propagate; no silent retry |

## Non-goals (this contract)

- CLI argument parsing
- Modifying tier runners or adversarial gate
- Wilson confidence intervals
- Blended accuracy reporting
- Pre-loading T2/T3 data into initial context

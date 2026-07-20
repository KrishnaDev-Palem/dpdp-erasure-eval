# Runner Spine Contract

**Version**: 1.0.0  
**Feature**: 002-context-tier-sweep  
**Authority**: Spec FR-001–FR-004, FR-010, FR-012, FR-014; planning section 7

## Purpose

Define the shared orchestration flow all tier runners MUST implement. Tier runners differ only in `runner_id` and which Feature 001 context builder is invoked.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Frozen export loader | [001/contracts/frozen-export.md](../../001-shared-core/contracts/frozen-export.md) |
| Context tier builders | [001/contracts/context-tiers.md](../../001-shared-core/contracts/context-tiers.md) |
| Model seam | [001/contracts/model-seam.md](../../001-shared-core/contracts/model-seam.md) |
| Cache keying & modes | [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) |
| Adjudication scoring | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |

## Entry point

```text
run_tier_sweep(
  *,
  tier: Tier,
  seam: ModelSeam,
  config: SweepConfig | None = None,
  export_dir: Path | None = None,
  cache_root: Path | None = None,
) -> TierSweepResult
```

Tier modules (`runners/t1.py`, etc.) MAY expose thin aliases:

```text
run_t1_sweep(**kwargs) -> TierSweepResult  # tier=t1, runner_id=t1, builder=build_t1
```

## Orchestration steps

### 1. Load and verify export

- Call `core.export.load_export(export_dir)`.
- Call `bundle.verify_provenance()` before any subject processing.
- On `ProvenanceError` or `ExportLoadError`, abort; do not partial-run.

### 2. Initialize configuration

- Read `MODEL_ID`, `CACHE_MODE` via `core.model.load_model_config()` unless overridden in `SweepConfig`.
- Construct `CacheStore(root=cache_root, cache_mode=...)`.
- MUST NOT hardcode model identity or cache mode in runner logic (FR-005).

### 3. Sample loop (outer)

For each `sample_index` in `{0, 1, 2, 3, 4}`:

1. Initialize empty list `all_pairs: list[tuple[ModelVerdict, ExpectedLabel]]`.
2. Execute subject loop (below).
3. Call `core.scoring.score_adjudication(all_pairs)` → `AdjudicationScoringResult`.
4. Append `SampleRollup` to results.

### 4. Subject loop (inner)

For each `AdjudicationSubject` in export order (stable, no silent skips):

1. **Build context** — invoke tier builder:
   - T1/T2: `build_t1` / `build_t2(request=subject.request, subject=subject)`
   - T3: `build_t3(request=subject.request, subject=subject, rules=bundle.rules)`
2. **Empty locations** — if context has zero locations, append no pairs; continue (no model call required).
3. **Cache key** — `core.cache.make_cache_key(context=..., model_id=config.model_id, runner_id=config.runner_id, case_id=subject.subject_id, sample_index=...)`.
4. **Resolve verdicts** — `CacheStore.get_or_refresh(key=..., context=..., seam=seam)`:
   - Offline miss → propagate `CacheMissError` with identifying path (FR-006, US3 scenario 4).
   - Refresh miss → `seam.adjudicate(context=..., case_id=subject.subject_id)` then persist entry.
5. **Parse verdicts** — extract `list[ModelVerdict]` from `CacheEntry.raw_response["verdicts"]`.
6. **Validate coverage** — every `location_id` in context locations MUST have exactly one verdict; extra or missing IDs → validation error (FR-012).
7. **Validate enum** — each verdict MUST be `erase`, `retain`, or `escalate`; otherwise validation error (edge case: no coercion).
8. **Pair** — for each location, append `(ModelVerdict, location.expected)` to `all_pairs`.

### 5. Variance summary

After five samples, compute `VarianceSummary` from the five `AdjudicationScoringResult` standalone rates. See [sweep-result.md](./sweep-result.md).

### 6. Return

Assemble `TierSweepResult` with metadata (`tier`, `runner_id`, `model_id`, `cache_mode`, `export_agent_sha` from manifest).

## Ground-truth isolation

- Runners MUST NOT pass `expected` fields to `ModelSeam` or include them in cache-canonicalized context (enforced by `core.context` builders).
- Runners MUST NOT read ground truth from business fields or rules text — only `LabeledLocation.expected` for pairing (FR-002).

## Determinism

Re-running the same tier sweep in offline mode with the same committed cache MUST yield identical per-sample scoring results (SC-008).

## Error taxonomy

| Error | When | Behavior |
|-------|------|----------|
| `ProvenanceError` | Export pin mismatch | Abort before sweep |
| `ExportLoadError` | Malformed/missing export | Abort before sweep |
| `CacheMissError` | Offline cache miss | Fail at first miss; include tier, subject_id, sample_index |
| Validation error | Bad/missing verdict | Fail at offending location |
| `ModelResponseError` | Seam rejects response (refresh path) | Propagate; no silent retry |

## Non-goals (this contract)

- CLI argument parsing
- Report table rendering
- Adversarial gate or autonomous retrieval flows
- Wilson confidence intervals

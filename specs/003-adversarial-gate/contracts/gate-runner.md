# Gate Runner Contract

**Version**: 1.0.0  
**Feature**: 003-adversarial-gate  
**Authority**: Spec FR-001–FR-012, FR-005–FR-011; planning section 4.3, section 7

## Purpose

Define the adversarial-gate runner orchestration: sweep the extended adversarial slice, classify note text via the injected model seam, score with shared adversarial primitives, and return per-sample results plus variance summary. Mirrors Feature 002 runner spine patterns without forking tier adjudication logic.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Model seam (`classify_note`) | [001/contracts/model-seam.md](../../001-shared-core/contracts/model-seam.md) |
| Adversarial scoring | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |
| Cache keying & modes | [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) |
| Frozen export seeds (cross-check) | [001/contracts/frozen-export.md](../../001-shared-core/contracts/frozen-export.md) |
| Extended slice fixture | [adversarial-slice.md](./adversarial-slice.md) |
| Gate sweep output | [gate-report.md](./gate-report.md) |
| Runner spine patterns (reference) | [002/contracts/runner-spine.md](../../002-context-tier-sweep/contracts/runner-spine.md) |
| Tier sweep result shape (reference) | [002/contracts/sweep-result.md](../../002-context-tier-sweep/contracts/sweep-result.md) |

## Entry point

```text
run_adversarial_gate_sweep(
  *,
  seam: ModelSeam,
  config: GateSweepConfig | None = None,
  slice_path: Path | None = None,
  cache_root: Path | None = None,
) -> GateSweepResult
```

Exposed from `runners/adversarial_gate/runner.py` (or `runners/adversarial_gate/__init__.py` re-export).

## Orchestration steps

### 1. Load extended slice

- Call `slice_loader.load_extended_slice(slice_path)`.
- When `config.verify_export_seeds` is true (default):
  1. Load export via `core.export.load_export(export_dir)`.
  2. Call `bundle.verify_provenance()` per [001/contracts/frozen-export.md](../../001-shared-core/contracts/frozen-export.md) — on `ProvenanceError`, abort before sweep start (mirrors Feature 002 runner spine).
  3. Cross-check the three frozen seed cases against `bundle.seeds` for byte-identical fields — on mismatch, abort with seed mismatch error.
- On slice validation failure, abort before sweep start.
- Do **not** load adjudication subjects for gate grading (export is used only for provenance + seed integrity check).

### 2. Initialize configuration

- Read `MODEL_ID`, `CACHE_MODE` via `core.model.load_model_config()` unless overridden in `GateSweepConfig`.
- Construct `CacheStore(root=cache_root, cache_mode=...)`.
- `runner_id` MUST be `adversarial_gate` (FR-008).
- MUST NOT hardcode model identity or cache mode in runner logic (FR-005).

### 3. Sample loop (outer)

For each `sample_index` in `{0, 1, 2, 3, 4}`:

1. Initialize empty list `all_pairs: list[tuple[ClassifierResult, AdversarialSeedCase]]`.
2. Execute case loop (below).
3. Call `core.scoring.score_adversarial(all_pairs)` → `AdversarialScoringResult`.
4. Append `GateSampleRollup` to results.

### 4. Case loop (inner)

For each `AdversarialSeedCase` in slice order (stable, no silent skips):

1. **Build cache payload** — canonical prompt identity is `{"text": case.text}` only (FR-009). Compute `prompt_hash` via `core.cache.prompt_hash`.
2. **Cache key** — `CacheKey(model_id=..., runner_id=adversarial_gate, case_id=case.case_id, prompt_hash=..., sample_index=...)`.
3. **Resolve classification** — gate cache helper:
   - Offline hit → parse `raw_response` into `ClassifierResult`.
   - Offline miss → propagate `CacheMissError` with path identifying `case_id`, `sample_index`, `runner_id` (FR-006, US4 scenario 4).
   - Refresh miss → `seam.classify_note(text=case.text, case_id=case.case_id)` then persist entry (FR-007).
4. **Validate outcome** — MUST be `clean` or `adversarial`; otherwise validation error naming `case_id` and `sample_index` (edge case: no coercion).
5. **Pair** — append `(ClassifierResult, case)` to `all_pairs`. Ground truth label and family come from fixture metadata only (FR-003).

### 5. Variance summary

After five samples, compute `GateVarianceSummary` from detection and false-alarm rates across the five `AdversarialScoringResult` values. See [gate-report.md](./gate-report.md).

### 6. Return

Assemble `GateSweepResult` with metadata (`runner_id`, `model_id`, `cache_mode`, `slice_case_count`).

## Ground-truth / label isolation

- Runners MUST pass only `text` (and optional audit `case_id`) to `ModelSeam.classify_note` — no request triple, record fields, or ground-truth label (FR-002).
- Cache canonical payload MUST contain `text` only — MUST NOT include `label`, `family`, or export `expected` blocks.
- Runners MUST NOT infer labels from note text (FR-003).

## Classifier input contract

Mirrors agent `screen_adversarial` gate per [001/contracts/model-seam.md](../../001-shared-core/contracts/model-seam.md):

| Seam argument | Gate runner supplies |
|---------------|---------------------|
| `text` | `case.text` |
| `case_id` | `case.case_id` (audit only; not ground truth) |

## Cache entry shape (gate)

Gate cache entries MUST conform to [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) for path layout, entry schema, and offline/refresh modes. Gate-specific differences only:

| Aspect | Gate rule |
|--------|-----------|
| `runner_id` | MUST be `adversarial_gate` |
| `prompt_hash` | SHA-256 of canonical `{"text": "<note>"}` — not a `ContextBundle` |
| `raw_response` | `ClassifierResult` shape: `{ "outcome": "clean" \| "adversarial", "detail": ... }` |
| `tool_calls` | MUST NOT be present (Feature 004 only) |

Path: `cache/{model_id}/adversarial_gate/{case_id}/{prompt_hash}/{sample_index}.json`

## Determinism

Re-running the same gate sweep in offline mode with the same committed cache MUST yield identical per-sample scoring results (SC-009).

## Error taxonomy

| Error | When | Behavior |
|-------|------|----------|
| Slice validation error | Missing family, duplicate id, out-of-range count | Abort before sweep |
| `ProvenanceError` | Export manifest/SHA mismatch during seed cross-check | Abort before sweep; do not expose case data for scoring |
| Seed mismatch error | Provenance passed but extended slice seed ≠ export seed | Abort before sweep |
| `CacheMissError` | Offline cache miss | Fail at first miss; include case_id, sample_index, runner_id |
| Validation error | Outcome ∉ {clean, adversarial} | Fail at offending case |
| Empty/whitespace text | Documented case | Still invoke classification or fail with documented validation error; no silent skip |

## Non-goals (this contract)

- CLI argument parsing
- Wilson interval computation (see [gate-report.md](./gate-report.md))
- Tier adjudication sweeps (Feature 002)
- Autonomous retrieval (Feature 004)
- Editing export seeds or adjudication subjects

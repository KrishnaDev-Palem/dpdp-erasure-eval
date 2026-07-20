# Research: 003-adversarial-gate

**Date**: 2026-07-03  
**Feature**: Adversarial gate evaluation (extended slice, gate runner, Wilson reporting)

## R1 — Gate runner module layout (planning section 7, spec FR-001)

**Decision**: Add `runners/adversarial_gate/` as a dedicated package with `runner.py` (orchestration), `slice_loader.py`, `cache.py` (gate-specific cache key + classify refresh), `variance.py`, and `types.py`. Mirror acceptance tests under `tests/gate/`. Tier runners (`runners/t1.py`, etc.) remain unchanged at the parent level.

**Rationale**: Spec FR-001 explicitly places the gate runner under `runners/adversarial_gate/`, distinguishing Evaluation 2 from the three flat tier entry modules shipped in Feature 002. A subdirectory keeps gate-specific concerns (slice loading, text-only prompt hashing, classify_note cache path) colocated without growing the tier spine. Planning section 7 treats adversarial gate as a separate evaluation executor beside tier runners.

**Alternatives considered**:
- `runners/adversarial_gate.py` (single flat module) — rejected; slice loader, cache helper, variance, and types exceed comfortable single-file scope (~200+ lines) and differ materially from tier spine.
- `core/gate/` — rejected; gate is orchestration, not shared library surface; violates Feature 001 boundary (runners orchestrate core, they are not part of `core/`).
- Extend `runners/spine.py` with adversarial mode — rejected; tier spine is tightly coupled to export subjects, context builders, and adjudication pairing; adversarial flow uses fixture slice, `classify_note`, and different scoring result type.

## R2 — Shared patterns vs tier spine duplication

**Decision**: Mirror Feature 002 orchestration shape (config from env → outer sample loop → inner case loop → aggregate score → variance summary) but implement a gate-specific runner module rather than parameterizing `runners/spine.py`. Reuse `core.model.load_model_config`, `core.cache.CacheStore`, `core.cache.prompt_hash`, `core.scoring.score_adversarial`, and variance constancy logic pattern from `runners/variance.py`.

**Rationale**: Feature 002 spine assumes `ExportBundle`, `ContextBundle`, `make_cache_key(context=...)`, and `score_adjudication`. Gate sweep inputs are `AdversarialSeedCase` fixtures, text-only cache identity, and `score_adversarial`. Forcing both into one spine would add branching complexity and risk label leakage through shared context paths. Copying the *loop structure* while keeping implementations separate matches spec FR-004 (use scoring primitives, don't reimplement rates) without unsafe abstraction.

**Alternatives considered**:
- Generic `runners/generic_sweep.py` with strategy injection — rejected; over-engineered for two evaluation families; YAGNI.
- Duplicate entire tier spine file — rejected; only loop shape is shared; gate module stays focused (~150 lines orchestration).

## R3 — Wilson confidence interval library/approach

**Decision**: Implement the Wilson score interval in `report/wilson.py` using stdlib `math` only. Default confidence level **95%** (`z = 1.96`). Input: core `Rate` (numerator, denominator, value). Output: `WilsonInterval` with `lower`, `upper`, and `confidence_level`. When `denominator == 0`, return `null` bounds (interval omitted).

**Rationale**: Spec assumption defers confidence level to plan phase; 95% is standard for thesis reporting tables. Wilson score interval is preferred over Wald (normal approximation) for proportions near 0 or 1 — common in adversarial detection with ~40–50 cases per class. Feature 001 explicitly deferred CIs from `core/scoring` to this feature's reporting layer (FR-016). Constitution VIII rejects unbounded deps; `scipy`, `statsmodels`, and `numpy` are unnecessary for closed-form Wilson on a handful of rates per report.

**Formula** (proportion \(\hat p = x/n\), critical value \(z\)):

\[
\text{center} = \frac{\hat p + z^2/(2n)}{1 + z^2/n}, \quad
\text{margin} = \frac{z \sqrt{\hat p(1-\hat p)/n + z^2/(4n^2)}}{1 + z^2/n}
\]

**Alternatives considered**:
- `scipy.stats` or `statsmodels.stats.proportion` — rejected; adds dependency for ~30 lines of arithmetic; violates bounded-deps guardrail without justification.
- Clopper-Pearson (exact binomial) — rejected; harder to hand-verify in acceptance tests; Wilson is planning section 5 default and sufficient for slice sizes.
- Wald interval — rejected; poor coverage at extreme proportions; acceptance fixtures include small-n family cuts.
- Implement in `core/scoring` — rejected; contradicts FR-016 and Feature 001 deferral.

## R4 — Extended adversarial slice fixture strategy

**Decision**:

1. **Location**: `fixtures/adversarial_slice/cases.yaml` — YAML list of case objects matching `AdversarialSeedCase` shape from `core/types.py`.
2. **Frozen seed inclusion**: The three export seeds (`adv-erase-all`, `adv-admin-claim`, `benign-extra-ask`) MUST appear in the extended slice with **byte-identical** `case_id`, `surface`, `text`, `label`, and `family` fields to `export/adversarial_seeds/seeds.yaml`. When `verify_export_seeds` is enabled, loader calls `load_export()` + `verify_provenance()` then compares seeds; aborts on `ProvenanceError` or seed field mismatch before sweep start.
3. **Additive authoring**: All new cases use new `case_id` values; no edits to export files or committed adjudication subjects.
4. **Coverage targets** (planning section 4.3): 80–100 total cases; ~40–50 attack, ~40–50 benign; five families at ~8–10 attack cases each; benign set includes instruction-like hard negatives.
5. **Family taxonomy** (stable snake_case IDs):

| Family ID | Description |
|-----------|-------------|
| `direct_override` | Direct instruction to ignore/bypass rules |
| `authority_spoof` | Authority or role claim |
| `obfuscated_injection` | Obfuscated or encoded instruction |
| `scope_expansion` | Scope-expansion smuggling |
| `exfiltration` | Exfiltration-style prompts |

6. **Type reuse**: Slice cases validate as `AdversarialSeedCase`; no parallel fixture type. `family` required on attack cases; omitted on benign.

**Rationale**: Reusing `AdversarialSeedCase` lets `score_adversarial` accept pairs without adapter types (scoring contract). Separate fixture directory preserves frozen-interface discipline — export seeds stay immutable while eval extends coverage. Single YAML file keeps clone-and-inspect simple; matches export seed file shape.

**Alternatives considered**:
- Loader merge at runtime only (fixture excludes seeds; loader appends export seeds) — acceptable variant but rejected for primary strategy; explicit inclusion in `cases.yaml` makes slice self-contained for reviewers counting cases without loading export.
- JSONL per family — rejected; splits complicate additive review and duplicate seed cross-check logic.
- New `AdversarialSliceCase` type — rejected; duplicates `AdversarialSeedCase` fields; violates data-model extend-don't-duplicate rule.

## R5 — Cache prompt identity for classify_note

**Decision**: Gate cache keys use `core.cache.prompt_hash({"text": case.text})` — minimal JSON dict with sorted-key canonicalization already supported by `canonicalize()`. `CacheKey` components: `model_id`, `runner_id=adversarial_gate`, `case_id`, `prompt_hash`, `sample_index`. Gate module provides `make_gate_cache_key(...)` wrapping manual `CacheKey` construction (existing `make_cache_key` requires `ContextBundle` for tier flows).

**Rationale**: Spec FR-009 and assumption: prompt hash from canonicalized note text only. `canonicalize` already accepts `dict[str, Any]` ([core/cache/canonicalize.py](../../core/cache/canonicalize.py)). No core change required.

**Cache entry shape** for gate:

```json
{
  "raw_response": {
    "outcome": "clean",
    "detail": null
  }
}
```

Refresh path calls `seam.classify_note(text=case.text, case_id=case.case_id)` and persists outcome.

**Alternatives considered**:
- Reuse `ContextBundle` with dummy tier — rejected; violates label-isolation spirit and bloats canonical payload.
- Extend `core.cache.make_cache_key` with optional text-only overload — deferred to implementation; gate-local helper avoids Feature 001 churn unless bugfix needed.

## R6 — N=5 sample sweep and variance (gate)

**Decision**: Same outer-sample loop as Feature 002 ([002/contracts/runner-spine.md](../002-context-tier-sweep/contracts/runner-spine.md)): five per-sample `AdversarialScoringResult` values covering the full slice; `GateVarianceSummary` tracks `detection_rate` and `false_alarm_rate` with `constant_across_samples` booleans.

**Rationale**: Planning section 9 fixes N=5; spec FR-010–FR-012. Reusing variance constancy semantics from `runners/variance.py` keeps cross-evaluation comparisons consistent.

**Alternatives considered**:
- Single-sample gate only — rejected; spec US4 requires five samples and variance summary.
- Per-case sample tables — rejected; out of scope (spec mirrors tier-runner deferral).

## R7 — Reporting module placement

**Decision**: Top-level `report/` package (not under `runners/`) with `wilson.py`, `adversarial_tables.py`, and `types.py`. Consumes `AdversarialScoringResult` from core; emits `GateReportTables` (primary rates + per-family detection table).

**Rationale**: Wilson CIs were explicitly deferred from Features 001 and 002 to this feature. Reporting is consumed by future writeup/CLI features; separating from runner keeps runner output as scored results while report layer adds presentation.

**Alternatives considered**:
- `runners/adversarial_gate/report.py` — rejected; report may later serve other evaluations; top-level matches planning section 7 module list.
- Wilson in runner — rejected; violates FR-016.

## R8 — Acceptance test strategy

**Decision**: Contract tests under `tests/gate/` using `FakeModelSeam`, hand-crafted scoring fixtures for Wilson/table tests (no runner required), and committed minimal cache for integration-style offline replay. Tests assert: full slice coverage, label isolation, config from env, five per-sample results, variance shape, Wilson bounds on representative numerators/denominators, per-family table rows, cache miss errors in offline mode.

**Rationale**: Constitution Principle II — tests exist before implementation and fail for absent gate behavior, not import/setup errors. Report tests can validate Wilson math independently of runner (US3 independent test).

**Alternatives considered**:
- Extend `tests/core/` only — rejected; gate is separate feature surface.
- Live API integration tests in CI — rejected; Principle IV.

## R9 — Dependencies and environment

**Decision**: No new runtime dependencies beyond Feature 001. Gate runner reads `MODEL_ID` and `CACHE_MODE` through `core.model.load_model_config()`. Optional refresh documented in quickstart; not executed in CI.

**Rationale**: Constitution VIII bounded-deps guardrail.

**Alternatives considered**:
- `tabulate` / `rich` for table emission — rejected; acceptance tests compare structured data; string formatting can use stdlib.
- CLI framework — rejected; out of scope.

## Resolved clarifications

| Item | Resolution |
|------|------------|
| Gate runner directory | `runners/adversarial_gate/` (R1) |
| Wilson confidence level | 95% (`z=1.96`) via stdlib (R3) |
| Wilson implementation location | `report/wilson.py`, not `core/scoring` (R3, FR-016) |
| Slice fixture path | `fixtures/adversarial_slice/cases.yaml` (R4) |
| Frozen seed strategy | Byte-identical inclusion + optional export cross-check (R4) |
| Attack family IDs | Five snake_case keys in taxonomy table (R4) |
| Cache prompt payload | `{"text": note}` via `prompt_hash` (R5) |
| Sample loop ordering | Outer sample, inner case (R6) |
| Tier spine reuse | Pattern only; separate gate runner module (R2) |

No open **NEEDS CLARIFICATION** items remain.

# Research: 002-context-tier-sweep

**Date**: 2026-07-02  
**Feature**: Context-tier adjudication sweep (T1/T2/T3 runners)

## R1 — Runner module layout (planning §7)

**Decision**: Add `runners/` at repository root with `runners/spine.py` (shared orchestration), `runners/pairing.py` and `runners/variance.py` (focused helpers), and thin tier entry modules `runners/t1.py`, `runners/t2.py`, `runners/t3.py`. Mirror acceptance tests under `tests/runners/`.

**Rationale**: Planning §7 places evaluation executors beside `core/` rather than inside it. Runners orchestrate core primitives; they are not part of the shared library surface. Separating `runners/` keeps Feature 001's `core/` package stable and makes the runner acceptance suite independently gateable.

**Alternatives considered**:
- `core/runners/` — rejected; blurs library vs orchestration boundaries and couples runner churn to core releases.
- Single monolithic `runners/tier_sweep.py` — rejected; three tier entrypoints aid discoverability and match planning runner naming (T1/T2/T3).
- CLI-first without runner modules — rejected; spec FR-014 requires reusable runner executors testable without CLI (CLI is out of scope).

## R2 — Shared spine vs duplicating tier logic in each runner

**Decision**: One shared spine function/class parameterized by `(tier, runner_id, context_builder)`. Tier runners are thin wrappers that supply the builder and `runner_id`. Context assembly, cache canonicalization, and scoring remain exclusively in Feature 001 (`core.context.build_t1/t2/t3`, `core.cache`, `core.scoring.score_adjudication`).

**Rationale**: Spec FR-014 mandates identical orchestration with only context assembly and `runner_id` differing. Feature 001 research R6 already rejected embedding tier templates in runners because it would duplicate tier logic across three files and drift from the context-tier contract. The spine captures the invariant loop (export load → subject iteration → cache lookup → seam adjudicate → pair → score); builders remain pure functions in `core/context/tiers.py`.

**Alternatives considered**:
- Three copy-paste runner implementations (~150 lines each) — rejected; violates FR-014, increases risk of pairing/scoring drift, and duplicates cache key wiring.
- Subclass hierarchy (`T1Runner`, `T2Runner`, `T3Runner`) with overridden hooks — acceptable pattern but unnecessary abstraction; a single spine with injected `ContextBuilder` callable and `runner_id: Tier` is simpler and matches existing functional style in `core/context/tiers.py`.
- Macro/template code generation for tiers — rejected; over-engineered for three fixed tiers.

## R3 — Cache-integrated adjudication path

**Decision**: Runners use `CacheStore.get_or_refresh` with keys from `core.cache.make_cache_key(context=..., model_id=..., runner_id=..., case_id=subject_id, sample_index=...)`. Offline mode (default) raises `CacheMissError` on miss with path-identifying message. Refresh mode delegates live fetch to injected `ModelSeam.adjudicate` and persists via `write_cache`.

**Rationale**: Feature 001 already implements filesystem cache layout, canonical prompt hashing, and refresh semantics ([001/contracts/cache.md](../001-shared-core/contracts/cache.md)). Runners should not fork cache behavior. `case_id` maps to `subject_id` per export convention; `runner_id` partitions tier namespaces (`t1`, `t2`, `t3`).

**Alternatives considered**:
- Runners call `ModelSeam` directly without cache layer — rejected; breaks offline CI and FR-006/FR-007.
- Per-tier cache roots — rejected; contract specifies single `cache/` tree keyed by `runner_id`.

## R4 — N=5 sample sweep orchestration

**Decision**: Outer loop over `sample_index ∈ {0,1,2,3,4}`; inner loop over all export subjects. Each sample index produces exactly one aggregate `AdjudicationScoringResult` covering all location pairs from the full subject sweep. Cache entries are distinct per `(runner_id, case_id, prompt_hash, sample_index)`.

**Rationale**: Spec FR-009–FR-011 and planning §9 bound sampling to N=5. Per-sample aggregate scoring (not per-subject tables) is the primary reporting unit per spec assumptions. Outer-sample loop keeps pairing lists independent and makes variance computation straightforward.

**Alternatives considered**:
- Inner sample loop per subject — rejected; produces per-subject sample tables outside spec scope and complicates aggregate scoring.
- Configurable N — rejected; planning §9 fixes N=5; unbounded samples violate cost discipline.

## R5 — Variance summary computation

**Decision**: After five per-sample `AdjudicationScoringResult` values, compute `VarianceSummary` with per-rate arrays indexed by `sample_index` and a `constant_across_samples` boolean per rate (true when all five `Rate.value` fields are equal, including all-`null` when denominators are zero).

**Rationale**: Spec FR-011 requires listing each standalone rate at every sample index and indicating constancy. Boolean flags keep output machine-readable for downstream reporting without implying blended accuracy.

**Alternatives considered**:
- Standard deviation / confidence intervals — rejected; out of scope (Wilson CIs deferred to Feature 003).
- Single headline variance score — rejected; violates standalone-rate discipline.

## R6 — Empty locations and unscorable subjects

**Decision**: When `subject.locations` is empty, context builders return empty location lists per [001/contracts/context-tiers.md](../001-shared-core/contracts/context-tiers.md). The spine skips model invocation for that subject (no location pairs) and continues the sweep. Subjects with locations require full verdict coverage.

**Rationale**: Spec edge cases and context-tier contract: do not fabricate records; empty subjects contribute zero pairs and do not block the sweep.

**Alternatives considered**:
- Fail sweep on empty-location subjects — rejected; contradicts spec assumption that empty lists do not block.
- Score empty subjects as implicit pass — rejected; no pairs means no contribution to denominators, not a synthetic success.

## R7 — Verdict validation and pairing

**Decision**: After cache replay, parse `raw_response.verdicts` into `ModelVerdict` objects. Require exactly one verdict per `location_id` present in the context bundle's locations (T1: zero locations → zero verdicts expected). Reject verdicts outside `{erase, retain, escalate}` with a validation error naming `subject_id`, `location_id`, and `sample_index`. Pair via `location_id` join to `LabeledLocation.expected`.

**Rationale**: Spec FR-012 and model-seam contract require alignment by `location_id` without silent drops. Invalid enum values must not be coerced.

**Alternatives considered**:
- Coerce unknown verdicts to `escalate` — rejected; hides model failures.
- Warn-and-continue on missing locations — rejected; violates FR-012.

## R8 — Acceptance test strategy

**Decision**: Contract tests under `tests/runners/` using `FakeModelSeam` for unit-level spine tests and committed minimal cache fixtures for integration-style offline replay. Tests assert: full subject coverage, ground-truth isolation (no `expected` in bundles passed to seam/cache), config from env, five per-sample results, variance shape, cache miss errors in offline mode.

**Rationale**: Constitution Principle II — tests exist before implementation and fail for absent runner behavior, not import/setup errors.

**Alternatives considered**:
- Extend `tests/core/` only — rejected; runners are a separate feature surface; mirroring layout aids navigation.
- Live API integration tests in CI — rejected; violates Principle IV.

## R9 — Dependencies and environment

**Decision**: No new runtime dependencies beyond Feature 001. Runners read `MODEL_ID` and `CACHE_MODE` through `core.model.load_model_config()`. Optional refresh documented in quickstart; not executed in CI.

**Rationale**: Constitution VIII bounded-deps guardrail; runner layer adds orchestration only.

**Alternatives considered**:
- Add CLI framework (click/typer) — rejected; CLI out of scope.
- Add tqdm/rich for progress — rejected; unnecessary for acceptance suite and CI.

## Resolved clarifications

| Item | Resolution |
|------|------------|
| Runner directory location | `runners/` at repo root (R1) |
| Tier logic duplication | Forbidden; use `core.context` builders (R2) |
| Sample loop ordering | Outer sample, inner subject (R4) |
| Empty-location subjects | Skip adjudication; zero pairs (R6) |
| Cache case identity | `case_id = subject_id` (R3) |

No open **NEEDS CLARIFICATION** items remain.

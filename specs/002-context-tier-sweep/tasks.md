# Tasks: Context-Tier Adjudication Sweep

**Input**: Design documents from `/specs/002-context-tier-sweep/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, quickstart.md, research.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Every phase lists failing acceptance tests before implementation tasks.

**Organization**: Bootstrap → Foundational (shared spine) → User stories by tier → Polish

**Branch**: `002-context-tier-sweep`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US5) for story-phase tasks only
- FR/SC references trace tasks to spec requirements

## Path Conventions

- Runners: `runners/` at repository root
- Acceptance tests: `tests/runners/` mirroring runner modules
- Committed artifacts: `export/` (immutable), `cache/` (additive entries only)
- Core (Feature 001, consumed not modified): `core/`

---

## Phase 1: Bootstrap (Runner Layout & Failing Acceptance Suite)

**Purpose**: Scaffold runner package and test harness; write the full acceptance suite so it fails for missing runner behavior (not setup errors) before any orchestration code lands.

**Goal (US4)**: Acceptance suite defines done before implementation (FR-015, SC-001).

**Independent Test**: `uv run pytest tests/runners -v` on a clean clone — all runner tests fail with import or `NotImplementedError`/assertion failures attributable to missing runners, not missing export/core fixtures.

### Bootstrap Tasks

- [ ] T001 Create `runners/` package skeleton with empty `runners/__init__.py` per plan.md project structure (FR-014)
- [ ] T002 [P] Create `tests/runners/conftest.py` with shared fixtures: repo `export/` path, `cache/` root, `FakeModelSeam`, `CACHE_MODE=offline` default, and helpers to build minimal `SweepConfig` (FR-015, SC-001)
- [ ] T003 [P] Add minimal committed cache seed under `cache/primary/t1/` for at least one export subject covering `sample_index` 0–4 to unblock early offline assertions (FR-006, SC-005)
- [ ] T004 [P] [US4] Write failing `tests/runners/test_acceptance_runner_config.py` asserting `MODEL_ID` and `CACHE_MODE` are read from environment at runner init, not hardcoded literals (FR-004, FR-005, US4 scenario 4)
- [ ] T005 [P] [US4] Write failing `tests/runners/test_acceptance_context_isolation.py` asserting model-facing bundles never contain `expected` keys for all tiers (FR-003, US4 scenario 3)
- [ ] T006 [P] [US4] Write failing `tests/runners/test_acceptance_runner_spine.py` for export load, provenance abort, subject iteration, pairing by `location_id`, and offline determinism (FR-002, FR-012, FR-014, SC-008)
- [ ] T007 [P] [US1] Write failing `tests/runners/test_acceptance_t1_runner.py` for full T1 sweep: all subjects visited, `runner_id=t1`, per-lane confusion matrix, standalone rates, no blended accuracy (FR-001, FR-008, FR-013, SC-002, SC-007)
- [ ] T008 [P] [US2] Write failing `tests/runners/test_acceptance_t2_runner.py` for T2 context inclusion (records, no rules) and independent tier metrics (FR-001, FR-003, US2 scenarios 1 & 4)
- [ ] T009 [P] [US2] Write failing `tests/runners/test_acceptance_t3_runner.py` for T3 context inclusion (T2 + rules corpus) and `runner_id=t3` cache namespace (FR-001, FR-003, FR-008, US2 scenarios 2 & 3)
- [ ] T010 [P] [US3] Write failing `tests/runners/test_acceptance_sample_variance.py` for five per-sample rollups, variance summary with `constant_across_samples` flags, and explicit offline cache-miss failure (`cache_miss` marker) (FR-009, FR-011, US3 scenarios 1–4, SC-003, SC-004)
- [ ] T011 Verify Feature 001 prerequisite: `uv run pytest tests/core -v` passes on branch `002-context-tier-sweep`

**Checkpoint (Bootstrap — tests must fail for the right reason)**:

```bash
uv run pytest tests/runners -v --tb=short
```

**Expected**: All `tests/runners/` tests fail due to missing runner modules/behavior; `tests/core/` green. No network or API key required.

---

## Phase 2: Foundational — Shared Runner Spine

**Purpose**: Implement shared orchestration spine and runner-layer types so spine, config, and isolation acceptance tests pass before any tier wrapper lands.

**Goal**: Single `run_tier_sweep` flow reused by T1/T2/T3 (FR-014).

**Independent Test**: Spine acceptance tests pass with minimal cache seed; tier-specific sweep tests still fail until Phase 3+.

**Depends on**: Phase 1 complete (failing acceptance suite + conftest + minimal cache seed).

### Tests (already written in Phase 1 — confirm still failing until implementation)

> Tests T004–T006 MUST remain red until T012–T015 land. Do not implement tier modules in this phase.

### Implementation for Shared Spine

- [ ] T012 [P] Implement runner-layer Pydantic types in `runners/types.py`: `SweepConfig`, `PerCaseResult`, `SampleRollup`, `RateAtSample`, `RateVariance`, `VarianceSummary`, `TierSweepResult` per data-model.md and contracts/sweep-result.md (FR-010, FR-011, FR-013)
- [ ] T013 [P] Implement `location_id` alignment and verdict enum validation in `runners/pairing.py` — missing/extra verdicts fail validation; no silent drops (FR-012)
- [ ] T014 [P] Implement cross-sample rate comparison in `runners/variance.py` producing `VarianceSummary` with `constant_across_samples` per sweep-result contract (FR-011)
- [ ] T015 Implement `run_tier_sweep` in `runners/spine.py`: export load + provenance verify, env-driven config via `core.model.load_model_config()`, outer sample loop 0–4, subject iteration, cache key via `core.cache.make_cache_key`, `CacheStore.get_or_refresh`, pairing from `expected` only, `core.scoring.score_adjudication` per sample, variance rollup (FR-002, FR-006, FR-007, FR-009, FR-010, FR-014, SC-008)
- [ ] T016 Expand minimal committed cache under `cache/primary/t1/` so spine acceptance tests can replay at least one subject × five samples offline (FR-006)

**Checkpoint (Foundational — spine green, tier tests still red)**:

```bash
uv run pytest tests/runners/test_acceptance_runner_spine.py tests/runners/test_acceptance_runner_config.py tests/runners/test_acceptance_context_isolation.py -v
```

**Expected**: Spine, config, and isolation tests pass. T1/T2/T3 and sample-variance full-sweep tests may still fail pending tier wrappers and full cache.

---

## Phase 3: User Story 1 — T1 Request-Only Sweep (Priority: P1) 🎯 MVP

**Goal**: T1 runner sweeps every labeled export subject with request-only context, offline cache replay, and aggregate adjudication metrics (FR-001, FR-003).

**Independent Test**: Run T1 runner offline against committed export; every subject visited; each location graded against `expected` only; output includes per-lane confusion matrix and standalone rates with no blended accuracy (US1 independent test, SC-002, SC-007).

**Depends on**: Phase 2 complete (shared spine).

### Tests (already written — T007)

> Confirm `test_acceptance_t1_runner.py` fails until T017–T019 complete.

### Implementation for User Story 1

- [ ] T017 [US1] Implement thin `run_t1_sweep` wrapper in `runners/t1.py` delegating to `run_tier_sweep(tier="t1", runner_id="t1", builder=build_t1)` per contracts/tier-runner.md (FR-001, FR-008, FR-014)
- [ ] T018 [US1] Seed committed cache entries for **all** export subjects × `t1` × `sample_index` 0–4 under `cache/primary/t1/` (additive only; do not edit `export/`) (FR-006, FR-008, SC-003, SC-005)
- [ ] T019 [US1] Validate full T1 offline sweep: 100% subject coverage, deterministic replay, hand-check one sample's standalone rates against raw pairs (SC-002, SC-004, SC-008)

**Checkpoint (US1 — T1 sweep green)**:

```bash
uv run pytest tests/runners/test_acceptance_t1_runner.py -v
```

**Expected**: T1 acceptance tests pass offline with no API key. T2/T3 tests may still fail.

---

## Phase 4: User Story 2 — T2 and T3 Tier Sweeps (Priority: P1)

**Goal**: T2 (records-augmented) and T3 (rule-augmented) runners reuse the shared spine with tier-appropriate context builders and independent cache namespaces (FR-001, FR-014, US2).

**Independent Test**: Run T2 and T3 offline; context inclusion matches context-tier contract; `runner_id` values `t2`/`t3`; each tier reports its own metrics independently (US2 independent test, SC-002).

**Depends on**: Phase 3 complete (T1 validates spine + cache pattern).

### Tests (already written — T008, T009)

> Confirm T2/T3 acceptance tests fail until T020–T024 complete.

### Implementation for User Story 2

- [ ] T020 [P] [US2] Implement thin `run_t2_sweep` in `runners/t2.py` delegating to spine with `build_t2` (FR-001, FR-008, FR-014)
- [ ] T021 [P] [US2] Implement thin `run_t3_sweep` in `runners/t3.py` delegating to spine with `build_t3` and `export.rules` (FR-001, FR-008, FR-014)
- [ ] T022 [P] [US2] Seed committed cache entries for **all** export subjects × `t2` × `sample_index` 0–4 under `cache/primary/t2/` (FR-006, FR-008, SC-003, SC-005)
- [ ] T023 [P] [US2] Seed committed cache entries for **all** export subjects × `t3` × `sample_index` 0–4 under `cache/primary/t3/` (FR-006, FR-008, SC-003, SC-005)
- [ ] T024 [US2] Validate full T2 and T3 offline sweeps: subject coverage, tier-isolated metrics, no cross-tier cache overwrite (SC-002, US2 scenario 4)

**Checkpoint (US2 — all three tiers green)**:

```bash
uv run pytest tests/runners/test_acceptance_t2_runner.py tests/runners/test_acceptance_t3_runner.py -v
```

**Expected**: T2 and T3 acceptance tests pass offline. Sample-variance full-suite test may still fail until Phase 5 validation.

---

## Phase 5: User Story 3 — N=5 Sampling & Cross-Sample Variance (Priority: P2)

**Goal**: Each tier produces five per-sample aggregate scoring results and a variance summary comparing standalone rates across samples; offline cache miss fails explicitly (FR-009, FR-011, US3).

**Independent Test**: With committed cache for all five sample indices, run any tier offline; verify five rollups, variance summary with per-index rates and constancy flags; cache miss raises explicit error (US3 independent test, SC-003, SC-004).

**Depends on**: Phase 4 complete (full tier cache coverage for offline replay).

### Tests (already written — T010)

> Sample loop logic lives in spine (T015); this phase validates end-to-end N=5 behavior across full export with complete cache.

### Validation for User Story 3

- [ ] T025 [US3] Verify spine outer sample loop emits exactly five `SampleRollup` entries with `sample_index` 0–4 and distinct cache keys per `(runner_id, subject_id, sample_index)` (FR-009, SC-003)
- [ ] T026 [US3] Add hand-calculated rate parity assertions in `tests/runners/test_acceptance_sample_variance.py` for at least one tier/sample (SC-004)
- [ ] T027 [US3] Verify offline cache-miss test (`cache_miss` marker) fails with message identifying tier, `subject_id`, and `sample_index` — no silent live model call (FR-006, US3 scenario 4)
- [ ] T028 [US3] Verify `VarianceSummary.constant_across_samples` is correct when sample rates differ vs. identical (FR-011)

**Checkpoint (US3 — variance and cache-miss green)**:

```bash
uv run pytest tests/runners/test_acceptance_sample_variance.py -v
uv run pytest tests/runners -k cache_miss -v
```

**Expected**: Five per-sample results and variance summary pass; cache-miss behavior explicit.

---

## Phase 6: User Story 5 — Quickstart & On-Ramp Validation (Priority: P3)

**Goal**: Human-readable path reproduces green offline sweeps mirroring CI (FR-016, US5, SC-006).

**Independent Test**: Follow `specs/002-context-tier-sweep/quickstart.md` on a clean clone without API key; all three tier sweeps replay from committed cache (US5 independent test).

**Depends on**: Phases 3–5 complete (all tier runners + full cache + variance).

### Validation for User Story 5

- [ ] T029 [US5] Execute quickstart setup and full acceptance suite steps from `specs/002-context-tier-sweep/quickstart.md` (FR-016, SC-006)
- [ ] T030 [P] [US5] Run quickstart spot-check commands: T1 inline sweep, context isolation, cache miss, variance tests per quickstart.md sections
- [ ] T031 [US5] Confirm quickstart lint commands pass: `uv run ruff check .` and `uv run ruff format --check .`

**Checkpoint (US5 — quickstart path green)**:

```bash
uv run pytest tests/runners -v
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Matches CI merge-gate expectations for this feature; no API key; under 10 minutes on a standard dev machine (SC-006).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite gate, documentation on-ramp, vocabulary discipline.

**Depends on**: Phase 6 complete.

- [ ] T032 [P] Update `README.md` with thesis-first on-ramp: mention T1/T2/T3 tier sweep runners, link to `specs/002-context-tier-sweep/quickstart.md`, and document `uv run pytest tests/runners -v` offline path (FR-016, FR-017)
- [ ] T033 Run full offline runners acceptance suite and confirm SC-001: all tests green with `CACHE_MODE=offline` and no `MODEL_API_KEY` (SC-001)
- [ ] T034 [P] Audit runner modules and tests for vocabulary: T1/T2/T3, `runner_id`, `subject_id`, DPDP domain terms; no retired terms (`pillar`, `condition`) (FR-017)
- [ ] T035 Confirm no blended accuracy field in `TierSweepResult` or embedded scoring across all tier outputs (FR-013, SC-007)

**Final Checkpoint**:

```bash
uv run pytest tests/core -v
uv run pytest tests/runners -v
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Full feature definition of done — SC-001 through SC-008 satisfied offline.

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Bootstrap
    ↓
Phase 2 Foundational (spine — BLOCKS all tier work)
    ↓
Phase 3 US1 T1 (MVP)
    ↓
Phase 4 US2 T2/T3
    ↓
Phase 5 US3 N=5 variance validation
    ↓
Phase 6 US5 quickstart validation
    ↓
Phase 7 Polish
```

### User Story Dependencies

| Story | Priority | Depends On | Delivers |
|-------|----------|------------|----------|
| US4 | P2 | Phase 1 only | Failing acceptance suite before implementation (T004–T010) |
| US1 | P1 | Phase 2 spine | T1 full sweep (T017–T019) |
| US2 | P1 | Phase 3 T1 pattern | T2/T3 sweeps + full tier cache (T020–T024) |
| US3 | P2 | Phase 4 full cache | N=5 variance + cache-miss discipline (T025–T028) |
| US5 | P3 | Phases 3–5 | Quickstart reproducibility (T029–T031) |

### Critical Sequencing Rules

1. **Test-first (Principle II)**: T004–T010 (all acceptance tests) MUST complete before T012–T015 (spine implementation).
2. **Spine before tiers**: T015 MUST complete before T017, T020, T021.
3. **Cache before offline validation**: T018 before T019; T022/T023 before T024; full cache before T025–T028.
4. **No out-of-scope work**: No CLI entrypoints, `report/` modules, adversarial gate (Feature 003), or autonomous runner (Feature 004).

### FR/SC Traceability Matrix

| Requirement | Tasks |
|-------------|-------|
| FR-001 (three tier runners) | T007–T009, T017, T020–T021 |
| FR-002 (export loader, expected only) | T006, T015 |
| FR-003 (tier builders, no expected in context) | T005, T007–T009, T017, T020–T021 |
| FR-004 (injected ModelSeam) | T004, T015 |
| FR-005 (env MODEL_ID, CACHE_MODE) | T004, T015 |
| FR-006 (offline default, CI no key) | T003, T015–T018, T022–T023, T027, T033 |
| FR-007 (refresh path available) | T015 |
| FR-008 (runner_id t1/t2/t3) | T007–T009, T017–T018, T020–T023 |
| FR-009 (N=5 samples) | T010, T015, T025 |
| FR-010 (per-sample aggregate scoring) | T012, T015 |
| FR-011 (variance summary) | T010, T012, T014, T028 |
| FR-012 (location_id pairing) | T006, T013, T015 |
| FR-013 (confusion matrix, standalone rates) | T007, T012 |
| FR-014 (shared spine) | T001, T006, T015, T017, T020–T021 |
| FR-015 (acceptance suite before impl) | T002, T004–T010 |
| FR-016 (quickstart guide) | T029–T031, T032 |
| FR-017 (vocabulary) | T032, T034 |
| SC-001 (offline CI green) | T011, T033 |
| SC-002 (100% subject coverage) | T019, T024 |
| SC-003 (five per-sample results) | T018, T022–T023, T025 |
| SC-004 (hand-calculated rate parity) | T026 |
| SC-005 (additive fixtures only) | T003, T018, T022–T023 |
| SC-006 (quickstart under 10 min) | T029 |
| SC-007 (no blended accuracy) | T007, T035 |
| SC-008 (deterministic replay) | T006, T015, T019 |

---

## Parallel Execution Examples

### Phase 1 Bootstrap (after T001)

```bash
# Parallel: conftest + all acceptance test files + minimal cache seed
T002 tests/runners/conftest.py
T003 cache/primary/t1/ minimal seed
T004 test_acceptance_runner_config.py
T005 test_acceptance_context_isolation.py
T006 test_acceptance_runner_spine.py
T007 test_acceptance_t1_runner.py
T008 test_acceptance_t2_runner.py
T009 test_acceptance_t3_runner.py
T010 test_acceptance_sample_variance.py
```

### Phase 2 Foundational (after tests red)

```bash
# Parallel: types + pairing + variance modules
T012 runners/types.py
T013 runners/pairing.py
T014 runners/variance.py
# Then sequential: T015 spine.py (depends on T012–T014)
```

### Phase 4 US2 (after T1 green)

```bash
# Parallel: tier wrappers + cache seeding
T020 runners/t2.py
T021 runners/t3.py
T022 cache/primary/t2/
T023 cache/primary/t3/
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1: Bootstrap — all failing tests + conftest + minimal cache
2. Complete Phase 2: Foundational — shared spine green
3. Complete Phase 3: US1 T1 — full T1 cache + T1 tests green
4. **STOP and VALIDATE**: `uv run pytest tests/runners/test_acceptance_t1_runner.py -v`
5. Demo baseline T1 ablation tier before T2/T3

### Incremental Delivery

1. Bootstrap + Foundational → spine orchestration proven
2. US1 T1 → baseline tier sweep (MVP)
3. US2 T2/T3 → complete ablation ladder
4. US3 → N=5 variance and cache-miss hardening
5. US5 + Polish → quickstart on-ramp and README

### Parallel Team Strategy

With multiple developers after Phase 2:

- Developer A: Phase 3 US1 (T1 runner + T1 cache)
- Developer B: Begin T2/T3 wrapper stubs (blocked on spine — start cache seeding scripts for t2/t3)
- Developer C: Expand acceptance test fixtures in `tests/runners/conftest.py`

After Phase 3, Developers A/B parallelize Phase 4 tier wrappers and cache seeding (T020–T023).

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same batch
- US4 acceptance-suite-before-implementation is satisfied by Phase 1 tasks T004–T010 preceding all implementation
- Do not modify `core/` or `specs/001-shared-core/` except blocking bugfixes (out of scope)
- Do not edit committed `export/` content (Principle III); cache entries are additive only
- Refresh path (`CACHE_MODE=refresh`) remains available via spine but is not CI-gated (FR-007)
- Total tasks: **35** (Bootstrap 11, Foundational 5, US1 3, US2 5, US3 4, US5 3, Polish 4)

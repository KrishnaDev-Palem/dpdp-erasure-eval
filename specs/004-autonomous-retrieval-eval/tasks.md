# Tasks: Autonomous Retrieval Evaluation

**Input**: Design documents from `/specs/004-autonomous-retrieval-eval/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, quickstart.md, research.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Every phase lists failing acceptance tests before implementation tasks.

**Organization**: Bootstrap → Foundational (core seam extension + autonomous runner spine) → User stories by spec priority → Polish

**Branch**: `004-autonomous-retrieval-eval`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US6) for story-phase tasks only
- FR/SC references trace tasks to spec requirements

## Path Conventions

- Retrieval tools: `core/tools/` at repository root
- Autonomous runner: `runners/autonomous/` at repository root
- Acceptance tests: `tests/autonomous/` mirroring `core/tools/` and `runners/autonomous/`
- Committed cache: `cache/primary/autonomous/` (additive entries only)
- Core (Feature 001, extend minimally for seam/types): `core/`
- Tier runners & gate (Feature 002/003, reference only — do not modify): `runners/spine.py`, `runners/t1.py`–`t3.py`, `runners/adversarial_gate/`

---

## Phase 1: Bootstrap (Autonomous Layout & Failing Acceptance Suite)

**Purpose**: Scaffold `core/tools/`, `runners/autonomous/`, and test harness; write the full acceptance suite so it fails for missing autonomous behavior (not setup errors) before any implementation code lands.

**Goal (US5)**: Acceptance suite defines done before implementation (FR-020, SC-001).

**Independent Test**: `uv run pytest tests/autonomous -v` on a clean clone — all autonomous tests fail with import or `NotImplementedError`/assertion failures attributable to missing tools/runner modules, not missing export/core fixtures.

### Bootstrap Tasks

- [X] T001 Create `runners/autonomous/` package skeleton with empty `runners/autonomous/__init__.py` per plan.md project structure (FR-004)
- [X] T002 [P] Create `core/tools/` package skeleton with empty `core/tools/__init__.py` and a `core/tools/registry.py` stub exporting a `ToolRegistry` Protocol (callable dispatch interface only; full implementation in T022) per plan.md project structure (FR-001, U1 seam dependency)
- [X] T003 [P] Create `tests/autonomous/conftest.py` with shared fixtures: repo root, `export/` path, `cache/` root, `FakeModelSeam`, `CACHE_MODE=offline` default, helper to build minimal `AutonomousSweepConfig`, fixture helper for a subject with `locations=[]` (empty-location edge case), and hand-calculated adjudication rate parity builders for variance tests (FR-020, SC-001)
- [X] T004 [P] Add minimal committed cache seed under `cache/primary/autonomous/` for at least one export subject covering `sample_index` 0–4 to unblock early offline assertions (FR-011, FR-019, SC-010)
- [X] T005 [P] [US5] Write failing `tests/autonomous/test_acceptance_autonomous_config.py` asserting `MODEL_ID` and `CACHE_MODE` are read from environment at autonomous runner init, not hardcoded literals (FR-010, US5 scenario 4)
- [X] T006 [P] [US5] Write failing `tests/autonomous/test_acceptance_label_isolation.py` in two scoped groups: **`context_isolation`** — assert `expected` never appears in request-only initial context or T1-canonicalized cache payloads (runnable from Phase 2); **`tool_isolation`** — assert `expected` never appears in retrieval tool responses (requires Phase 3 tools). Use `@pytest.mark.context_isolation` and `@pytest.mark.tool_isolation` markers (FR-002, FR-006, US5 scenario 3)
- [X] T007 [P] [US1] Write failing `tests/autonomous/test_acceptance_retrieval_tools.py` for T2/T3 parity: `get_location_records` matches `build_t2` location fields (no `expected`), `get_retention_floors` and `get_governance_map` match T3 rules corpus, empty locations return `[]`, unknown subject returns documented error without cross-subject leakage, tools read export via loader only (FR-001–FR-003, US1 scenarios 1–5, SC-005)
- [X] T008 [P] [US3] Write failing `tests/autonomous/test_acceptance_tool_call_traces.py` for ordered `tool_calls` persistence, auditable argument/result summaries per tool-call-trace contract, offline replay reads traces without re-executing tools, tier-runner cache entries (`t1`/`t2`/`t3`) and gate entries lack non-empty `tool_calls` (FR-015, US3 scenarios 1–4, SC-006)
- [X] T009 [P] [US2] Write failing `tests/autonomous/test_acceptance_autonomous_runner.py` for full autonomous sweep: every export subject visited, `runner_id=autonomous`, request-only T1 initial context (no pre-loaded records/rules), tool-use enabled on adjudication, per-lane confusion matrix and standalone rates with no blended accuracy, pairing by `location_id` from `expected` only, empty-location subjects visited with zero pairs and no model call, invalid verdict enum rejection naming `subject_id`, `location_id`, and `sample_index`, offline determinism (FR-004–FR-009, FR-013, US2 scenarios 1–6, SC-002, SC-004, SC-009)
- [X] T010 [P] [US4] Write failing `tests/autonomous/test_acceptance_autonomous_sample_variance.py` for five per-sample rollups, variance summary with `constant_across_samples` flags, distinct cache keys per `(runner_id, subject_id, sample_index)` with T1 prompt hash, explicit offline cache-miss failure (`cache_miss` marker), and hand-calculated over-erasure/over-retention/mis-escalation rate parity for at least one sample from raw prediction–ground-truth pairs (FR-016–FR-018, US4 scenarios 1–4, SC-003, SC-004)
- [X] T011 [P] [US2] Write failing `tests/autonomous/test_acceptance_autonomous_cache_offline.py` for offline replay via `runner_id=autonomous`, cache prompt identity from T1-canonicalized request-only context only, refresh path opt-in via `@pytest.mark.refresh`, and cache-miss error naming `subject_id`, `sample_index`, `runner_id` (FR-011–FR-014, US2 scenario 5, US4 scenario 4, SC-010)
- [X] T012 Verify Feature 001, Feature 002, and Feature 003 prerequisites: `uv run pytest tests/core tests/runners tests/gate -v` passes on branch `004-autonomous-retrieval-eval`

**Checkpoint (Bootstrap — tests must fail for the right reason)**:

```bash
uv run pytest tests/autonomous -v --tb=short
```

**Expected**: All `tests/autonomous/` tests fail due to missing tools/runner modules/behavior; `tests/core/`, `tests/runners/`, and `tests/gate/` green. No network or API key required.

---

## Phase 2: Foundational — Core Seam Extension & Autonomous Runner Spine

**Purpose**: Implement shared types, model seam tool-use extension, `FakeModelSeam` support, autonomous runner types, and cache helper so config, context-scoped label-isolation, and trace-schema acceptance tests pass before retrieval tools and full sweep land.

**Goal**: Autonomous-specific infrastructure without tier/gate call-site changes (FR-007, FR-015).

**Independent Test**: Config and context-scoped label-isolation acceptance tests pass with minimal cache seed; tool-scoped label-isolation, retrieval-tools, full-sweep, and variance tests still fail until Phases 3–4.

**Depends on**: Phase 1 complete (failing acceptance suite + conftest + minimal cache seed).

### Tests (already written in Phase 1 — confirm still failing until implementation)

> Tests T007–T011 MUST remain red until Phases 3–4 land. Do not seed full 10-entry cache in this phase.

### Implementation for Foundational Spine

- [X] T013 [P] Add `ToolCallTrace` and `AdjudicationSessionResult` Pydantic models to `core/types.py` per data-model.md and contracts/tool-call-trace.md; validate `tool_name` enum and no `expected` keys in trace payloads. Confirm `ToolRegistry` Protocol stub from T002 in `core/tools/registry.py` is importable by `core/model/seam.py` (FR-015)
- [X] T014 Extend `ModelSeam.adjudicate` in `core/model/seam.py` with optional keyword-only `tool_registry: ToolRegistry | None = None` (import `ToolRegistry` from `core.tools.registry`): default path returns `list[ModelVerdict]` unchanged; with registry returns `AdjudicationSessionResult` per contracts/autonomous-runner.md. Depends on T013 and T002 registry stub (FR-007)
- [X] T015 [P] Update `FakeModelSeam` in `core/model/fake.py` to invoke configured tools and record `ToolCallTrace` entries when `tool_registry` is provided; preserve unchanged behavior for tier/gate callers (FR-007, US3)
- [X] T016 [P] Implement autonomous runner Pydantic types in `runners/autonomous/types.py`: `AutonomousSweepConfig`, `AutonomousSweepResult` (reusing Feature 002 `SampleRollup`, `VarianceSummary` from `runners/types.py`) per data-model.md and contracts/autonomous-runner.md (FR-016–FR-018)
- [X] T017 Implement `resolve_autonomous_entry` in `runners/autonomous/cache.py`: T1-canonicalized `prompt_hash`, `CacheKey` with `runner_id=autonomous`, offline replay parsing `raw_response.verdicts` and `tool_calls`, refresh via `seam.adjudicate(..., tool_registry=registry)` persisting both fields, `CacheMissError` with identifying path (FR-011–FR-015)
- [X] T018 Expand minimal committed cache under `cache/primary/autonomous/` so config, label-isolation, and trace round-trip acceptance tests can replay at least one subject × five samples offline (FR-011, FR-019)

**Checkpoint (Foundational — config/context-isolation/trace schema green, tools/sweep still red)**:

```bash
uv run pytest tests/autonomous/test_acceptance_autonomous_config.py -v
uv run pytest tests/autonomous/test_acceptance_label_isolation.py -v -m context_isolation
uv run pytest tests/autonomous/test_acceptance_tool_call_traces.py -v -k "not tier_isolation and not gate_isolation"
```

**Expected**: Config and context-scoped label-isolation tests pass. `tool_isolation` label tests, retrieval-tools, full-sweep, sample-variance, and complete offline cache tests may still fail pending tools and runner orchestration.

---

## Phase 3: User Story 1 — Filesystem-Backed Retrieval Tools (Priority: P1)

**Goal**: Three filesystem-backed retrieval tools expose T2 location records and T3 retention floors / governance map from the committed export without `expected` labels (FR-001–FR-003).

**Independent Test**: Invoke each retrieval tool against the committed export for a known subject; verify T2/T3 field-for-field parity, no `expected` in responses, empty locations return `[]`, unknown subject returns documented error (US1 independent test, SC-005).

**Depends on**: Phase 2 complete (types and registry protocol surface).

### Tests (already written — T007)

> Confirm `test_acceptance_retrieval_tools.py` fails until T019–T022 complete.

### Implementation for User Story 1

- [X] T019 [P] [US1] Implement `get_location_records` in `core/tools/location_records.py`: read subject locations from `ExportBundle`, return T2-equivalent business fields only, empty list for empty locations, `subject_not_found` error for unknown IDs per contracts/retrieval-tools.md (FR-001, FR-002, FR-003)
- [X] T020 [P] [US1] Implement `get_retention_floors` in `core/tools/retention_floors.py`: return all five sectoral floors from export rules corpus matching T3 builder output (FR-001, FR-002)
- [X] T021 [P] [US1] Implement `get_governance_map` in `core/tools/governance_map.py`: return full governance map from export rules corpus matching T3 builder output (FR-001, FR-002)
- [X] T022 [US1] Implement `build_retrieval_tool_registry` and `ToolRegistry` dispatch in `core/tools/registry.py`; export from `core/tools/__init__.py` (FR-001, FR-003)

**Checkpoint (US1 — retrieval tools and full label isolation green)**:

```bash
uv run pytest tests/autonomous/test_acceptance_retrieval_tools.py -v
uv run pytest tests/autonomous/test_acceptance_label_isolation.py -v
```

**Expected**: All retrieval-tool parity, tool-scoped isolation, and context-scoped isolation tests pass. Autonomous runner sweep tests may still fail.

---

## Phase 4: User Story 2 — Full Autonomous Adjudication Sweep Offline (Priority: P1) 🎯 MVP

**Goal**: Autonomous runner sweeps every labeled export subject with request-only T1 context, tool-use enabled, verdicts paired against `expected` only, aggregate scoring via `core.scoring.score_adjudication`, and offline cache replay (FR-004–FR-009, FR-011, FR-013).

**Independent Test**: Run autonomous sweep offline against committed cache; every export subject visited; each location graded against `expected` only; output includes per-lane confusion matrix and standalone rates with no blended accuracy; no live model credentials (US2 independent test, SC-002, SC-004, SC-010).

**Depends on**: Phase 3 complete (retrieval tools + registry for refresh path and `FakeModelSeam` integration).

### Tests (already written — T009, T011)

> Confirm full-sweep acceptance tests fail until T023–T025 complete.

### Implementation for User Story 2

- [X] T023 [US2] Implement `run_autonomous_sweep` in `runners/autonomous/runner.py`: export load + provenance verify, env-driven config via `core.model.load_model_config()`, build tool registry, outer sample loop 0–4, subject iteration with `build_t1` only, pairing location IDs per tier-spine T1 rule, `pair_subject_verdicts` from `expected` only, `core.scoring.score_adjudication` per sample, `runners.variance.compute_variance_summary`; re-export from `runners/autonomous/__init__.py` (FR-004–FR-009, FR-013–FR-014, FR-017)
- [X] T024 [US2] Seed committed cache entries for all location-bearing export subjects × `autonomous` × `sample_index` 0–4 under `cache/primary/autonomous/` (2 subjects × 5 samples = 10 entries; skip `empty-locations-subject` per Feature 002 seeding; additive only; do not edit `export/`) (FR-011, FR-019, SC-003, SC-010)
- [X] T025 [US2] Validate full autonomous offline sweep: 100% subject coverage, deterministic replay on re-run, hand-check one sample's standalone rates against raw prediction–ground-truth pairs, invalid verdict raises validation error naming `subject_id`, `location_id`, and `sample_index` (FR-008, SC-002, SC-004, SC-009)

**Checkpoint (MVP — full autonomous sweep green)**:

```bash
uv run pytest tests/autonomous/test_acceptance_autonomous_runner.py tests/autonomous/test_acceptance_autonomous_cache_offline.py -v
```

**Expected**: Autonomous runner and offline cache acceptance tests pass with no API key. Sample-variance and tier/gate trace-isolation tests may still fail until Phases 5–6.

---

## Phase 5: User Story 3 — Tool-Call Trace Logging in Committed Cache (Priority: P1)

**Goal**: Committed autonomous cache entries record ordered tool-call traces in `tool_calls`; offline replay uses stored traces without re-execution; tier and gate cache entries remain trace-free (FR-015, US3).

**Independent Test**: Load a committed autonomous cache entry in offline mode; verify `tool_calls` present with auditable summaries when tools were invoked; tier-runner entries for the same subject lack non-empty `tool_calls` (US3 independent test, SC-006).

**Depends on**: Phase 4 complete (full cache with trace payloads).

### Tests (already written — T008)

> Trace persistence logic lives in cache helper (T017) and refresh path; this phase validates end-to-end trace contract against full committed cache.

### Validation for User Story 3

- [ ] T026 [US3] Verify committed autonomous cache entries include ordered `tool_calls` with required result-summary fields per contracts/tool-call-trace.md for entries where tool use occurred; empty `[]` valid when no tools invoked (FR-015, US3 scenarios 1 and 4, SC-006)
- [ ] T027 [US3] Verify tier-runner cache entries under `cache/primary/t1/`, `t2/`, `t3/` and gate entries under `cache/primary/adversarial_gate/` normalize to empty `tool_calls` — autonomous-only trace namespace (FR-015, US3 scenario 3)
- [ ] T028 [US3] Verify offline replay path in `runners/autonomous/cache.py` reads stored `tool_calls` and `raw_response.verdicts` without re-executing tools or live model calls (FR-015, US3 scenario 2)

**Checkpoint (US3 — tool-call traces green)**:

```bash
uv run pytest tests/autonomous/test_acceptance_tool_call_traces.py -v
```

**Expected**: All tool-call trace acceptance tests pass including tier/gate namespace isolation.

---

## Phase 6: User Story 4 — Sample N=5 and Report Cross-Sample Variance (Priority: P2)

**Goal**: Autonomous runner produces five per-sample aggregate scoring results and a variance summary comparing standalone safety rates across samples; offline cache miss fails explicitly (FR-016–FR-018, US4).

**Independent Test**: With committed cache for all five sample indices across the export, run autonomous sweep offline; verify five rollups, variance summary with per-index rates and constancy flags; cache miss raises explicit error (US4 independent test, SC-003, SC-004).

**Depends on**: Phase 4 complete (full 10-entry cache coverage for offline replay).

### Tests (already written — T010)

> Sample loop logic lives in runner (T023); this phase validates end-to-end N=5 behavior and variance reporting across full export.

### Validation for User Story 4

- [ ] T029 [US4] Verify outer sample loop emits exactly five `SampleRollup` entries with `sample_index` 0–4 and distinct cache keys per `(runner_id, subject_id, sample_index)` using T1 prompt hash (FR-016, SC-003)
- [ ] T030 [US4] Confirm SC-004 hand-calculated over-erasure, over-retention, and mis-escalation rate parity assertions from T010 pass against full committed cache after Phase 4 (FR-009, SC-004)
- [ ] T031 [US4] Verify offline cache-miss test (`cache_miss` marker) fails with message identifying `subject_id`, `sample_index`, and `runner_id` — no silent live model call (FR-011, US4 scenario 4)
- [ ] T032 [US4] Verify `VarianceSummary.constant_across_samples` is correct when sample rates differ vs. identical across all five samples (FR-018, US4 scenario 3)

**Checkpoint (US4 — variance and cache-miss green)**:

```bash
uv run pytest tests/autonomous/test_acceptance_autonomous_sample_variance.py -v
uv run pytest tests/autonomous -k cache_miss -v
```

**Expected**: Five per-sample results and variance summary pass; cache-miss behavior explicit.

---

## Phase 7: User Story 6 — Validate Autonomous Evaluation via Quickstart Guide (Priority: P3)

**Goal**: Human-readable path reproduces green offline autonomous sweep mirroring CI (FR-021, SC-008).

**Independent Test**: Follow `specs/004-autonomous-retrieval-eval/quickstart.md` on a clean clone without API key; autonomous sweep replays from committed cache and acceptance suite is green (US6 independent test).

**Depends on**: Phases 4–6 complete (full sweep, traces, variance).

### Validation for User Story 6

- [ ] T033 [US6] Execute quickstart setup and full acceptance suite steps from `specs/004-autonomous-retrieval-eval/quickstart.md` on a clean clone without API key (FR-021, SC-008)
- [ ] T034 [P] [US6] Run quickstart spot-check commands: retrieval tools parity, autonomous offline sweep, label isolation, tool-call traces, cache miss, N=5 variance, and lint per quickstart.md sections
- [ ] T035 [US6] Confirm quickstart lint commands pass: `uv run ruff check .` and `uv run ruff format --check .`

**Checkpoint (US6 — quickstart path green)**:

```bash
uv run pytest tests/autonomous -v
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Matches CI merge-gate expectations for this feature; no API key; under 10 minutes on a standard dev machine (SC-008).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite gate, vocabulary discipline, deterministic replay confirmation, frozen-interface audit.

**Depends on**: Phase 7 complete.

- [ ] T036 Run full offline autonomous acceptance suite and confirm SC-001: all tests green with `CACHE_MODE=offline` and no `MODEL_API_KEY` (SC-001)
- [ ] T037 [P] Audit autonomous runner, retrieval tools, and test modules for vocabulary: *autonomous retrieval evaluation* in reader-facing copy, `autonomous` in developer identifiers, DPDP domain terms; no retired scaffolding terms (FR-023)
- [ ] T038 Confirm no blended accuracy field in `AutonomousSweepResult`, `SampleRollup`, or runner output across all autonomous results (FR-009, SC-007)
- [ ] T039 Confirm re-running autonomous sweep twice in offline mode yields identical per-sample scoring results (SC-009); confirm no edits to committed `export/`, tier runners, or adversarial-gate modules (FR-024, SC-007)

**Final Checkpoint**:

```bash
uv run pytest tests/core tests/runners tests/gate tests/autonomous -v
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Full feature definition of done — SC-001 through SC-010 satisfied offline.

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Bootstrap (US5 failing tests)
    ↓
Phase 2 Foundational (seam extension + cache helper — BLOCKS tools and sweep)
    ↓
Phase 3 US1 Retrieval Tools
    ↓
Phase 4 US2 Full Autonomous Sweep + full cache (MVP)
    ↓
Phase 5 US3 Tool-Call Trace validation
    ↓
Phase 6 US4 N=5 variance validation
    ↓
Phase 7 US6 quickstart validation
    ↓
Phase 8 Polish
```

### User Story Dependencies

| Story | Priority | Depends On | Delivers |
|-------|----------|------------|----------|
| US5 | P2 | Phase 1 only | Failing acceptance suite before implementation (T005–T011) |
| US1 | P1 | Phase 2 types/registry surface | Filesystem retrieval tools (T019–T022) |
| US2 | P1 | Phase 3 tools green | Full offline autonomous sweep (T023–T025) |
| US3 | P1 | Phase 4 full cache | Tool-call trace contract validated (T026–T028) |
| US4 | P2 | Phase 4 full cache | N=5 variance + cache-miss discipline (T029–T032) |
| US6 | P3 | Phases 4–6 | Quickstart reproducibility (T033–T035) |

### Critical Sequencing Rules

1. **Test-first (Principle II)**: T005–T011 (all acceptance tests) MUST complete before T013–T017 (foundational implementation).
2. **SC-004/SC-005 at bootstrap**: Hand-calculated rate parity and T2/T3 field-for-field parity assertions MUST be written in T007 and T010 (Phase 1), not added after implementation.
3. **Registry stub before seam**: T002 `ToolRegistry` Protocol stub MUST land before T014 extends `ModelSeam.adjudicate`.
4. **Seam before tools**: T013–T015 MUST complete before T022 wires registry into `FakeModelSeam` and refresh path.
5. **Tools before sweep**: T019–T022 MUST complete before T023 orchestrates tool-use adjudication.
6. **Runner before full cache**: T023 MUST complete before T024 full cache seeding.
7. **Full cache before variance validation**: T024 before T029–T032.
8. **Label isolation split**: Phase 2 checkpoint runs only `context_isolation` marker tests; full label-isolation suite (including `tool_isolation`) MUST pass at Phase 3 checkpoint.
9. **No out-of-scope work**: No CLI entrypoints, `report/` modules, tier-runner rework (`runners/spine.py`, `runners/t1.py`–`t3.py`), adversarial-gate edits, or committed export content changes.

### FR/SC Traceability Matrix

| Requirement | Tasks |
|-------------|-------|
| FR-001 (retrieval tools under `core/tools/`) | T002, T007, T019–T022 |
| FR-002 (T2/T3 parity, no `expected`) | T006, T007, T019–T021 |
| FR-003 (export loader only) | T007, T019–T022 |
| FR-004 (autonomous runner) | T001, T009, T023, T025 |
| FR-005 (request-only context + tool-use) | T009, T023 |
| FR-006 (no pre-loaded records/rules) | T006, T009, T023 |
| FR-007 (ModelSeam.adjudicate with tools) | T014, T015, T017, T023 |
| FR-008 (ground truth from `expected` only) | T009, T023, T025 |
| FR-009 (shared adjudication scoring) | T009, T023, T030, T038 |
| FR-010 (env MODEL_ID, CACHE_MODE) | T005, T023 |
| FR-011 (offline default, CI no key) | T004, T011, T017, T023, T024, T031, T036 |
| FR-012 (refresh path available) | T011, T017 |
| FR-013 (runner_id autonomous) | T009, T011, T017, T024 |
| FR-014 (T1 prompt hash identity) | T006, T011, T017, T029 |
| FR-015 (tool_calls traces) | T008, T013, T017, T026–T028 |
| FR-016 (N=5 samples) | T010, T023, T029 |
| FR-017 (per-sample aggregate scoring) | T010, T016, T023 |
| FR-018 (variance summary) | T010, T016, T032 |
| FR-019 (committed cache full coverage) | T004, T011, T018, T024 |
| FR-020 (acceptance suite before impl) | T003, T005–T011 |
| FR-021 (quickstart guide) | T033–T035 |
| FR-022 (feature branch only) | All tasks on `004-autonomous-retrieval-eval` |
| FR-023 (vocabulary discipline) | T037 |
| FR-024 (no tier/gate/export edits) | T039 |
| SC-001 (offline CI green) | T012, T036 |
| SC-002 (100% subject coverage) | T009, T025 |
| SC-003 (five per-sample results) | T010, T024, T029 |
| SC-004 (hand-calculated rate parity) | T010, T025, T030 |
| SC-005 (tool vs builder parity) | T007, T019–T022 |
| SC-006 (autonomous traces; tier entries clean) | T008, T026, T027 |
| SC-007 (additive only; no blended accuracy) | T024, T038, T039 |
| SC-008 (quickstart under 10 min) | T033 |
| SC-009 (deterministic replay) | T009, T023, T025, T039 |
| SC-010 (full export offline replay) | T011, T024, T025 |

---

## Parallel Execution Examples

### Phase 1 Bootstrap (after T001–T002)

```bash
# Parallel: conftest + all acceptance test files + minimal cache seed
T003 tests/autonomous/conftest.py
T004 cache/primary/autonomous/ minimal seed
T005 test_acceptance_autonomous_config.py
T006 test_acceptance_label_isolation.py
T007 test_acceptance_retrieval_tools.py
T008 test_acceptance_tool_call_traces.py
T009 test_acceptance_autonomous_runner.py
T010 test_acceptance_autonomous_sample_variance.py
T011 test_acceptance_autonomous_cache_offline.py
```

### Phase 2 Foundational (after tests red)

```bash
# Parallel: core types + fake seam + runner types (ToolRegistry stub from T002 already in place)
T013 core/types.py
T015 core/model/fake.py
T016 runners/autonomous/types.py
# Then sequential: T014 core/model/seam.py (depends on T013 + T002 registry stub)
# Then sequential: T017 runners/autonomous/cache.py (depends on T014–T015)
```

### Phase 3 US1 (after foundational green)

```bash
# Parallel: three tool modules
T019 core/tools/location_records.py
T020 core/tools/retention_floors.py
T021 core/tools/governance_map.py
# Then sequential: T022 core/tools/registry.py (depends on T019–T021)
```

---

## Implementation Strategy

### MVP First (US1 Tools + US2 Full Offline Sweep)

1. Complete Phase 1: Bootstrap — all failing tests + conftest + minimal cache
2. Complete Phase 2: Foundational — seam extension + cache helper + runner types green
3. Complete Phase 3: US1 — retrieval tools parity tests green
4. Complete Phase 4: US2 — full 10-entry cache + autonomous sweep tests green
5. **STOP and VALIDATE**: `uv run pytest tests/autonomous/test_acceptance_autonomous_runner.py tests/autonomous/test_acceptance_autonomous_cache_offline.py -v`
6. Continue with US3 trace validation, US4 variance, US6 quickstart, and polish

### Incremental Delivery

1. Bootstrap + Foundational → autonomous infrastructure proven with minimal cache
2. US1 → filesystem retrieval tools with T2/T3 parity
3. US2 → full offline autonomous sweep (**MVP checkpoint**)
4. US3 → tool-call trace contract validated against committed cache
5. US4 → N=5 variance and cache-miss hardening
6. US6 + Polish → quickstart on-ramp and full-suite gate

### Parallel Team Strategy

With multiple developers after Phase 2:

- Developer A: Phase 3 US1 (retrieval tool modules + registry)
- Developer B: Phase 2 completion (cache helper + seam extension) then begin cache seeding script for autonomous namespace
- Developer C: Expand acceptance fixtures in `tests/autonomous/conftest.py` and parity helpers

After Phase 3, Developer A implements runner orchestration (T023) while Developer B seeds full autonomous cache (T024).

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same batch
- US5 acceptance-suite-before-implementation is satisfied by Phase 1 tasks T005–T011 preceding all implementation (T013–T023)
- Extend `core/` minimally for seam/types only; do not modify tier runners or adversarial gate (FR-024)
- Do not edit committed `export/` content (Principle III); cache entries are additive only
- Refresh path (`CACHE_MODE=refresh`) remains available via autonomous cache helper but is not CI-gated (FR-012)
- No `report/` layer for this feature — variance summary reuses Feature 002 `runners/variance.py`
- Total tasks: **39** (Bootstrap 12, Foundational 6, US1 4, US2 3, US3 3, US4 4, US6 3, Polish 4)

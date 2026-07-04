# Tasks: Adversarial Gate Evaluation

**Input**: Design documents from `/specs/003-adversarial-gate/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, quickstart.md, research.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Every phase lists failing acceptance tests before implementation tasks.

**Organization**: Bootstrap → Foundational (gate runner spine + slice loading) → User stories by spec priority → Report/CI tables → Polish

**Branch**: `003-adversarial-gate`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US6) for story-phase tasks only
- FR/SC references trace tasks to spec requirements

## Path Conventions

- Gate runner: `runners/adversarial_gate/` at repository root
- Acceptance tests: `tests/gate/` mirroring gate runner modules
- Extended slice fixture: `fixtures/adversarial_slice/cases.yaml` (additive; export seeds unchanged)
- Reporting: `report/` at repository root (Wilson CIs + per-family tables)
- Committed cache: `cache/primary/adversarial_gate/` (additive entries only)
- Core (Feature 001, consumed not modified): `core/`
- Tier runners (Feature 002, reference only — do not modify): `runners/spine.py`, `runners/t1.py`, etc.

---

## Phase 1: Bootstrap (Gate Layout & Failing Acceptance Suite)

**Purpose**: Scaffold gate runner package and test harness; write the full acceptance suite so it fails for missing gate behavior (not setup errors) before any orchestration code lands.

**Goal (US5)**: Acceptance suite defines done before implementation (FR-018, SC-001).

**Independent Test**: `uv run pytest tests/gate -v` on a clean clone — all gate tests fail with import or `NotImplementedError`/assertion failures attributable to missing gate modules, not missing export/core fixtures.

### Bootstrap Tasks

- [ ] T001 Create `runners/adversarial_gate/` package skeleton with empty `runners/adversarial_gate/__init__.py` per plan.md project structure (FR-001)
- [ ] T002 [P] Create `tests/gate/conftest.py` with shared fixtures: repo root, `export/` path, `cache/` root, `fixtures/adversarial_slice/` path, `FakeModelSeam`, `CACHE_MODE=offline` default, helper to build minimal `GateSweepConfig`, and hand-calculated Wilson/rate parity fixture builders for report tests (FR-018, SC-001)
- [ ] T003 [P] Add minimal committed cache seed under `cache/primary/adversarial_gate/` for at least one slice case covering `sample_index` 0–4 to unblock early offline assertions (FR-006, FR-017, SC-010)
- [ ] T004 [P] [US5] Write failing `tests/gate/test_acceptance_gate_config.py` asserting `MODEL_ID` and `CACHE_MODE` are read from environment at gate runner init, not hardcoded literals (FR-005, US5 scenario 4)
- [ ] T005 [P] [US5] Write failing `tests/gate/test_acceptance_label_isolation.py` asserting ground-truth `label` and `family` never appear in `classify_note` kwargs or cache-canonicalized payloads; only `text` drives prompt hash (FR-002, FR-009, US5 scenario 3)
- [ ] T006 [P] [US5] Write failing `tests/gate/test_acceptance_adversarial_slice.py` for extended slice: three frozen seeds byte-identical to export, 80–100 total cases, attack/benign balance, five attack families at ~8–10 each (taxonomy IDs `direct_override`, `authority_spoof`, `obfuscated_injection`, `scope_expansion`, `exfiltration`), hard-negative benign controls, unique `case_id` values; abort with `ProvenanceError` when export provenance fails during seed cross-check (FR-013, FR-014, US2 scenarios 1–6, SC-007)
- [ ] T007 [P] [US1] Write failing `tests/gate/test_acceptance_gate_runner.py` for full gate sweep: every slice case visited, `runner_id=adversarial_gate`, `classify_note` receives note `text` only, detection/false-alarm rates via shared scoring primitives, no blended accuracy, offline determinism (FR-001–FR-004, FR-008, US1 scenarios 1–5, SC-002, SC-004, SC-009)
- [ ] T008 [P] [US4] Write failing `tests/gate/test_acceptance_gate_sample_variance.py` for five per-sample rollups, variance summary with `constant_across_samples` flags, distinct cache keys per `(runner_id, case_id, sample_index)`, explicit offline cache-miss failure (`cache_miss` marker), and hand-calculated detection/false-alarm rate parity for at least one sample from raw outcome–label pairs (FR-010–FR-012, US4 scenarios 1–4, SC-003, SC-004)
- [ ] T009 [P] [US3] Write failing `tests/gate/test_acceptance_gate_report.py` with hand-crafted scoring fixtures asserting Wilson interval bounds and per-family detection rows match independently calculated values within documented tolerance; zero-denominator families omitted from per-family table; overall detection or false-alarm rate with zero attack or zero benign pairs yields `Rate.value: null` and `RateWithCI.interval: null` (FR-015, FR-016, US3 scenarios 1–5, SC-005, SC-006)
- [ ] T010 [P] [US1] Write failing `tests/gate/test_acceptance_gate_cache_offline.py` for offline replay via `runner_id=adversarial_gate`, cache prompt identity from `{"text": note}` only, refresh path opt-in via `@pytest.mark.refresh`, and cache-miss error naming `case_id`, `sample_index`, `runner_id` (FR-006–FR-009, FR-017, US1 scenario 4, US4 scenario 4, SC-010)
- [ ] T011 Verify Feature 001 and Feature 002 prerequisites: `uv run pytest tests/core tests/runners -v` passes on branch `003-adversarial-gate`

**Checkpoint (Bootstrap — tests must fail for the right reason)**:

```bash
uv run pytest tests/gate -v --tb=short
```

**Expected**: All `tests/gate/` tests fail due to missing gate modules/behavior; `tests/core/` and `tests/runners/` green. No network or API key required.

---

## Phase 2: Foundational — Gate Runner Spine & Slice Loading

**Purpose**: Implement gate runner types, extended slice fixture, slice loader, cache helper, variance summary, and orchestration spine so slice, config, isolation, and spine acceptance tests pass before full cache expansion and reporting.

**Goal**: Shared gate sweep flow with slice loading and N=5 sample loop (FR-001, FR-010, FR-014).

**Independent Test**: Slice loader and gate spine acceptance tests pass with minimal cache seed; full-sweep, report, and complete offline cache tests still fail until Phases 3–5.

**Depends on**: Phase 1 complete (failing acceptance suite + conftest + minimal cache seed).

### Tests (already written in Phase 1 — confirm still failing until implementation)

> Tests T004–T010 MUST remain red until T012–T018 land. Do not implement `report/` modules in this phase.

### Implementation for Gate Spine & Slice Loading

- [ ] T012 [P] Implement gate runner Pydantic types in `runners/adversarial_gate/types.py`: `GateSweepConfig`, `PerCaseGateResult`, `GateSampleRollup`, `GateRateAtSample`, `GateRateVariance`, `GateVarianceSummary`, `GateSweepResult` per data-model.md and contracts/gate-runner.md (FR-010–FR-012)
- [ ] T013 [P] Author extended adversarial slice fixture `fixtures/adversarial_slice/cases.yaml` with ~80–100 labeled cases: three frozen export seeds byte-identical, ~40–50 attack and ~40–50 benign, five attack families at ~8–10 each, hard-negative benign controls; additive only — do not edit `export/adversarial_seeds/seeds.yaml` (FR-013, FR-014, US2, SC-007)
- [ ] T014 Implement `load_extended_slice` in `runners/adversarial_gate/slice_loader.py`: parse `AdversarialSeedCase` list, validate coverage rules, optional export seed cross-check via `core.export.load_export()` with `verify_provenance()` then byte-identical seed comparison, stable file order, typed errors (`ProvenanceError`, seed mismatch) on validation failure per contracts/adversarial-slice.md (FR-013, FR-014, US2)
- [ ] T015 [P] Implement gate cache key helper and classify resolution in `runners/adversarial_gate/cache.py`: `prompt_hash({"text": case.text})`, `CacheKey` with `runner_id=adversarial_gate`, offline replay, refresh via `seam.classify_note(text=..., case_id=...)`, `CacheMissError` with identifying path (FR-007–FR-009)
- [ ] T016 [P] Implement cross-sample rate comparison in `runners/adversarial_gate/variance.py` producing `GateVarianceSummary` with `constant_across_samples` per contracts/gate-report.md (FR-011, FR-012)
- [ ] T017 Implement `run_adversarial_gate_sweep` in `runners/adversarial_gate/runner.py`: load slice, env-driven config via `core.model.load_model_config()`, outer sample loop 0–4, case loop with label from fixture metadata only, outcome validation ∈ {clean, adversarial}, `core.scoring.score_adversarial` per sample, variance rollup; re-export from `runners/adversarial_gate/__init__.py` (FR-001–FR-005, FR-010, FR-011, FR-014)
- [ ] T018 Expand minimal committed cache under `cache/primary/adversarial_gate/` so slice-loader, config, isolation, and spine acceptance tests can replay at least one case × five samples offline (FR-006, FR-017)

**Checkpoint (Foundational — slice + spine green, full sweep/report still red)**:

```bash
uv run pytest tests/gate/test_acceptance_adversarial_slice.py tests/gate/test_acceptance_gate_config.py tests/gate/test_acceptance_label_isolation.py -v
uv run pytest tests/gate/test_acceptance_gate_runner.py -v -k "not full_sweep and not deterministic_replay"
```

**Expected**: Slice loader, config, and label-isolation tests pass. Full-sweep, report, sample-variance full-slice, and complete offline cache tests may still fail pending full cache and report modules.

---

## Phase 3: User Story 2 — Extended Adversarial Slice Fixture (Priority: P1)

**Goal**: Committed extended slice meets coverage targets and passes slice acceptance contract independently of full cache (FR-013, FR-014).

**Independent Test**: Load extended slice fixture; verify three frozen seeds unchanged, 80–100 cases, five families represented, attack/benign balance, hard-negative benign controls (US2 independent test, SC-007).

**Depends on**: Phase 2 complete (slice loader + fixture committed).

### Tests (already written — T006)

> Confirm `test_acceptance_adversarial_slice.py` passes after T013–T014; add no new slice tests unless coverage gaps found.

### Validation for User Story 2

- [ ] T019 [US2] Audit `fixtures/adversarial_slice/cases.yaml` against contracts/adversarial-slice.md: confirm all five attack families present at ~8–10 each, benign hard negatives included, no duplicate `case_id`, no edits to export seed content (FR-014, US2 scenarios 2–4)
- [ ] T020 [US2] Verify slice loader seed cross-check: (a) aborts with `ProvenanceError` when export manifest/SHA verification fails; (b) aborts with explicit seed mismatch error when provenance passes but a frozen seed field diverges from `export/adversarial_seeds/seeds.yaml` (US2 scenarios 1 and 6, spec edge case: provenance vs seed mismatch)

**Checkpoint (US2 — slice fixture green)**:

```bash
uv run pytest tests/gate/test_acceptance_adversarial_slice.py -v
```

**Expected**: All slice acceptance tests pass. Gate full-sweep and report tests may still fail.

---

## Phase 4: User Story 1 — Full Adversarial Gate Sweep Offline (Priority: P1) 🎯 MVP

**Goal**: Gate runner sweeps every case in the extended slice via `classify_note` with note text only, scores with shared adversarial primitives, and replays committed cache offline (FR-001–FR-004, FR-006, FR-008).

**Independent Test**: Run gate sweep offline against committed cache; every slice case visited; detection and false-alarm rates match hand-calculated proportions; no live model credentials (US1 independent test, SC-002, SC-004, SC-010).

**Depends on**: Phase 3 complete (validated slice fixture).

### Tests (already written — T007, T010)

> Confirm full-sweep acceptance tests fail until T021–T022 complete.

### Implementation for User Story 1

- [ ] T021 [US1] Seed committed cache entries for **all** extended slice cases × `adversarial_gate` × `sample_index` 0–4 under `cache/primary/adversarial_gate/` (additive only; do not edit `export/` or accepted slice case content) (FR-006, FR-008, FR-017, SC-003, SC-010)
- [ ] T022 [US1] Validate full gate offline sweep: 100% slice case coverage, deterministic replay on re-run, hand-check one sample's detection and false-alarm rates against raw outcome–label pairs, invalid outcome raises validation error naming `case_id` and `sample_index` (FR-004, SC-002, SC-004, SC-009)

**Checkpoint (US1 — gate sweep green)**:

```bash
uv run pytest tests/gate/test_acceptance_gate_runner.py tests/gate/test_acceptance_gate_cache_offline.py -v
```

**Expected**: Gate runner and offline cache acceptance tests pass with no API key. Report and full variance tests may still fail.

---

## Phase 5: User Story 4 — N=5 Sampling & Cross-Sample Variance (Priority: P2)

**Goal**: Gate runner produces five per-sample aggregate scoring results and a variance summary comparing detection and false-alarm rates across samples; offline cache miss fails explicitly (FR-010–FR-012, US4).

**Independent Test**: With committed cache for all five sample indices across the slice, run gate sweep offline; verify five rollups, variance summary with per-index rates and constancy flags; cache miss raises explicit error (US4 independent test, SC-003, SC-004).

**Depends on**: Phase 4 complete (full slice cache coverage for offline replay).

### Tests (already written — T008)

> Sample loop logic lives in runner (T017); this phase validates end-to-end N=5 behavior across full slice with complete cache.

### Validation for User Story 4

- [ ] T023 [US4] Verify outer sample loop emits exactly five `GateSampleRollup` entries with `sample_index` 0–4 and distinct cache keys per `(runner_id, case_id, sample_index)` (FR-010, SC-003)
- [ ] T024 [US4] Confirm SC-004 hand-calculated detection/false-alarm rate parity assertions from T008 pass against full committed cache after Phase 4 (FR-004, SC-004)
- [ ] T025 [US4] Verify offline cache-miss test (`cache_miss` marker) fails with message identifying `case_id`, `sample_index`, and `runner_id` — no silent live model call (FR-006, US4 scenario 4)
- [ ] T026 [US4] Verify `GateVarianceSummary.constant_across_samples` is correct when sample rates differ vs. identical across all five samples (FR-012, US4 scenario 3)

**Checkpoint (US4 — variance and cache-miss green)**:

```bash
uv run pytest tests/gate/test_acceptance_gate_sample_variance.py -v
uv run pytest tests/gate -k cache_miss -v
```

**Expected**: Five per-sample results and variance summary pass; cache-miss behavior explicit.

---

## Phase 6: User Story 3 — Wilson Confidence Intervals & Per-Family Reporting Tables (Priority: P1)

**Goal**: Reporting layer computes Wilson confidence intervals on detection and false-alarm rates and emits per-attack-family detection breakdown tables consuming core scoring numerators/denominators only (FR-015, FR-016).

**Independent Test**: Feed hand-crafted scoring results into report layer; verify Wilson bounds and per-family detection rows match independently calculated values (US3 independent test, SC-005, SC-006).

**Depends on**: Phase 4 complete (scored gate sweep output available for integration); report tests written in Phase 1 (T009).

### Tests (already written — T009)

> Confirm `test_acceptance_gate_report.py` fails until T027–T029 complete.

### Implementation for User Story 3

- [ ] T027 [P] [US3] Create `report/` package with reporting types in `report/types.py`: `WilsonInterval`, `RateWithCI`, `FamilyDetectionRow`, `GateReportTables` per data-model.md — do not add Wilson types to `core/types.py` (FR-016)
- [ ] T028 [P] [US3] Implement Wilson score interval in `report/wilson.py` using stdlib `math` only at default 95% confidence; return null bounds when denominator is zero (FR-015, FR-016, US3 scenario 3)
- [ ] T029 [US3] Implement `build_gate_report` in `report/adversarial_tables.py`: wrap core `Rate` with Wilson CIs for overall detection and false-alarm; emit per-family detection rows from `scoring.per_family`, omitting zero-denominator families; do not re-derive rate numerators/denominators (FR-015, US3 scenarios 1–2, SC-005, SC-006)

**Checkpoint (US3 — report/CI tables green)**:

```bash
uv run pytest tests/gate/test_acceptance_gate_report.py -v
```

**Expected**: Wilson interval and per-family table acceptance tests pass on hand-crafted fixtures.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite gate, quickstart on-ramp, vocabulary discipline, deterministic replay confirmation.

**Goal (US6)**: Human-readable path reproduces green offline gate sweep mirroring CI (FR-019, SC-008).

**Depends on**: Phases 4–6 complete.

### Validation & Polish Tasks

- [ ] T030 [US6] Execute quickstart setup and full acceptance suite steps from `specs/003-adversarial-gate/quickstart.md` on a clean clone without API key (FR-019, SC-008)
- [ ] T031 [P] [US6] Run quickstart spot-check commands: slice loader, gate offline sweep, label isolation, Wilson/per-family report, cache miss, N=5 variance, and lint per quickstart.md sections
- [ ] T032 Run full offline gate acceptance suite and confirm SC-001: all tests green with `CACHE_MODE=offline` and no `MODEL_API_KEY` (SC-001)
- [ ] T033 [P] Audit gate runner, report, and test modules for vocabulary: *adversarial-gate evaluation* in reader-facing copy, `adversarial_gate` in developer identifiers, DPDP domain terms; no retired scaffolding terms (FR-021)
- [ ] T034 Confirm no blended accuracy field in `GateSweepResult`, `GateSampleRollup`, or `GateReportTables` across all gate outputs (FR-004, SC-007)
- [ ] T035 Confirm re-running gate sweep twice in offline mode yields identical per-sample scoring results and report tables (SC-009)

**Final Checkpoint**:

```bash
uv run pytest tests/core tests/runners tests/gate -v
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
Phase 2 Foundational (spine + slice loading — BLOCKS all story work)
    ↓
Phase 3 US2 Extended Slice validation
    ↓
Phase 4 US1 Full Gate Sweep + full cache (MVP)
    ↓
Phase 5 US4 N=5 variance validation
    ↓
Phase 6 US3 Report/CI tables (Wilson + per-family)
    ↓
Phase 7 Polish + US6 quickstart
```

### User Story Dependencies

| Story | Priority | Depends On | Delivers |
|-------|----------|------------|----------|
| US5 | P2 | Phase 1 only | Failing acceptance suite before implementation (T004–T010) |
| US2 | P1 | Phase 2 slice loader | Validated extended slice fixture (T013–T014, T019–T020) |
| US1 | P1 | Phase 3 slice green | Full offline gate sweep (T021–T022) |
| US4 | P2 | Phase 4 full cache | N=5 variance + cache-miss discipline (T023–T026) |
| US3 | P1 | Phase 4 scored output | Wilson CIs + per-family tables (T027–T029) |
| US6 | P3 | Phases 4–6 | Quickstart reproducibility (T030–T031) |

### Critical Sequencing Rules

1. **Test-first (Principle II)**: T004–T010 (all acceptance tests) MUST complete before T012–T017 (gate spine implementation).
2. **SC-004/SC-005/SC-006 at bootstrap**: Hand-calculated rate and Wilson parity assertions MUST be written in T008 and T009 (Phase 1), not added after implementation.
3. **Slice before runner**: T013–T014 MUST complete before T017 wires the sweep loop against the full corpus.
4. **Spine before full cache**: T017 MUST complete before T021 full cache seeding.
5. **Full cache before variance validation**: T021 before T023–T026.
6. **Report consumes scoring only**: T029 MUST NOT re-implement adversarial rate math from `core/scoring`.
7. **No out-of-scope work**: No CLI entrypoints, `core/tools` changes, tier-runner rework (`runners/spine.py`, `runners/t1.py`–`t3.py`), autonomous runner (Feature 004), or Wilson logic in `core/scoring`.

### FR/SC Traceability Matrix

| Requirement | Tasks |
|-------------|-------|
| FR-001 (adversarial-gate runner) | T001, T007, T017, T022 |
| FR-002 (`classify_note` text only) | T005, T007, T015, T017 |
| FR-003 (labels from fixture metadata) | T005, T006, T014, T017 |
| FR-004 (shared adversarial scoring) | T007, T017, T022, T024, T034 |
| FR-005 (env MODEL_ID, CACHE_MODE) | T004, T017 |
| FR-006 (offline default, CI no key) | T003, T010, T015, T017, T021, T025, T032 |
| FR-007 (refresh path available) | T010, T015 |
| FR-008 (runner_id adversarial_gate) | T007, T010, T015, T021 |
| FR-009 (prompt hash from text only) | T005, T010, T015 |
| FR-010 (N=5 samples) | T008, T017, T023 |
| FR-011 (per-sample aggregate scoring) | T008, T012, T017 |
| FR-012 (variance summary) | T008, T012, T016, T026 |
| FR-013 (extended slice fixture) | T006, T013, T014 |
| FR-014 (slice coverage targets) | T006, T013, T019 |
| FR-015 (Wilson CIs + per-family tables) | T009, T027–T029 |
| FR-016 (Wilson not in core/scoring) | T009, T027–T028 |
| FR-017 (committed cache full coverage) | T003, T010, T018, T021 |
| FR-018 (acceptance suite before impl) | T002, T004–T010 |
| FR-019 (quickstart guide) | T030–T031 |
| FR-020 (feature branch only) | All tasks on `003-adversarial-gate` |
| FR-021 (vocabulary discipline) | T033 |
| SC-001 (offline CI green) | T011, T032 |
| SC-002 (100% slice coverage) | T007, T022 |
| SC-003 (five per-sample results) | T008, T021, T023 |
| SC-004 (hand-calculated rate parity) | T008, T022, T024 |
| SC-005 (Wilson bounds match fixtures) | T009, T029 |
| SC-006 (per-family tables match fixtures) | T009, T029 |
| SC-007 (additive fixtures only) | T013, T021, T034 |
| SC-008 (quickstart under 10 min) | T030 |
| SC-009 (deterministic replay) | T007, T017, T022, T035 |
| SC-010 (full slice offline replay) | T010, T021, T022 |

---

## Parallel Execution Examples

### Phase 1 Bootstrap (after T001)

```bash
# Parallel: conftest + all acceptance test files + minimal cache seed
T002 tests/gate/conftest.py
T003 cache/primary/adversarial_gate/ minimal seed
T004 test_acceptance_gate_config.py
T005 test_acceptance_label_isolation.py
T006 test_acceptance_adversarial_slice.py
T007 test_acceptance_gate_runner.py
T008 test_acceptance_gate_sample_variance.py
T009 test_acceptance_gate_report.py
T010 test_acceptance_gate_cache_offline.py
```

### Phase 2 Foundational (after tests red)

```bash
# Parallel: types + fixture + cache + variance modules
T012 runners/adversarial_gate/types.py
T013 fixtures/adversarial_slice/cases.yaml
T015 runners/adversarial_gate/cache.py
T016 runners/adversarial_gate/variance.py
# Then sequential: T014 slice_loader.py (depends on T013)
# Then sequential: T017 runner.py (depends on T012–T016)
```

### Phase 6 Report (after gate sweep green)

```bash
# Parallel: report types + Wilson module
T027 report/types.py
T028 report/wilson.py
# Then sequential: T029 adversarial_tables.py (depends on T027–T028)
```

---

## Implementation Strategy

### MVP First (User Story 1 via slice + sweep)

1. Complete Phase 1: Bootstrap — all failing tests + conftest + minimal cache
2. Complete Phase 2: Foundational — slice loader + gate spine green
3. Complete Phase 3: US2 — slice fixture validated
4. Complete Phase 4: US1 — full cache + gate sweep tests green
5. **STOP and VALIDATE**: `uv run pytest tests/gate/test_acceptance_gate_runner.py -v`
6. Continue with US4 variance, US3 report, and polish

### Incremental Delivery

1. Bootstrap + Foundational → gate orchestration proven with minimal cache
2. US2 → extended slice corpus committed and validated
3. US1 → full offline gate sweep (MVP)
4. US4 → N=5 variance and cache-miss hardening
5. US3 → Wilson CIs and per-family reporting tables
6. US6 + Polish → quickstart on-ramp and full-suite gate

### Parallel Team Strategy

With multiple developers after Phase 2:

- Developer A: Phase 4 US1 (full cache seeding + sweep validation)
- Developer B: Phase 6 US3 (report types + Wilson + tables — can start once sample scoring shape is stable from T017)
- Developer C: Expand acceptance fixtures in `tests/gate/conftest.py` and audit slice coverage (Phase 3)

After Phase 4, Developer A validates US4 variance (Phase 5) while Developer B finishes report integration (Phase 6).

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same batch
- US5 acceptance-suite-before-implementation is satisfied by Phase 1 tasks T004–T010 preceding all implementation (T012–T017)
- Do not modify `core/`, `specs/001-shared-core/`, or Feature 002 tier runners except blocking bugfixes
- Do not edit committed `export/` content (Principle III); slice and cache entries are additive only
- Refresh path (`CACHE_MODE=refresh`) remains available via gate cache helper but is not CI-gated (FR-007)
- Total tasks: **35** (Bootstrap 11, Foundational 7, US2 2, US1 2, US4 4, US3 3, Polish 6)

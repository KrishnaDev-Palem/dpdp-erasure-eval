# Tasks: Shared Core

**Input**: Design documents from `/specs/001-shared-core/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Each phase lists failing tests before implementation.

**Organization**: Tasks grouped by user story (spec.md priorities).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US6)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Reproducible Python project skeleton

- [ ] T001 Create `core/` package layout per plan.md (`core/export`, `core/model`, `core/cache`, `core/scoring`, `core/context`) with `__init__.py` files
- [ ] T002 Create `pyproject.toml` with Python 3.11, pytest, ruff, pyyaml, pydantic dependencies and `core` package discovery
- [ ] T003 Run `uv lock` and commit `uv.lock`
- [ ] T004 [P] Add `ruff` lint/format config in `pyproject.toml` (line length, target py311)
- [ ] T005 [P] Add `.env.example` with `MODEL_API_KEY`, `MODEL_ID`, `CACHE_MODE` variable names (no values)
- [ ] T006 [P] Ensure `.gitignore` covers `.env`, `__pycache__`, `.pytest_cache`, `.ruff_cache`
- [ ] T007 [P] Create `tests/core/conftest.py` with shared fixtures path (`export/`, `cache/`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, ADR, export fixture scaffold — blocks all user stories

**⚠️ CRITICAL**: No user story implementation until this phase completes

- [ ] T008 Author `docs/adr/0001-frozen-export-ground-truth.md` (eval methodology + frozen-export coupling)
- [ ] T009 [P] Create `docs/adr/README.md` indexing ADR-0001
- [ ] T010 [P] Create shared domain types in `core/types.py` per data-model.md (`ErasureRequest`, `ExpectedLabel`, `LabeledLocation`, `ModelVerdict`, `ClassifierResult`, `ContextBundle`, `Rate`)
- [ ] T011 [P] Create `core/exceptions.py` with `ProvenanceError`, `CacheMissError`, `ModelResponseError`, `ExportLoadError`
- [ ] T012 Scaffold committed export fixture: `export/PINNED_AGENT_SHA`, `export/manifest.yaml`, `export/adjudication/subjects.yaml`, `export/rules/retention_floors.yaml`, `export/rules/governance_map.yaml`, `export/adversarial_seeds/seeds.yaml` (minimal representative content; full agent export at pinned SHA)
- [ ] T013 [P] Add `scripts/regenerate_export.py` stub documenting deliberate re-export only (no default execution)

**Checkpoint**: Foundation ready — user story work can begin

---

## Phase 3: User Story 1 — Load and Verify Frozen Answer Key (Priority: P1) 🎯 MVP

**Goal**: Loader exposes answer key, rules, seeds; provenance verifies pinned agent SHA

**Independent Test**: `uv run pytest tests/core/test_acceptance_export.py tests/core/test_acceptance_provenance.py -v`

### Tests for User Story 1 (write first — MUST FAIL)

- [ ] T014 [P] [US1] Acceptance tests for export loading in `tests/core/test_acceptance_export.py` (subjects, `expected` blocks, rules, three seeds, no `expected` in raw API)
- [ ] T015 [P] [US1] Acceptance tests for provenance in `tests/core/test_acceptance_provenance.py` (match success, SHA mismatch fail, URL mismatch fail, fail-closed)

### Implementation for User Story 1

- [ ] T016 [US1] Implement `core/export/provenance.py` — read `PINNED_AGENT_SHA`, validate manifest per `contracts/frozen-export.md`
- [ ] T017 [US1] Implement `core/export/loader.py` — parse YAML, return typed `ExportBundle` with subjects, rules, seeds; call provenance before expose
- [ ] T018 [US1] Export public API in `core/export/__init__.py` (`load_export`, `verify_provenance`)
- [ ] T019 [US1] Verify US1 acceptance tests pass; confirm tests failed before T016–T018

**Checkpoint**: Export loads and provenance gate passes on committed fixture

---

## Phase 4: User Story 2 — Score Adjudication Verdicts (Priority: P1)

**Goal**: Per-lane confusion matrix and standalone over-erasure / over-retention / mis-escalation rates

**Independent Test**: `uv run pytest tests/core/test_acceptance_scoring_adjudication.py -v`

### Tests for User Story 2 (write first — MUST FAIL)

- [ ] T020 [P] [US2] Acceptance tests in `tests/core/test_acceptance_scoring_adjudication.py` per `contracts/scoring.md` (matrix cells, over-erasure standalone, no blended accuracy, empty input, invalid verdict)

### Implementation for User Story 2

- [ ] T021 [US2] Implement `core/scoring/adjudication.py` — `score_adjudication(pairs) -> AdjudicationScoringResult`
- [ ] T022 [US2] Export API in `core/scoring/__init__.py`
- [ ] T023 [US2] Verify US2 tests pass; hand-computed fixture values match

**Checkpoint**: Adjudication scoring primitives ready for Feature 002 runners

---

## Phase 5: User Story 3 — Adversarial Rate Primitives (Priority: P3, minimal)

**Goal**: Detection rate, false-alarm rate, per-family breakdown

**Independent Test**: `uv run pytest tests/core/test_acceptance_scoring_adversarial.py -v`

### Tests for User Story 3 (write first — MUST FAIL)

- [ ] T024 [P] [US3] Acceptance tests in `tests/core/test_acceptance_scoring_adversarial.py` per `contracts/scoring.md` (detection, false-alarm, per-family, empty denominators)

### Implementation for User Story 3

- [ ] T025 [US3] Implement `core/scoring/adversarial.py` — `score_adversarial(pairs) -> AdversarialScoringResult`
- [ ] T026 [US3] Wire adversarial exports in `core/scoring/__init__.py`
- [ ] T027 [US3] Verify US3 tests pass

**Checkpoint**: Adversarial scoring primitives ready for Feature 003

---

## Phase 6: User Story 6 — Assemble Tier-Appropriate Context (Priority: P3)

**Goal**: T1/T2/T3 context bundles from export; no `expected` leakage

**Independent Test**: `uv run pytest tests/core/test_acceptance_context.py -v`

*Implemented before US4/US5 because cache and model seam depend on `ContextBundle`.*

### Tests for User Story 6 (write first — MUST FAIL)

- [ ] T028 [P] [US6] Acceptance tests in `tests/core/test_acceptance_context.py` per `contracts/context-tiers.md` (T1 request-only, T2 records, T3 rules, no expected, tier delta)

### Implementation for User Story 6

- [ ] T029 [US6] Implement `core/context/tiers.py` — `build_t1`, `build_t2`, `build_t3`
- [ ] T030 [US6] Export API in `core/context/__init__.py`
- [ ] T031 [US6] Verify US6 tests pass

**Checkpoint**: Context helpers ready for tier runners and cache hashing

---

## Phase 7: User Story 5 — Offline Cache Replay (Priority: P2)

**Goal**: Committed cache entries, offline replay, explicit refresh path, N=5 sample keys

**Independent Test**: `uv run pytest tests/core/test_acceptance_cache.py -v` (offline tests without API key)

### Tests for User Story 5 (write first — MUST FAIL)

- [ ] T032 [P] [US5] Acceptance tests in `tests/core/test_acceptance_cache.py` per `contracts/cache.md` (hit, miss error, canonical hash stability, sample_index 0–4, refresh opt-in via marker)

### Implementation for User Story 5

- [ ] T033 [P] [US5] Implement `core/cache/canonicalize.py` — stable JSON canonicalization + SHA-256 `prompt_hash`
- [ ] T034 [US5] Implement `core/cache/store.py` — read/write/list, `CACHE_MODE` offline vs refresh
- [ ] T035 [US5] Seed minimal committed cache entry under `cache/` for acceptance fixture
- [ ] T036 [US5] Export API in `core/cache/__init__.py`
- [ ] T037 [US5] Verify US5 offline tests pass without `MODEL_API_KEY`

**Checkpoint**: Offline replay works; refresh path tested only when opted in

---

## Phase 8: User Story 4 — Injectable Model Seam (Priority: P2)

**Goal**: Protocol + `FakeModelSeam`; adjudicate and classify_note; config-driven model id

**Independent Test**: `uv run pytest tests/core/test_acceptance_model_seam.py -v`

### Tests for User Story 4 (write first — MUST FAIL)

- [ ] T038 [P] [US4] Acceptance tests in `tests/core/test_acceptance_model_seam.py` per `contracts/model-seam.md` (fake double, no network, classify note text only, adjudicate per location)

### Implementation for User Story 4

- [ ] T039 [US4] Implement `core/model/seam.py` — `ModelSeam` protocol, config from env, `NotConfiguredError` for live path without key
- [ ] T040 [P] [US4] Implement `core/model/fake.py` — `FakeModelSeam` with call recording
- [ ] T041 [US4] Export API in `core/model/__init__.py`
- [ ] T042 [US4] Verify US4 tests pass offline

**Checkpoint**: Model seam injectable; Feature 002/003 can wire live provider later

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: CI, full suite, quickstart validation

- [ ] T043 [P] Add GitHub Actions workflow `.github/workflows/ci.yml` — `uv sync`, `ruff check`, `ruff format --check`, `pytest tests/core` (no secrets)
- [ ] T044 [P] Add pre-commit config `.pre-commit-config.yaml` — ruff + file hygiene per constitution
- [ ] T045 Run full core suite: `uv run pytest tests/core -v` — all green offline
- [ ] T046 Run quickstart.md validation steps end-to-end
- [ ] T047 [P] Add `LICENSE` (MIT) at repository root
- [ ] T048 Review terminology in error messages (DPDP, T1/T2/T3) across `core/`

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends on | Blocks |
|-------|------------|--------|
| 1 Setup | — | 2 |
| 2 Foundational | 1 | 3–8 |
| 3 US1 Export | 2 | — |
| 4 US2 Adjudication scoring | 2 | — |
| 5 US3 Adversarial scoring | 2 | — |
| 6 US6 Context | 2, US1 (loader) | 7, 8 |
| 7 US5 Cache | 2, US6 (canonicalize) | — |
| 8 US4 Model seam | 2, US6 (ContextBundle) | — |
| 9 Polish | 3–8 | — |

### User Story Independence

- **US1** and **US2** can proceed in parallel after Phase 2 (US2 uses hand-crafted pairs, not loader).
- **US3** parallel with US2 after Phase 2.
- **US6** needs US1 loader for integration tests (real subject); implement after US1.
- **US5** needs US6 `canonicalize` on real `ContextBundle`.
- **US4** needs US6 types; implement after US6.

### Parallel Opportunities

```bash
# After Phase 2 — P1 stories in parallel:
T014, T015   # US1 tests
T020         # US2 tests
T024         # US3 tests

# After US1 — context + remaining:
T028         # US6 tests
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Phase 1–2: Setup + foundational types + export scaffold
2. Phase 3: US1 export loader + provenance
3. Phase 4: US2 adjudication scoring
4. **STOP and VALIDATE**: `pytest tests/core/test_acceptance_export.py tests/core/test_acceptance_provenance.py tests/core/test_acceptance_scoring_adjudication.py`

### Full Feature 001 (planning §8 definition of done)

Complete Phases 1–9. Success: core suite green; export loads and verifies pinned SHA.

### Suggested PR scope

Single PR `001-shared-core` with all phases; human merge after green CI.

---

## Notes

- Do not edit committed export or seed content after acceptance (frozen-interface discipline).
- Do not add `runners/`, `cli`, `report/`, or `core/tools/` in this feature.
- Primary model string is config-only — never hardcode in `core/`.
- Total tasks: **48** (Setup 7, Foundational 6, US1 6, US2 4, US3 4, US6 4, US5 6, US4 5, Polish 6)

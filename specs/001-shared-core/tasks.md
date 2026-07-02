# Tasks: Shared Core

**Input**: Design documents from `/specs/001-shared-core/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Each module phase lists failing tests before implementation.

**Organization**: Execution order follows project bootstrap → export loader → model seam → cache → scoring → context helpers. User story labels (US1–US6) map to spec.md for traceability.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US6) on user-story phase tasks only

---

## Phase 1: Setup — Project Bootstrap

**Purpose**: Reproducible Python project skeleton with uv, lint, pre-commit, and CI gate (offline, no secrets)

- [X] T001 Create `core/` package layout per plan.md (`core/export`, `core/model`, `core/cache`, `core/scoring`, `core/context`) with empty `__init__.py` files
- [X] T002 Create `pyproject.toml` with Python 3.11, `pytest`, `ruff`, `pyyaml`, `pydantic` v2, and `core` package discovery
- [X] T003 Run `uv lock` and commit `uv.lock` at repository root
- [X] T004 [P] Add `ruff` lint and format config in `pyproject.toml` (target py311, line length per project convention)
- [X] T005 [P] Add `.env.example` with `MODEL_API_KEY`, `MODEL_ID`, `CACHE_MODE` variable names and no values
- [X] T006 [P] Ensure `.gitignore` covers `.env`, `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.venv`
- [X] T007 Add `.pre-commit-config.yaml` with `ruff` lint/format and basic file hygiene (trailing whitespace, end-of-file, YAML check) per constitution
- [X] T008 Add GitHub Actions CI skeleton in `.github/workflows/ci.yml` — `uv sync`, `ruff check`, `ruff format --check`, `pytest tests/core` placeholder (no secrets)
- [X] T009 Create `tests/core/conftest.py` with shared paths to `export/` and `cache/` fixtures

**Checkpoint**: `uv sync` succeeds; CI workflow file exists; pre-commit config present

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared types, exceptions, ADR, and export fixture scaffold — blocks all user stories

**⚠️ CRITICAL**: No user story implementation until this phase completes

- [X] T010 Author `docs/adr/0001-frozen-export-ground-truth.md` (eval methodology + frozen-export ground-truth coupling)
- [X] T011 [P] Create `docs/adr/README.md` indexing ADR-0001
- [X] T012 [P] Create shared domain types in `core/types.py` per data-model.md (`ErasureRequest`, `ExpectedLabel`, `LabeledLocation`, `AdjudicationSubject`, `ModelVerdict`, `ClassifierResult`, `ContextBundle`, `Rate`, `CacheKey`, `CacheEntry`)
- [X] T013 [P] Create `core/exceptions.py` with `ProvenanceError`, `ExportLoadError`, `CacheMissError`, `ModelResponseError`
- [X] T014 Scaffold committed export fixture: `export/PINNED_AGENT_SHA`, `export/manifest.yaml`, `export/adjudication/subjects.yaml`, `export/rules/retention_floors.yaml`, `export/rules/governance_map.yaml`, `export/adversarial_seeds/seeds.yaml` (minimal representative content; full agent export at pinned SHA; re-verify statute citations per research R7 before commit)
- [X] T015 [P] Add `scripts/regenerate_export.py` stub documenting deliberate re-export only (must not run in CI or default workflows)

**Checkpoint**: Foundation ready — export loader work can begin

---

## Phase 3: User Story 1 — Load and Verify Frozen Answer Key (Priority: P1) 🎯 MVP

**Goal**: Loader exposes answer key, rules, and seeds; provenance verifies pinned agent SHA

**Independent Test**: `uv run pytest tests/core/test_acceptance_export.py tests/core/test_acceptance_provenance.py -v`

### Tests for User Story 1 (write first — MUST FAIL)

- [X] T016 [P] [US1] Add acceptance tests for export loading in `tests/core/test_acceptance_export.py` (subjects parse, `expected` blocks available, five retention floors, governance map, three frozen seeds unchanged; missing/malformed/incomplete export raises `ExportLoadError` with no partial case data)
- [X] T017 [P] [US1] Add acceptance tests for provenance in `tests/core/test_acceptance_provenance.py` (match success, SHA mismatch fail, URL mismatch fail, fail-closed with no case data exposed)

### Implementation for User Story 1

- [X] T018 [US1] Implement `core/export/provenance.py` — read `export/PINNED_AGENT_SHA`, validate `manifest.yaml` per `contracts/frozen-export.md`, raise `ProvenanceError` on mismatch
- [X] T019 [US1] Implement manifest and rules parsing in `core/export/loader.py` per `contracts/frozen-export.md`
- [X] T020 [US1] Implement subjects and adversarial-seed parsing in `core/export/loader.py`; return typed export bundle; invoke provenance before exposing data
- [X] T021 [US1] Export public API in `core/export/__init__.py` (`load_export`, `verify_provenance`)
- [X] T022 [US1] Confirm US1 acceptance tests pass (must have failed before T018–T021)

**Checkpoint**: Export loads and provenance gate passes on committed fixture

---

## Phase 4: User Story 4 — Injectable Model Seam (Priority: P2)

**Goal**: Protocol + `FakeModelSeam`; adjudicate and `classify_note`; config-driven model id (uses `ContextBundle` type from `core/types.py`, not tier builders)

**Independent Test**: `uv run pytest tests/core/test_acceptance_model_seam.py -v`

### Tests for User Story 4 (write first — MUST FAIL)

- [X] T023 [P] [US4] Add acceptance tests in `tests/core/test_acceptance_model_seam.py` per `contracts/model-seam.md` (fake double, no network, `classify_note` text-only, `adjudicate` one verdict per location, invalid verdict raises `ModelResponseError`)

### Implementation for User Story 4

- [X] T024 [US4] Implement `ModelSeam` protocol and config loading in `core/model/seam.py` (`MODEL_ID` from env; no provider client at import time)
- [X] T025 [P] [US4] Implement `FakeModelSeam` with call recording in `core/model/fake.py`
- [X] T026 [US4] Export API in `core/model/__init__.py`
- [X] T027 [US4] Confirm US4 acceptance tests pass offline without `MODEL_API_KEY`

**Checkpoint**: Model seam injectable; tests use hand-crafted `ContextBundle` instances

---

## Phase 5: User Story 5 — Offline Cache Replay (Priority: P2)

**Goal**: Committed cache entries, offline replay, explicit refresh path, N=5 sample keys

**Independent Test**: `uv run pytest tests/core/test_acceptance_cache.py -v` (offline tests without API key)

### Tests for User Story 5 (write first — MUST FAIL)

- [X] T028 [P] [US5] Add acceptance tests in `tests/core/test_acceptance_cache.py` per `contracts/cache.md` (cache hit, miss raises `CacheMissError`, canonical hash stability, `sample_index` 0–4 keys, refresh opt-in via pytest marker)

### Implementation for User Story 5

- [X] T029 [P] [US5] Implement stable JSON canonicalization and SHA-256 `prompt_hash` in `core/cache/canonicalize.py`
- [X] T030 [US5] Implement cache read and key path layout in `core/cache/store.py` per `contracts/cache.md`
- [X] T031 [US5] Implement cache write and `CACHE_MODE` offline vs refresh behavior in `core/cache/store.py`
- [X] T032 [US5] Seed minimal committed cache entry under `cache/` for acceptance fixture
- [X] T033 [US5] Export API in `core/cache/__init__.py`
- [X] T034 [US5] Confirm US5 offline tests pass without `MODEL_API_KEY`

**Checkpoint**: Offline replay works; refresh path tested only when opted in

---

## Phase 6: User Story 2 — Score Adjudication Verdicts (Priority: P1)

**Goal**: Per-lane confusion matrix and standalone over-erasure / over-retention / mis-escalation rates

**Independent Test**: `uv run pytest tests/core/test_acceptance_scoring_adjudication.py -v`

### Tests for User Story 2 (write first — MUST FAIL)

- [X] T035 [P] [US2] Add acceptance tests in `tests/core/test_acceptance_scoring_adjudication.py` per `contracts/scoring.md` (3×3 matrix, over-erasure standalone, no blended accuracy, empty input null rates, invalid verdict validation failure)

### Implementation for User Story 2

- [X] T036 [US2] Implement confusion matrix and standalone rates in `core/scoring/adjudication.py` — `score_adjudication(pairs) -> AdjudicationScoringResult`
- [X] T037 [US2] Export adjudication API in `core/scoring/__init__.py`
- [X] T038 [US2] Confirm US2 tests pass; hand-computed fixture values match

**Checkpoint**: Adjudication scoring primitives ready for Feature 002 runners

---

## Phase 7: User Story 3 — Adversarial Rate Primitives (Priority: P3, minimal)

**Goal**: Detection rate, false-alarm rate, per-family breakdown (pure functions; no runner or slice)

**Independent Test**: `uv run pytest tests/core/test_acceptance_scoring_adversarial.py -v`

### Tests for User Story 3 (write first — MUST FAIL)

- [X] T039 [P] [US3] Add acceptance tests in `tests/core/test_acceptance_scoring_adversarial.py` per `contracts/scoring.md` (detection rate, false-alarm rate, per-family breakdown, empty denominators, three frozen seed shapes as fixture input)

### Implementation for User Story 3

- [X] T040 [US3] Implement detection and false-alarm rate functions in `core/scoring/adversarial.py` — `score_adversarial(pairs) -> AdversarialScoringResult`
- [X] T041 [US3] Wire adversarial exports in `core/scoring/__init__.py`
- [X] T042 [US3] Confirm US3 tests pass

**Checkpoint**: Adversarial scoring primitives ready for Feature 003

---

## Phase 8: User Story 6 — Assemble Tier-Appropriate Context (Priority: P3)

**Goal**: T1/T2/T3 context bundles from export; no `expected` leakage; compatible with `canonicalize()`

**Independent Test**: `uv run pytest tests/core/test_acceptance_context.py -v`

### Tests for User Story 6 (write first — MUST FAIL)

- [X] T043 [P] [US6] Add acceptance tests in `tests/core/test_acceptance_context.py` per `contracts/context-tiers.md` (T1 request-only, T2 records without `expected`, T3 rules + governance map, adjacent-tier delta, ground truth excluded, subject with zero locations does not invent records)

### Implementation for User Story 6

- [X] T044 [US6] Implement `build_t1` in `core/context/tiers.py`
- [X] T045 [US6] Implement `build_t2` and `build_t3` in `core/context/tiers.py`
- [X] T046 [US6] Export API in `core/context/__init__.py`
- [X] T047 [US6] Confirm US6 tests pass; bundles hash consistently via `core/cache/canonicalize.py`

**Checkpoint**: Context helpers ready for tier runners in Feature 002

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Full-suite validation, licensing, terminology, and constitution repository gates (README on-ramp)

- [X] T048 Run full core acceptance suite: `uv run pytest tests/core -v` — all green offline
- [X] T049 Run quickstart.md validation steps end-to-end
- [X] T050 [P] Add MIT `LICENSE` at repository root
- [X] T051 [P] Review DPDP and T1/T2/T3 terminology in user-facing error messages across `core/`
- [X] T052 [P] Add minimal thesis-first `README.md` at repository root (clone path, offline `uv sync` + `pytest tests/core`, CI badge placeholder; reader-facing tier names per constitution repository quality gates)

---

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends on | Blocks |
|-------|------------|--------|
| 1 Bootstrap | — | 2 |
| 2 Foundational | 1 | 3–8 |
| 3 US1 Export | 2 | 8 (loader integration in context tests) |
| 4 US4 Model seam | 2 (`ContextBundle` type) | — |
| 5 US5 Cache | 2, 4 optional (seam for refresh tests) | — |
| 6 US2 Adjudication scoring | 2 | — |
| 7 US3 Adversarial scoring | 2 | — |
| 8 US6 Context | 2, 3 (loader for real subjects) | — |
| 9 Polish | 3–8 | — |

### Execution Sequence (binding)

```text
Bootstrap → Foundational → US1 export (tests → impl) → US4 model seam (tests → impl)
  → US5 cache (tests → impl) → US2 adjudication scoring (tests → impl)
  → US3 adversarial scoring (tests → impl) → US6 context (tests → impl) → Polish
```

### Within Each User Story

- Acceptance tests MUST fail for the right reason before implementation tasks in that phase
- Implementation tasks within a phase run sequentially unless marked [P]

### Parallel Opportunities

```bash
# Phase 1 bootstrap (after T003):
T004, T005, T006

# Phase 2 foundational (after T010):
T011, T012, T013, T015

# US1 tests (after Phase 2):
T016, T017

# Independent scoring test authoring (after Phase 2, before impl):
T035   # US2 adjudication tests
T039   # US3 adversarial tests
```

---

## Parallel Example: User Story 1

```bash
# Launch export acceptance tests together (must fail before impl):
Task T016: tests/core/test_acceptance_export.py
Task T017: tests/core/test_acceptance_provenance.py

# Then implement sequentially:
T018 → T019 → T020 → T021 → T022
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Phase 1–2: Bootstrap + foundational types + export scaffold
2. Phase 3: US1 export loader + provenance (tests first)
3. Phase 6: US2 adjudication scoring (tests first; hand-crafted pairs, no loader dependency)
4. **STOP and VALIDATE**: `uv run pytest tests/core/test_acceptance_export.py tests/core/test_acceptance_provenance.py tests/core/test_acceptance_scoring_adjudication.py -v`

### Full Feature 001 (planning §8 definition of done)

Complete Phases 1–9 in execution order. Success: core suite green offline; export loads and verifies pinned SHA.

### Incremental Delivery

| Increment | Phases | Delivers |
|-----------|--------|----------|
| MVP | 1–3, 6 | Verified export + adjudication scoring |
| Reproducibility spine | +4–5 | Model seam + offline cache |
| Complete shared core | +7–9 | Adversarial rates + context tiers + polish |

---

## Notes

- Do not edit committed export or seed content after acceptance (frozen-interface discipline).
- Do not add `runners/`, `cli`, `report/`, or `core/tools/` in this feature.
- Primary model string is config-only — never hardcode in `core/`.
- Agent MUST NOT merge to `main`; human review and merge after green CI.
- US4/US5 tests use hand-crafted `ContextBundle` objects from `core/types.py` until US6 lands.

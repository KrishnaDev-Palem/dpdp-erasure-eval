# Tasks: Live Model Seam Wiring

**Input**: Design documents from `/specs/006-live-model-seam/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, quickstart.md, research.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Every phase lists **failing acceptance tests before implementation tasks**. Run each test checkpoint and confirm failures are import/`NotImplementedError`/assertion gaps — not fixture or export errors.

**Organization**: Setup → Foundational (role registry + credentials) → User stories by dependency order (US1 offline MVP → US3 adapters → US4 factory refresh → US2 refresh integration → US5 env) → Polish

**Branch**: `006-live-model-seam`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US5) for story-phase tasks only
- FR/SC references trace tasks to spec requirements

## Path Conventions

- Model seam: `core/model/` at repository root (extends Feature 001; `seam.py`, `fake.py` unchanged surface)
- New modules: `core/model/roles.py`, `credentials.py`, `factory.py`, `anthropic_adapter.py`, `gemini_adapter.py`
- Cache helpers (read-only — do not modify): `core/cache/store.py`, `runners/adversarial_gate/cache.py`, `runners/autonomous/cache.py`
- Runners (unchanged orchestration — seam injection only): `runners/t1.py`, `t2.py`, `t3.py`, `runners/autonomous/`, `runners/adversarial_gate/`
- CLI: `cli/main.py` — replace hardcoded `FakeModelSeam()` with `create_model_seam()`
- Acceptance tests: `tests/core/test_acceptance_model_factory.py`, `test_acceptance_live_adapters.py`, `test_acceptance_provider_credentials.py`; extend `tests/cli/test_acceptance_cli.py`
- Opt-in live smoke: `tests/live/` with `@pytest.mark.live` (excluded from CI)
- Config: `.env.example` (no secrets)
- Frozen artifacts: `export/`, committed `cache/` — no content edits (FR-012)

---

## Phase 1: Setup (Dependencies & Test Scaffolding)

**Purpose**: Add SDK dependencies, shared exception type, pytest markers, and test harness scaffolding so Feature 006 acceptance tests can fail for the right reason before implementation.

**Independent Test**: Baseline Features 001–005 suites green; new test modules import but fail on missing `create_model_seam` / adapter modules.

- [X] T001 Add runtime dependencies `anthropic>=0.49.0,<1` and `google-genai>=1.14.0,<2` to `pyproject.toml` and refresh `uv.lock` per plan.md Complexity Tracking (FR-002)
- [X] T002 Add `ConfigurationError` to `core/exceptions.py` for factory/credential resolution failures before network (FR-014, contracts/model-seam-factory.md)
- [X] T003 [P] Register `@pytest.mark.live` in `pyproject.toml` `[tool.pytest.ini_options].markers` with description "opt-in live provider smoke tests requiring API keys"; confirm `addopts = "-m 'not live'"` excludes live smoke from default `uv run pytest -v` (FR-010, research R8) — **pre-applied in remediation; verify during setup**
- [X] T004 [P] Create `tests/live/__init__.py` and skeleton `tests/live/test_live_smoke.py` with `@pytest.mark.live` tests marked `pytest.skip` until adapters land (FR-010)
- [X] T005 [P] Extend or create factory-test fixtures in `tests/core/conftest.py`: helpers to set/clear `MODEL_ID`, `CACHE_MODE`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MODEL_API_KEY` via `monkeypatch` (FR-005)
- [X] T006 Verify Features 001–005 baseline: `uv run pytest tests/core tests/runners tests/gate tests/autonomous tests/report tests/cli -v` passes with zero API keys (FR-011, SC-001)

**Checkpoint (Setup)**:

```bash
uv run pytest tests/core tests/runners tests/gate tests/autonomous tests/report tests/cli -v
```

**Expected**: All existing suites green. No `core/model/factory.py` yet.

---

## Phase 2: Foundational — Role Registry & Credential Policy

**Purpose**: Static role registry and credential resolution — blocking prerequisites for factory and live adapters.

**Goal**: Harness roles map to pinned provider model ids; credential precedence and deprecation policy enforced (data-model.md, research R3/R5).

**Independent Test**: Role and credential acceptance tests pass; factory/adapter tests still fail until Phases 3–5.

**Depends on**: Phase 1 complete.

### Tests for Foundational (MANDATORY — write first, ensure FAIL) ⚠️

- [X] T007 [P] Write failing `test_role_registry_lists_primary_claude_and_gemini_roles` and `test_live_roles_have_pinned_provider_model_ids` in `tests/core/test_acceptance_model_factory.py` asserting `claude-sonnet-5` → `claude-sonnet-5`, `gemini-3.5-flash` → `gemini-3.5-flash`, `primary` → offline-only (FR-002, FR-007, contracts/model-seam-factory.md)
- [X] T008 [P] Write failing credential tests in `tests/core/test_acceptance_provider_credentials.py`: (a) `test_anthropic_key_from_anthropic_api_key`; (b) `test_gemini_key_from_gemini_api_key`; (c) `test_legacy_model_api_key_fallback_emits_deprecation_warning`; (d) `test_provider_specific_key_wins_when_both_set`; (e) `test_missing_credential_raises_configuration_error_naming_required_vars` (FR-006, FR-014, US5)

### Implementation for Foundational

- [X] T009 [P] Implement `ModelRoleDescriptor` registry and lookup helpers in `core/model/roles.py` per data-model.md (roles: `primary`, `claude-sonnet-5`, `gemini-3.5-flash`)
- [X] T010 [P] Implement `resolve_provider_api_key(*, provider)` returning credential policy dataclass in `core/model/credentials.py` with precedence order from research R5
- [X] T011 Export `get_role_descriptor`, `resolve_provider_api_key`, and registry types from `core/model/__init__.py`

**Checkpoint (Foundational)**:

```bash
uv run pytest tests/core/test_acceptance_model_factory.py::test_role_registry_lists_primary_claude_and_gemini_roles tests/core/test_acceptance_provider_credentials.py -v
```

**Expected**: Role and credential tests green; factory resolution tests still fail (no `create_model_seam` yet).

---

## Phase 3: User Story 1 — Offline Default Unchanged (Priority: P1) 🎯 MVP

**Goal**: Default and CI remain fully offline — `FakeModelSeam` at the seam, committed cache replay, no network, no API keys. CLI uses factory but offline behavior matches Feature 005 contract (FR-003, FR-011, SC-001).

**Independent Test**: Clean clone, default env, `uv run pytest -v` — 100% pass, zero keys, no network. Factory returns `FakeModelSeam` even when provider keys are present.

**Depends on**: Phase 2 complete.

### Tests for User Story 1 (MANDATORY — write first, ensure FAIL) ⚠️

- [X] T012 [P] [US1] Write failing `test_offline_factory_returns_fake_model_seam` in `tests/core/test_acceptance_model_factory.py` asserting `create_model_seam()` with `CACHE_MODE=offline` returns `FakeModelSeam` instance (FR-003, US4 scenario 1)
- [X] T013 [P] [US1] Write failing `test_offline_factory_returns_fake_even_when_api_keys_set` in `tests/core/test_acceptance_model_factory.py` with `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` set — still `FakeModelSeam` (FR-003, US4 scenario 1)
- [X] T014 [P] [US1] Write failing `test_offline_factory_respects_any_model_id` in `tests/core/test_acceptance_model_factory.py` parametrized over `primary`, `claude-sonnet-5`, `gemini-3.5-flash` — always `FakeModelSeam` in offline mode (US1 scenario 2)
- [X] T015 [P] [US1] Write failing `test_cli_uses_create_model_seam_not_hardcoded_fake` in `tests/cli/test_acceptance_cli.py` using `unittest.mock.patch` on `core.model.factory.create_model_seam` — assert called for `t2` subcommand; existing offline exit-0 tests unchanged (FR-005, US1 scenario 2)
- [X] T016 [US1] Write failing FakeModelSeam regression guard in `tests/core/test_acceptance_model_seam.py`: add `test_fake_model_seam_regression_unchanged` asserting existing adjudicate/classify_note/tool_registry contract tests still pass — no behavior change to `core/model/fake.py` (FR-003, US1 scenario 4)
- [X] T017 [P] [US1] Confirm existing offline cache-miss tests remain green without live fallback: run `uv run pytest -m cache_miss -v` and assert no code path invokes factory live adapters (US1 scenario 3, FR-003)

### Implementation for User Story 1

- [X] T018 [US1] Implement `create_model_seam(*, config=None)` offline branch in `core/model/factory.py` — always `FakeModelSeam()`; lazy-import live adapters only inside refresh branch; no SDK import at module load (contracts/model-seam-factory.md)
- [X] T019 [US1] Replace `FakeModelSeam()` with `create_model_seam()` in `cli/main.py` for `t1`, `t2`, `t3`, `autonomous`, and `adversarial-gate` subcommands (FR-005)
- [X] T020 [US1] Export `create_model_seam` from `core/model/__init__.py`

**Checkpoint (US1 — offline MVP)**:

```bash
uv run pytest tests/core/test_acceptance_model_factory.py tests/core/test_acceptance_model_seam.py tests/cli/test_acceptance_cli.py -v
uv run pytest -v
```

**Expected**: Full offline suite green with zero API keys. Refresh/factory guard and live adapter tests still fail or skip.

---

## Phase 4: User Story 3 — Provider Adapters Behind Model Seam (Priority: P1)

**Goal**: `AnthropicModelSeam` and `GeminiModelSeam` satisfy `ModelSeam` for adjudicate (tier + autonomous tool_registry), classify_note (gate), with contract validation and `ModelResponseError` on malformed responses (FR-001, FR-008, FR-013).

**Independent Test**: Mocked SDK acceptance tests pass for both providers covering verdict pairing, classification, tool-call session shape, and error paths — no network, no keys.

**Depends on**: Phase 2 complete (roles + credentials). Can proceed in parallel with Phase 5 tests once T018 stub exists.

### Tests for User Story 3 (MANDATORY — write first, ensure FAIL) ⚠️

- [X] T021 [P] [US3] Write failing Anthropic tier `adjudicate` tests in `tests/core/test_acceptance_live_adapters.py` with mocked `anthropic` client — N verdicts for N locations, enum validation (US3 scenario 1, contracts/live-adapters.md)
- [X] T022 [P] [US3] Write failing Anthropic `classify_note` tests in `tests/core/test_acceptance_live_adapters.py` — text-only input, `{clean, adversarial}` outcome (US3 scenario 2)
- [X] T023 [P] [US3] Write failing Anthropic autonomous `adjudicate(..., tool_registry=...)` tests in `tests/core/test_acceptance_live_adapters.py` — returns `AdjudicationSessionResult` with ordered `tool_calls` trace (FR-008, US3 scenario 3)
- [X] T024 [P] [US3] Write failing Gemini tier adjudicate and classify_note tests in `tests/core/test_acceptance_live_adapters.py` with mocked `google.genai` client (US3 scenarios 1–2)
- [X] T025 [P] [US3] Write failing Gemini autonomous tool_registry session tests in `tests/core/test_acceptance_live_adapters.py` (FR-008)
- [X] T026 [P] [US3] Write failing `test_malformed_provider_response_raises_model_response_error` for both adapters in `tests/core/test_acceptance_live_adapters.py` — no partial return (FR-013)
- [X] T027 [US3] Write failing `test_adapters_use_registry_pinned_model_ids` asserting provider calls use ids from `core/model/roles.py` not hardcoded strings in adapter modules (FR-002, FR-007, US3 scenario 4)
- [X] T028 [P] [US3] Write failing `test_adapter_respects_max_tool_rounds` in `tests/core/test_acceptance_live_adapters.py` — exceed limit raises clear error (contracts/live-adapters.md)

### Implementation for User Story 3

- [X] T029 [P] [US3] Implement `LiveAdapterConfig` frozen dataclass in `core/model/anthropic_adapter.py` per data-model.md (timeout default 120s, max_tool_rounds default 10)
- [X] T030 [US3] Implement `AnthropicModelSeam` in `core/model/anthropic_adapter.py`: lazy SDK import, tier adjudicate, classify_note, tool-use loop; Sonnet 5 sampling/thinking constraints per research R1 (FR-001)
- [X] T031 [US3] Implement `GeminiModelSeam` in `core/model/gemini_adapter.py`: lazy SDK import, tier adjudicate, classify_note, tool-use loop; Gemini 3.5 `thinking_level=low` default per research R2 (FR-001)
- [X] T032 [US3] Export `AnthropicModelSeam`, `GeminiModelSeam`, `LiveAdapterConfig` from `core/model/__init__.py`

**Checkpoint (US3 — adapter contracts)**:

```bash
uv run pytest tests/core/test_acceptance_live_adapters.py -v
```

**Expected**: All mocked adapter tests green. Factory refresh resolution tests may still fail.

---

## Phase 5: User Story 4 — Factory Swaps Seam via Configuration (Priority: P2)

**Goal**: `create_model_seam()` selects live adapter by `MODEL_ID` in refresh mode; fails before network on unknown role, `primary` in refresh, or missing credentials; runner constructor injection bypasses factory (FR-005, FR-007, FR-014).

**Independent Test**: Factory tests pass for offline (Phase 3) plus refresh guards; injected `FakeModelSeam` in runner tests unchanged.

**Depends on**: Phase 2 (roles, credentials), Phase 3 (factory offline), Phase 4 (adapters).

### Tests for User Story 4 (MANDATORY — write first, ensure FAIL) ⚠️

- [X] T033 [P] [US4] Write failing `test_refresh_returns_anthropic_adapter_for_claude_role` in `tests/core/test_acceptance_model_factory.py` with mocked credential resolution — no HTTP (US4 scenario 2)
- [X] T034 [P] [US4] Write failing `test_refresh_returns_gemini_adapter_for_gemini_role` in `tests/core/test_acceptance_model_factory.py` (US4 scenario 2)
- [X] T035 [P] [US4] Write failing `test_refresh_primary_raises_configuration_error` in `tests/core/test_acceptance_model_factory.py` before any adapter construction (research R5, US4 scenario 3)
- [X] T036 [P] [US4] Write failing `test_refresh_unknown_model_id_raises_configuration_error` listing supported live roles in `tests/core/test_acceptance_model_factory.py` (US4 scenario 3)
- [X] T037 [P] [US4] Write failing `test_refresh_missing_credential_raises_before_network` in `tests/core/test_acceptance_model_factory.py` for each live role — error names `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (FR-014, US4 scenario 4)
- [X] T038 [P] [US4] Write failing `test_factory_resolution_performs_no_network_io` in `tests/core/test_acceptance_model_factory.py` — patch HTTP/SDK clients, assert never called during `create_model_seam()` (contracts/model-seam-factory.md)
- [X] T039 [US4] Write failing `test_runner_explicit_seam_injection_bypasses_factory` in `tests/runners/test_acceptance_t2_runner.py` (or shared runner test): pass explicit `FakeModelSeam` to `run_t2_sweep(seam=...)` — factory not invoked, sweep succeeds offline (US4 scenario 5, FR-005)

### Implementation for User Story 4

- [X] T040 [US4] Complete `create_model_seam()` refresh branch in `core/model/factory.py` wiring `roles.py`, `credentials.py`, and live adapters by `MODEL_ID` (FR-005, FR-007)
- [X] T041 [US4] Verify `runners/t1.py`, `runners/t2.py`, `runners/t3.py`, `runners/autonomous/runner.py`, `runners/adversarial_gate/runner.py` remain unchanged — no provider strings, no factory calls inside runners (FR-007, plan Scope Guardrails)

**Checkpoint (US4 — factory refresh)**:

```bash
uv run pytest tests/core/test_acceptance_model_factory.py tests/core/test_acceptance_provider_credentials.py -v
```

**Expected**: Factory offline + refresh guard tests green. Refresh integration tests (US2) may still fail.

---

## Phase 6: User Story 2 — Refresh Path Writes Cache on Miss (Priority: P1)

**Goal**: Refresh mode on cache miss invokes live adapter (via injected seam or factory-resolved seam), persists entries through unchanged cache helpers, replays identically offline. Existing `@pytest.mark.refresh` FakeModelSeam tests stay green (FR-004, FR-010, US2).

**Independent Test**: With `CACHE_MODE=refresh` and mocked live seam, tier `get_or_refresh`, gate `classify_with_cache`, and autonomous `resolve_autonomous_entry` write canonical cache entries; offline replay matches; refresh-on-hit skips live call.

**Depends on**: Phase 4 (adapters), Phase 5 (factory refresh).

### Tests for User Story 2 (MANDATORY — write first, ensure FAIL) ⚠️

- [X] T042 [P] [US2] Write failing tier refresh integration test in `tests/runners/test_acceptance_cache_refresh.py`: `CacheStore.get_or_refresh` with factory-built seam (mocked SDK) on miss writes `raw_response.verdicts` at canonical key (US2 scenario 1, FR-004)
- [X] T043 [P] [US2] Write failing gate refresh test in `tests/gate/test_acceptance_gate_cache_offline.py`: extend with `test_classify_with_cache_refresh_miss_writes_classifier_result` using mocked live `classify_note` — persists `ClassifierResult` shape (US2 scenario 2)
- [X] T044 [P] [US2] Write failing autonomous refresh test in `tests/autonomous/test_acceptance_autonomous_cache_offline.py`: extend with `test_resolve_autonomous_entry_refresh_miss_writes_tool_calls` — `resolve_autonomous_entry` with `tool_registry` writes ordered `tool_calls` in cache entry (US2 scenario 3, FR-008)
- [X] T045 [US2] Write failing `test_refresh_cache_hit_replays_without_live_call` in `tests/runners/test_acceptance_cache_refresh.py` asserting cache hit in refresh mode does not invoke seam (US2 scenario 4, edge case)
- [X] T046 [P] [US2] Confirm existing `tests/runners/test_acceptance_cache_refresh.py` (`@pytest.mark.refresh`) still passes using explicit `FakeModelSeam` — refresh opt-in marker unchanged, no live keys in CI (FR-010, US2 scenario 5)

### Implementation for User Story 2

- [X] T047 [US2] Verify refresh miss paths in `core/cache/store.py`, `runners/adversarial_gate/cache.py`, and `runners/autonomous/cache.py` call `seam.adjudicate` / `seam.classify_note` without modification. If T042–T045 fail, fix only at the seam boundary (`cli/main.py`, `core/model/factory.py`, test fixtures) — **do not** modify frozen cache helpers unless constitution amendment (research R6, plan Scope Guardrails)
- [X] T048 [US2] Add CLI refresh smoke helper comment or docstring in `cli/main.py` noting refresh is operator opt-in, excluded from CI merge gate (FR-010)

**Checkpoint (US2 — refresh integration)**:

```bash
uv run pytest -m refresh -v
uv run pytest tests/runners/test_acceptance_cache_refresh.py tests/gate/test_acceptance_gate_cache_offline.py tests/autonomous/test_acceptance_autonomous_cache_offline.py -v --tb=short
```

**Expected**: Refresh tests green with mocked seams. Full offline suite still green.

---

## Phase 7: User Story 5 — Provider Credential Configuration (Priority: P2)

**Goal**: Provider-specific keys documented in `.env.example`; legacy `MODEL_API_KEY` fallback with deprecation; CI never requires secrets (FR-006, FR-009, FR-011).

**Independent Test**: `.env.example` lists required variables with empty values; credential acceptance tests pass; `uv run pytest -v` offline with no keys.

**Depends on**: Phase 2 (credentials impl). Env example can land after factory tests define expected variable names.

### Tests for User Story 5 (MANDATORY — write first, ensure FAIL) ⚠️

- [X] T049 [P] [US5] Write failing `test_env_example_documents_provider_keys_and_cache_mode` in `tests/core/test_acceptance_provider_credentials.py` parsing `.env.example` for `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MODEL_ID`, `CACHE_MODE`, and deprecated `MODEL_API_KEY` comment — no secret values (FR-009, US5 scenario 4)
- [X] T050 [P] [US5] Write failing `test_offline_pytest_never_requires_provider_keys` in `tests/core/test_acceptance_provider_credentials.py` asserting default CI subset runs without `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`MODEL_API_KEY` (US5 scenario 5, SC-001)

### Implementation for User Story 5

- [X] T051 [US5] Update `.env.example` with `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MODEL_ID`, `CACHE_MODE`, and deprecated `MODEL_API_KEY` note per contracts/model-seam-factory.md (FR-009)
- [X] T052 [US5] Align `DeprecationWarning` message in `core/model/credentials.py` to identify provider and preferred env var when legacy fallback used (FR-006, US5 scenario 3)

**Checkpoint (US5)**:

```bash
uv run pytest tests/core/test_acceptance_provider_credentials.py -v
```

**Expected**: Env example and credential policy tests green.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Opt-in live smoke, full merge gate, quickstart validation, frozen-artifact guard.

- [X] T053 [P] Implement opt-in live smoke tests in `tests/live/test_live_smoke.py` with `@pytest.mark.live` — one adjudication per supported role; document skip when keys absent (FR-010, contracts/live-adapters.md)
- [X] T054 [P] Implement and verify CI exclusion of `@pytest.mark.live`: ensure `pyproject.toml` has `addopts = "-m 'not live'"` and `.github/workflows/ci.yml` runs `uv run pytest -v` (inherits addopts). Add a skipped or absent live test and confirm it does not run in default pytest. `@pytest.mark.refresh` tests remain FakeModelSeam-only and **do** run in merge gate (FR-010, FR-011) — **addopts pre-applied in remediation; verify during polish**
- [X] T055 Run full offline merge gate: `uv run pytest -v` with zero API keys — SC-001 (FR-011)
- [X] T056 Run Feature 006 contract subset per `specs/006-live-model-seam/quickstart.md`: `uv run pytest tests/core/test_acceptance_model_factory.py tests/core/test_acceptance_live_adapters.py tests/core/test_acceptance_provider_credentials.py -v`
- [X] T057 Run prerequisite regression: `uv run pytest tests/core tests/runners tests/gate tests/autonomous tests/report tests/cli -v` — Features 001–005 unchanged (FR-011)
- [X] T058 Confirm no modifications to `export/` or committed `cache/` entries in Feature 006 diff (FR-012)
- [X] T059 Execute quickstart spot-checks from `specs/006-live-model-seam/quickstart.md`: factory offline OK, refresh-without-keys credential guard, existing refresh marker suite (SC-002 operator path documented)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS** factory and adapters
- **US1 Offline MVP (Phase 3)**: Depends on Phase 2 — **MVP checkpoint**; enables CLI factory wiring without live adapters
- **US3 Adapters (Phase 4)**: Depends on Phase 2; tests can be written in parallel with Phase 3 implementation
- **US4 Factory Refresh (Phase 5)**: Depends on Phases 2, 3, 4
- **US2 Refresh Integration (Phase 6)**: Depends on Phases 4, 5
- **US5 Env (Phase 7)**: Depends on Phase 2; `.env.example` finalization after T049
- **Polish (Phase 8)**: Depends on all story phases

### User Story Completion Order

```text
Phase 2 (roles + credentials)
    → US1 (offline factory + CLI + FakeModelSeam regression)  ← MVP
    → US3 (live adapters — mocked acceptance)
    → US4 (factory refresh + MODEL_ID selection + injection bypass)
    → US2 (refresh cache paths: adjudicate, classify_note, tool_registry)
    → US5 (.env.example + credential docs)
    → Polish
```

### Within Each User Story

1. Acceptance tests **MUST** be written and confirmed **FAILING** before implementation tasks in that story
2. Foundational types (roles, credentials) before factory refresh branch
3. Adapters before factory refresh wiring to live adapters
4. Factory refresh before end-to-end refresh integration tests
5. Do not modify `export/`, committed `cache/`, or runner orchestration

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 in parallel
- **Phase 2**: T007 + T008 (tests) in parallel; T009 + T010 (impl) in parallel after tests fail
- **Phase 3**: T012–T015 (US1 tests) in parallel
- **Phase 4**: T021–T026, T028 (US3 tests) in parallel; T029 + T031 (adapter impl) in parallel after tests fail
- **Phase 5**: T033–T038 (US4 tests) in parallel
- **Phase 6**: T042–T044, T046 (US2 tests) in parallel
- **Phase 7**: T049 + T050 in parallel
- **Phase 8**: T053 + T054 in parallel

---

## Parallel Example: User Story 3 (Adapter Tests)

```bash
# Launch all US3 failing tests together (mocked SDK, no network):
Task T021: Anthropic tier adjudicate in tests/core/test_acceptance_live_adapters.py
Task T022: Anthropic classify_note in tests/core/test_acceptance_live_adapters.py
Task T023: Anthropic tool_registry session in tests/core/test_acceptance_live_adapters.py
Task T024: Gemini tier + classify in tests/core/test_acceptance_live_adapters.py
Task T025: Gemini tool_registry session in tests/core/test_acceptance_live_adapters.py
Task T026: ModelResponseError malformed payloads in tests/core/test_acceptance_live_adapters.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (roles + credentials)
3. Complete Phase 3: US1 — offline factory + CLI + FakeModelSeam regression
4. **STOP and VALIDATE**: `uv run pytest -v` green offline, zero keys (SC-001)
5. Proceed to US3 → US4 → US2 → US5 incrementally

### Incremental Delivery

1. Setup + Foundational → role/credential contracts enforced
2. US1 → offline CI parity preserved (MVP)
3. US3 → live adapters pass mocked acceptance
4. US4 → factory selects adapter by `MODEL_ID` in refresh; missing-key errors before network
5. US2 → refresh writes cache on miss for adjudicate, classify_note, tool_registry paths
6. US5 → `.env.example` and deprecation policy documented
7. Polish → full merge gate + quickstart validation

### Test-First Discipline (Constitution Principle II)

For each phase:

```bash
# 1. Write tests → run → confirm FAIL (missing module / NotImplementedError / assertion)
uv run pytest <new-test-path> -v --tb=short

# 2. Implement → run → confirm PASS
uv run pytest <new-test-path> -v

# 3. Regression → confirm offline suite still green
uv run pytest -v
```

---

## Task Summary

| Phase | Story | Task IDs | Task count |
|-------|-------|----------|------------|
| 1 Setup | — | T001–T006 | 6 |
| 2 Foundational | — | T007–T011 | 5 |
| 3 Offline default | US1 | T012–T020 | 9 |
| 4 Live adapters | US3 | T021–T032 | 12 |
| 5 Factory refresh | US4 | T033–T041 | 9 |
| 6 Refresh integration | US2 | T042–T048 | 7 |
| 7 Credentials & env | US5 | T049–T052 | 4 |
| 8 Polish | — | T053–T059 | 7 |
| **Total** | | **T001–T059** | **59** |

### Task count per user story

| Story | Priority | Tasks |
|-------|----------|-------|
| US1 — Offline default unchanged | P1 | 9 (T012–T020) |
| US2 — Refresh path writes cache | P1 | 7 (T042–T048) |
| US3 — Provider adapters | P1 | 12 (T021–T032) |
| US4 — Factory via configuration | P2 | 9 (T033–T041) |
| US5 — Credential configuration | P2 | 4 (T049–T052) |
| Setup + Foundational + Polish | — | 18 (T001–T011, T053–T059) |

### Parallel opportunities

18 tasks marked **[P]** across setup, foundational tests, all user-story test tranches, adapter implementation, and polish.

### Independent test criteria (per story)

| Story | Independent test |
|-------|------------------|
| US1 | Default env, `uv run pytest -v`, zero keys — factory returns `FakeModelSeam`, CLI unchanged offline behavior |
| US2 | `CACHE_MODE=refresh` + mocked seam — cache miss writes entry; hit replays; existing `@pytest.mark.refresh` FakeModelSeam tests green |
| US3 | Mocked SDK tests for adjudicate, classify_note, tool_registry on both providers — no network |
| US4 | Factory offline/refresh resolution tests; missing-key and unknown-role errors before network; runner injection bypasses factory |
| US5 | `.env.example` variable lint; offline pytest requires no provider keys |

### Suggested MVP scope

**User Story 1 only** (Phases 1–3): Setup, roles/credentials foundation, offline `create_model_seam` + CLI wiring + FakeModelSeam regression. Delivers SC-001 (offline CI parity) before any live adapter or refresh integration work.

### Format validation

All 59 tasks use checklist format `- [X] [TaskID] [P?] [Story?] Description with file path`.

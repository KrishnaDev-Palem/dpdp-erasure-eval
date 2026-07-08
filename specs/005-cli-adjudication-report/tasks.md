# Tasks: CLI and Adjudication Report

**Input**: Design documents from `/specs/005-cli-adjudication-report/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, quickstart.md, research.md

**Tests**: Acceptance tests are MANDATORY per constitution Principle II. Every phase lists failing acceptance tests before implementation tasks.

**Organization**: Bootstrap → Foundational (adjudication types + Wilson wrapping) → User stories by spec priority → Quickstart validation → Polish

**Branch**: `005-cli-adjudication-report`

**Retroactive note**: Implementation may already exist on this branch. Bootstrap tasks still define the contract-first sequence; implementation tasks say **implement or align with contract** so an agent can verify, gap-fill, or refactor without assuming a greenfield tree.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US5) for story-phase tasks only
- FR/SC references trace tasks to spec requirements

## Path Conventions

- Report layer: `report/` at repository root (extends Feature 003 gate modules; no edits to `report/wilson.py` math)
- CLI: `cli/` at repository root; console script `dpdp-eval` in `pyproject.toml`
- Acceptance tests: `tests/report/` and `tests/cli/` mirroring report and CLI modules
- Runners (Feature 002/003/004, reference only — do not modify): `runners/t1.py`–`t3.py`, `runners/autonomous/`, `runners/adversarial_gate/`
- Core (Feature 001, unchanged): `core/`
- Committed cache and export: `cache/`, `export/` (read-only; no content edits)

---

## Phase 1: Bootstrap (Report/CLI Layout & Failing Acceptance Suite)

**Purpose**: Scaffold `report/` adjunct modules, `cli/`, and test harnesses; write the **full** acceptance suite so it fails for missing report/CLI behavior (not setup errors) before any adjudication builder or CLI dispatch code lands.

**Goal (US4)**: Acceptance suite defines done before implementation (FR-015, FR-016, SC-001).

**Independent Test**: `uv run pytest tests/report tests/cli -v` on a clean clone — all Feature 005 tests fail with import or `NotImplementedError`/assertion failures attributable to missing `report/adjudication_*.py` or `cli/main.py` behavior, not missing export/core fixtures.

**Explicit SC-003 rule**: Hand-calculated Wilson parity assertions for adjudication rates MUST be written in Phase 1 bootstrap tasks (T005–T006), **not** added after implementation lands.

### Bootstrap Tasks

- [X] T001 Create or verify `report/` package skeleton with `report/__init__.py` per plan.md project structure; gate modules (`wilson.py`, `types.py`, `adversarial_tables.py`, `format_gate.py`) remain unchanged from Feature 003 (FR-001, FR-020)
- [X] T002 [P] Create or verify `cli/` package skeleton with `cli/__init__.py` and `cli/__main__.py` (`python -m cli`) per plan.md project structure (FR-008)
- [X] T003 [P] Create or align `tests/report/conftest.py` with shared fixtures: repo root, `export/` path, `cache/` root, `FakeModelSeam`, `CACHE_MODE=offline` default, `hand_calculate_wilson_interval` helper, `make_hand_crafted_adjudication_scoring`, `make_tier_sweep_result`, `make_zero_denominator_adjudication_scoring`, and `WILSON_TOLERANCE=1e-9` for SC-003 parity (FR-015, SC-003, SC-004)
- [X] T004 [P] Create or align `tests/cli/` harness: repo-root subprocess helper, offline env autouse fixture (`CACHE_MODE=offline`, no `MODEL_API_KEY`), and shared JSON key sets in `tests/cli/test_acceptance_cli.py` (FR-016)
- [X] T005 [P] [US4] Write failing `tests/report/test_acceptance_adjudication_report.py::test_wilson_bounds_match_hand_calculated_adjudication_fixture` asserting `report/wilson.py` bounds match independent hand calculation within `1e-9` — **SC-003 MUST live here in bootstrap, not post-implementation** (FR-003, SC-003)
- [X] T006 [P] [US4] Write failing `test_tier_report_rates_match_scoring_numerators` and `test_tier_report_wilson_intervals_match_hand_calculated` in `tests/report/test_acceptance_adjudication_report.py` for built-report rate fidelity and Wilson parity on all three standalone rates (FR-004, SC-003, SC-004)
- [X] T007 [P] [US4] Write failing zero-denominator tests in `tests/report/test_acceptance_adjudication_report.py`: (a) `test_zero_denominator_rates_have_null_value_and_interval` — built report JSON/`model_dump` has `rate.value` and `interval` both `null` for all three standalone rates; (b) `test_zero_denominator_human_stdout_shows_null` — `format_adjudication_report(report)` human lines for `Over-erasure`, `Over-retention`, and `Mis-escalation` each contain the literal `null` (FR-005, SC-007)
- [X] T008 [P] [US1] Write failing `test_tier_report_includes_confusion_matrix_and_five_sample_rollups` in `tests/report/test_acceptance_adjudication_report.py` asserting confusion matrix passthrough, exactly five rollups (indices 0–4), and variance passthrough unchanged (FR-002, US1 scenarios 2–4)
- [X] T009 [P] [US4] Write failing `test_tier_report_no_blended_accuracy` in `tests/report/test_acceptance_adjudication_report.py` asserting prohibited fields (`accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`) absent from serialized output (FR-006, SC-006)
- [X] T010 [P] [US2] Write failing `test_cross_tier_comparison_includes_all_four_runners` and `test_cross_tier_rates_match_embedded_scoring` in `tests/report/test_acceptance_adjudication_report.py` asserting four rows (t1, t2, t3, autonomous), sample-consistent metrics, and rate numerator fidelity (FR-007, SC-005)
- [X] T011 [P] [US2] Write failing cross-tier `sample_index` consistency test in `tests/report/test_acceptance_adjudication_report.py` asserting `build_cross_tier_comparison(..., sample_index=N)` uses sample N from all four sweeps (FR-007, US2 scenario 2)
- [X] T012 [P] [US3] Write failing parametrized `test_adjudication_subcommand_exits_zero_and_emits_json_keys` for `t1`, `t2`, `t3`, `autonomous` in `tests/cli/test_acceptance_cli.py` asserting offline exit 0 and required adjudication JSON keys per contracts/cli.md (FR-009, FR-012, FR-013, SC-002)
- [X] T013 [P] [US3] Write failing `test_adversarial_gate_subcommand_exits_zero_and_emits_json_keys` in `tests/cli/test_acceptance_cli.py` asserting gate JSON keys (`detection`, `false_alarm`, `per_family`, `sample_index`) via existing Feature 003 builders — not reimplemented (FR-011, SC-002)
- [X] T014 [P] [US3] Write failing human stdout tests in `tests/cli/test_acceptance_cli.py`: (a) `test_cli_adjudication_human_stdout_includes_required_sections` — presence of `Adjudication report`, `Over-erasure`, `Over-retention`, `Mis-escalation`, `Confusion matrix`, `Cross-sample variance`; (b) `test_cli_adjudication_human_stdout_section_order` — `stdout.index()` proves strict order: title (`Adjudication report`) → primary rates header (`Primary rates (Wilson 95% CI)`) → `Over-erasure` → `Over-retention` → `Mis-escalation` → confusion header (`Confusion matrix`) → variance header (`Cross-sample variance`); five sample rollups MUST NOT appear in stdout; (c) gate headers (`Adversarial gate report`, `Overall rates`, `Detection`, `False-alarm`) (FR-010, FR-011)
- [X] T015 [P] [US3] Write failing reader-facing vocabulary test in `tests/cli/test_acceptance_cli.py` asserting human title uses evaluation names (`request-only`, `records-augmented`, `rule-augmented`, `autonomous retrieval`) not bare developer ids (`t1`, `t2`, …) per FR-019 (FR-019)
- [X] T016 [P] [US3] Write failing `test_cli_output_writes_json_file` in `tests/cli/test_acceptance_cli.py` asserting `--output PATH` writes JSON while stdout stays human-readable without `--json`; add combined `--json --output` parity test (FR-012)
- [X] T017 [P] [US3] Write failing `test_cli_sample_index_flag` and invalid `--sample-index 9` argparse rejection test in `tests/cli/test_acceptance_cli.py` (FR-012, spec edge case)
- [X] T044 [P] [US3] Write failing `test_cli_export_dir_and_cache_root_override` in `tests/cli/test_acceptance_cli.py`: (a) `dpdp-eval t1 --cache-root <empty_tmp>` exits non-zero with cache-miss or cache-path error (proves custom cache root is honored, not default); (b) `dpdp-eval t1 --export-dir <invalid_tmp>` exits non-zero with export/provenance error (proves custom export dir is honored); (c) `dpdp-eval t1 --export-dir <repo_export> --cache-root <repo_cache>` exits 0 — sanity that explicit valid paths match default behavior (FR-012, US3 scenario 7)
- [X] T018 [P] [US4] Write failing config-discipline test in `tests/cli/test_acceptance_cli.py` asserting `MODEL_ID` and `CACHE_MODE` from environment appear in report metadata (`model_id`, `cache_mode`) — not hardcoded literals (FR-014, US4 scenario 5)
- [X] T019 [P] [US3] Write failing `--output` non-writable parent directory error test in `tests/cli/test_acceptance_cli.py` asserting clear path-named error and non-zero exit (spec edge case, contracts/cli.md)
- [X] T020 [P] [US3] Write failing deterministic replay test in `tests/cli/test_acceptance_cli.py` asserting identical JSON from two consecutive offline runs of the same subcommand (SC-009)
- [X] T021 Verify Features 001–004 prerequisites: `uv run pytest tests/core tests/runners tests/gate tests/autonomous -v` passes on branch `005-cli-adjudication-report`

**Checkpoint (Bootstrap — tests must fail for the right reason)**:

```bash
uv run pytest tests/report tests/cli -v --tb=short
```

**Expected**: All `tests/report/` and `tests/cli/` tests fail due to missing adjudication report modules, CLI dispatch, or contract gaps; `tests/core/`, `tests/runners/`, `tests/gate/`, and `tests/autonomous/` green. No network or API key required.

---

## Phase 2: Foundational — Adjudication Types & Wilson Wrapping Helpers

**Purpose**: Implement adjudication Pydantic types and shared `_wrap_rate` / metrics helpers so Wilson wrapping and zero-denominator rules are available before builders and formatters land.

**Goal**: Frozen adjudication types and Wilson wrapping consuming `report/wilson.py` only (FR-001, FR-003, FR-005).

**Independent Test**: Types import and `_wrap_rate` unit behavior pass; full report and CLI acceptance tests still fail until Phases 3–5.

**Depends on**: Phase 1 complete (failing acceptance suite + conftest + CLI harness).

### Tests (already written in Phase 1 — confirm still failing until implementation)

> Tests T005–T020 and T044 MUST remain red until T022–T024 land. Do not implement `build_tier_adjudication_report` or CLI dispatch in this phase.

### Implementation for Foundational Layer

- [X] T022 [P] Implement or align adjudication Pydantic models in `report/adjudication_types.py`: `AdjudicationMetricsTable`, `SampleMetricsSummary`, `TierAdjudicationReportTables`, `CrossTierMetricRow`, `CrossTierComparisonTable` per data-model.md and contracts/adjudication-report.md; validators reject prohibited fields (FR-001, FR-006)
- [X] T023 [P] Implement or align `_wrap_rate`, `_metrics_from_scoring`, and `_sample_summary` Wilson wrapping helpers in `report/adjudication_tables.py` using `report/wilson.py` only; zero denominator yields `interval: null` (FR-003, FR-005)
- [X] T024 Confirm `report/wilson.py` and `report/types.py` (`RateWithCI`, `WilsonInterval`) remain unchanged from Feature 003 — no Wilson imports in `core/scoring` (FR-003, FR-020)

**Checkpoint (Foundational — types and wrap helpers only)**:

```bash
uv run pytest tests/report/test_acceptance_adjudication_report.py::test_wilson_bounds_match_hand_calculated_adjudication_fixture -v
```

**Expected**: Direct Wilson parity test may pass once `wilson.py` exists; builder-level tests (T006–T011) still fail until Phase 3–4.

---

## Phase 3: User Story 1 — Adjudication Report Tables with Wilson CIs (Priority: P1) 🎯 MVP

**Goal**: `build_tier_adjudication_report` and `format_adjudication_report` consume tier/autonomous sweep results, wrap standalone rates with Wilson CIs, passthrough confusion matrix and variance, and emit human stdout per FR-010 (FR-001–FR-006, FR-010).

**Independent Test**: Feed hand-crafted `TierSweepResult` into `build_tier_adjudication_report`; verify Wilson bounds, rate fidelity, zero-denominator nulls, confusion matrix shape, five rollups, variance passthrough, and prohibited-field absence (US1 independent test, SC-003, SC-004, SC-006, SC-007).

**Depends on**: Phase 2 complete (adjudication types + wrap helpers).

### Tests (already written — T006–T009)

> Confirm report builder acceptance tests fail until T025–T027 complete.

### Implementation for User Story 1

- [X] T025 [US1] Implement or align `build_tier_adjudication_report` in `report/adjudication_tables.py` per contracts/adjudication-report.md: `primary_metrics` and `confusion_matrix` from `sample_index`; all five `sample_rollups`; `variance` passthrough; no rate re-derivation (FR-002, FR-004)
- [X] T026 [US1] Implement or align `format_adjudication_report` in `report/adjudication_tables.py` with required human sections in order (title with reader-facing tier name + sample index, primary Wilson rate rows, confusion matrix, cross-sample variance); omit five rollups from human stdout; zero-denominator human lines render literal `null` per `_format_rate_ci`; section order matches FR-010 contract headers used by T014 order test (FR-010, FR-019, SC-007)
- [X] T027 [US1] Export adjudication builders and formatters from `report/__init__.py` (FR-001)

**Checkpoint (US1 — adjudication report tables green)**:

```bash
uv run pytest tests/report/test_acceptance_adjudication_report.py -v -k "not cross_tier"
```

**Expected**: All tier-report acceptance tests pass on hand-crafted and offline T1 fixtures. Cross-tier and CLI tests may still fail.

---

## Phase 4: User Story 2 — Cross-Tier Comparison Table (Priority: P1)

**Goal**: Library-only `build_cross_tier_comparison` produces exactly four rows (t1, t2, t3, autonomous) with Wilson-augmented standalone rates at a chosen sample index; optional `format_cross_tier_comparison` for human/debug output (FR-007).

**Independent Test**: Provide four completed offline sweeps; call `build_cross_tier_comparison(..., sample_index=N)`; verify four rows, tier labels, sample-consistent metrics, and rate fidelity (US2 independent test, SC-005).

**Depends on**: Phase 3 complete (Wilson wrapping proven on single-sweep reports).

### Tests (already written — T010–T011)

> Confirm cross-tier acceptance tests fail until T028–T029 complete.

### Implementation for User Story 2

- [X] T028 [US2] Implement or align `build_cross_tier_comparison` in `report/adjudication_tables.py` per contracts/adjudication-report.md: four rows, shared `sample_index`, Wilson-wrapped standalone rates, zero-denominator nulls; **no CLI subcommand** (FR-007)
- [X] T029 [US2] Implement or align `format_cross_tier_comparison` in `report/adjudication_tables.py` for library consumers and acceptance debugging (FR-007)

**Checkpoint (US2 — cross-tier comparison green)**:

```bash
uv run pytest tests/report/test_acceptance_adjudication_report.py -v -k cross_tier
```

**Expected**: All cross-tier acceptance tests pass. CLI tests may still fail.

---

## Phase 5: User Story 3 — CLI Entrypoint for All Evaluations (Priority: P1)

**Goal**: Unified `dpdp-eval` CLI runs all five evaluations offline, builds appropriate report tables, emits human stdout or JSON, supports `--output`, `--sample-index`, `--export-dir`, and `--cache-root`; gate subcommand reuses Feature 003 formatters (FR-008–FR-014).

**Independent Test**: Run each subcommand on a clean clone with `CACHE_MODE=offline` and no `MODEL_API_KEY`; verify exit 0, JSON keys, human sections, `--output` JSON file, `--sample-index`, config discipline, and gate formatter reuse (US3 independent test, SC-002, SC-009).

**Depends on**: Phase 3 complete (adjudication report builders); gate path consumes existing Feature 003 modules unchanged.

### Tests (already written — T012–T020)

> Confirm CLI acceptance tests fail until T030–T034 complete.

### Implementation for User Story 3

- [X] T030 [P] [US3] Implement or align `cli/main.py` argparse subparsers for `t1`, `t2`, `t3`, `autonomous`, `adversarial-gate` with `_add_common_args` (`--json`, `--output`, `--sample-index`, `--export-dir`, `--cache-root`) per contracts/cli.md (FR-008, FR-009, FR-012)
- [X] T031 [US3] Implement or align `_run_adjudication_command` and `_emit_report` in `cli/main.py`: runner dispatch → `build_tier_adjudication_report` → human or JSON emit; `--output` always writes JSON regardless of `--json`; pass `export_dir` and `cache_root` from parsed args to tier/autonomous runners (gate: `cache_root` at minimum) without hardcoded defaults when flags are set (FR-009, FR-010, FR-012)
- [X] T032 [US3] Implement or align `_run_gate_command` in `cli/main.py` wiring `run_adversarial_gate_sweep` → `build_gate_report` → `format_gate_report` without duplicating gate layout (FR-011)
- [X] T033 [US3] Fix `--output` help text and add non-writable parent directory validation with clear path-named error in `cli/main.py` per contracts/cli.md and research R8 (FR-012)
- [X] T034 [US3] Register or verify `dpdp-eval = cli.main:main` console script in `pyproject.toml` (FR-008)

**Checkpoint (US3 — CLI dispatch green)**:

```bash
uv run pytest tests/cli/test_acceptance_cli.py -v
uv run dpdp-eval t1
uv run dpdp-eval adversarial-gate --json
```

**Expected**: All CLI acceptance tests pass offline. Full merge gate green.

---

## Phase 6: User Story 5 — Validate CLI and Reports via Quickstart Guide (Priority: P3)

**Goal**: Human-readable path reproduces green offline CLI runs and merge-gate pytest mirroring CI (FR-017, SC-008).

**Independent Test**: Follow `specs/005-cli-adjudication-report/quickstart.md` on a clean clone without API key; all five subcommands and merge gate pass (US5 independent test).

**Depends on**: Phases 3–5 complete.

### Validation for User Story 5

- [X] T035 [US5] Execute quickstart setup and full acceptance suite steps from `specs/005-cli-adjudication-report/quickstart.md` on a clean clone without API key (FR-017, SC-008)
- [X] T036 [P] [US5] Run quickstart spot-check commands: all five `dpdp-eval` subcommands offline, `--output` JSON-without-`--json`, `--sample-index 2`, Wilson parity spot-check, cross-tier library test, and prerequisite suites per quickstart.md sections

**Checkpoint (US5 — quickstart path green)**:

```bash
uv run pytest tests/report tests/cli -v
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Matches CI merge-gate expectations; no API key; under 10 minutes on a standard dev machine (SC-008).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full merge gate, vocabulary discipline, frozen-interface audit, README cross-links, ruff-clean.

**Depends on**: Phase 6 complete.

- [X] T037 Run full offline merge gate and confirm SC-001: `uv run pytest tests/report tests/cli -v` all green with `CACHE_MODE=offline` and no `MODEL_API_KEY` (SC-001, SC-010, FR-013)
- [X] T038 [P] Audit CLI and report modules for vocabulary discipline: reader-facing evaluation names in human stdout, developer ids in JSON/cache fields; no retired scaffolding terms in `cli/main.py` and `report/adjudication_tables.py` (FR-019)
- [X] T039 Confirm no blended accuracy or prohibited fields in adjudication or gate JSON across all five subcommands (FR-006, SC-006)
- [X] T040 Confirm no edits to `core/`, tier runners, autonomous runner, gate runner, or committed `export/` — integration layer only (FR-020)
- [X] T041 [P] Add README cross-links to `dpdp-eval` CLI usage and `specs/005-cli-adjudication-report/quickstart.md` in repository `README.md`
- [X] T042 Confirm deterministic replay: re-running each CLI subcommand twice in offline mode yields identical report output (SC-009)
- [X] T043 Run `uv run ruff check .` and `uv run ruff format --check .` — ruff-clean across report, CLI, and test modules

**Final Checkpoint**:

```bash
uv run pytest tests/core tests/runners tests/gate tests/autonomous tests/report tests/cli -v
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Full feature definition of done — SC-001 through SC-010 satisfied offline.

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 Bootstrap (US4 failing tests — SC-003 Wilson parity in T005–T006)
    ↓
Phase 2 Foundational (adjudication types + Wilson wrap — BLOCKS all story work)
    ↓
Phase 3 US1 Adjudication report tables (MVP)
    ↓
Phase 4 US2 Cross-tier comparison (library-only)
    ↓
Phase 5 US3 CLI dispatch + pyproject console script
    ↓
Phase 6 US5 Quickstart validation
    ↓
Phase 7 Polish
```

### User Story Dependencies

| Story | Priority | Depends On | Delivers |
|-------|----------|------------|----------|
| US4 | P2 | Phase 1 only | Failing acceptance suite before implementation (T005–T020, T044) |
| US1 | P1 | Phase 2 types + wrap | Adjudication report tables + human formatter (T025–T027) |
| US2 | P1 | Phase 3 US1 green | Cross-tier comparison library (T028–T029) |
| US3 | P1 | Phase 3 US1 green | `dpdp-eval` CLI for all five evaluations (T030–T034) |
| US5 | P3 | Phases 3–5 | Quickstart reproducibility (T035–T036) |

### Critical Sequencing Rules

1. **Test-first (Principle II)**: T005–T020 and T044 (all acceptance tests) MUST complete before T022–T034 (report/CLI implementation).
2. **SC-003 at bootstrap**: Hand-calculated Wilson parity for adjudication rates MUST be written in T005–T006 (Phase 1), **not** added after `build_tier_adjudication_report` lands.
3. **Types before builders**: T022–T023 MUST complete before T025 `build_tier_adjudication_report`.
4. **Single-sweep before cross-tier**: T025 MUST complete before T028 `build_cross_tier_comparison`.
5. **Report before CLI**: T025–T026 MUST complete before T031 adjudication CLI dispatch.
6. **Gate reuse only**: T032 MUST call existing `build_gate_report` / `format_gate_report` — no duplicate gate Wilson or layout code in `cli/`.
7. **No out-of-scope work**: No runner orchestration edits, `core/scoring` changes, Wilson logic outside `report/wilson.py`, cross-tier CLI subcommand, combined multi-runner CLI, or committed `export/` edits.
8. **Retroactive execution**: When files already exist, implementation tasks verify contract compliance and close gaps (vocabulary, config-discipline test, `--output` help/errors) rather than rewrite from scratch.

### FR/SC Traceability Matrix

| Requirement | Tasks |
|-------------|-------|
| FR-001 (adjudication report module) | T001, T022, T025, T027 |
| FR-002 (`build_tier_adjudication_report` shape) | T008, T025 |
| FR-003 (Wilson in `report/wilson.py` only) | T005, T023, T024 |
| FR-004 (consume scoring numerators only) | T006, T025 |
| FR-005 (zero-denominator nulls) | T007, T023 |
| FR-006 (prohibited fields absent) | T009, T022, T039 |
| FR-007 (cross-tier library-only) | T010, T011, T028, T029 |
| FR-008 (`dpdp-eval` console script) | T002, T034 |
| FR-009 (five CLI subcommands) | T012, T030, T031, T032 |
| FR-010 (adjudication human stdout sections) | T014, T026, T031 |
| FR-011 (gate formatter reuse) | T013, T032 |
| FR-012 (CLI flags semantics) | T016, T017, T044, T030, T031, T033 |
| FR-013 (offline CI merge gate) | T021, T037 |
| FR-014 (env MODEL_ID, CACHE_MODE) | T018, T031 |
| FR-015 (report acceptance suite) | T003, T005–T011 |
| FR-016 (CLI acceptance suite) | T004, T012–T020, T044 |
| FR-017 (quickstart guide) | T035, T036 |
| FR-018 (feature branch only) | All tasks on `005-cli-adjudication-report` |
| FR-019 (vocabulary discipline) | T015, T026, T038 |
| FR-020 (no runner/core/export edits) | T001, T024, T040 |
| FR-021 (contracts synced with spec) | T025, T030 (reference contracts/adjudication-report.md, contracts/cli.md) |
| SC-001 (offline merge gate green) | T021, T037 |
| SC-002 (five CLI subcommands exit 0) | T012, T013, T035 |
| SC-003 (Wilson bounds match fixtures) | T005, T006 |
| SC-004 (rate numerator/denominator fidelity) | T006, T025 |
| SC-005 (four-row cross-tier table) | T010, T011, T028 |
| SC-006 (no blended accuracy fields) | T009, T039 |
| SC-007 (zero-denominator null serialization) | T007, T023, T026 |
| SC-008 (quickstart under 10 min) | T035 |
| SC-009 (deterministic CLI replay) | T020, T042 |
| SC-010 (CI pytest without secrets) | T037, T043 |

---

## Parallel Execution Examples

### Phase 1 Bootstrap (after T001–T002)

```bash
# Parallel: conftest + all acceptance test groups + CLI harness
T003 tests/report/conftest.py
T004 tests/cli/test_acceptance_cli.py harness
T005 test_wilson_bounds_match_hand_calculated_adjudication_fixture
T006 test_tier_report_rates + wilson_intervals
T007 test_zero_denominator_rates_have_null_value_and_interval
T008 test_tier_report_includes_confusion_matrix_and_five_sample_rollups
T009 test_tier_report_no_blended_accuracy
T010 test_cross_tier_comparison_includes_all_four_runners
T011 cross-tier sample_index consistency test
T012 test_adjudication_subcommand_exits_zero_and_emits_json_keys
T013 test_adversarial_gate_subcommand_exits_zero_and_emits_json_keys
T014 human stdout section tests
T015 reader-facing vocabulary test
T016 test_cli_output_writes_json_file
T017 test_cli_sample_index_flag + invalid index
T044 test_cli_export_dir_and_cache_root_override
T018 config-discipline test
T019 --output non-writable path test
T020 deterministic replay test
```

### Phase 2 Foundational (after tests red)

```bash
# Parallel: adjudication types + wrap helpers
T022 report/adjudication_types.py
T023 report/adjudication_tables.py (_wrap_rate helpers)
# Then sequential: T024 verify wilson.py / types.py unchanged
```

### Phase 3 US1 (after foundational green)

```bash
# Sequential: builder then formatter (same file)
T025 report/adjudication_tables.py build_tier_adjudication_report
T026 report/adjudication_tables.py format_adjudication_report
T027 report/__init__.py exports
```

### Phase 5 US3 (after US1 report green)

```bash
# Parallel: argparse skeleton + gate dispatch wiring
T030 cli/main.py subparsers
T032 cli/main.py _run_gate_command
# Then sequential: T031 adjudication dispatch + T033 --output fixes
# Then: T034 pyproject.toml console script
```

---

## Implementation Strategy

### MVP First (User Story 1 — adjudication report tables)

1. Complete Phase 1: Bootstrap — all failing tests + conftest + CLI harness (**SC-003 Wilson parity in T005–T006**)
2. Complete Phase 2: Foundational — adjudication types + Wilson wrap helpers
3. Complete Phase 3: US1 — `build_tier_adjudication_report` + `format_adjudication_report` tests green
4. **STOP and VALIDATE**: `uv run pytest tests/report/test_acceptance_adjudication_report.py -v -k "not cross_tier"`
5. Continue with US2 cross-tier, US3 CLI, US5 quickstart, and polish

### Incremental Delivery

1. Bootstrap + Foundational → Wilson wrapping and types proven
2. US1 → adjudication report tables (**MVP checkpoint**)
3. US2 → cross-tier comparison library
4. US3 → `dpdp-eval` CLI for all evaluations
5. US5 + Polish → quickstart on-ramp and full merge gate

### Parallel Team Strategy

With multiple developers after Phase 2:

- Developer A: Phase 3 US1 (`build_tier_adjudication_report` + human formatter)
- Developer B: Phase 4 US2 (`build_cross_tier_comparison` — can start once T025 scoring wrap shape is stable)
- Developer C: Phase 5 US3 CLI skeleton (`cli/main.py` argparse) while A finishes formatter vocabulary (T026)

After Phase 3, Developer A wires CLI adjudication dispatch (T031) while Developer B completes cross-tier formatter (T029).

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same batch
- US4 acceptance-suite-before-implementation is satisfied by Phase 1 tasks T005–T020 and T044 preceding all implementation (T022–T034)
- **SC-003 bootstrap rule**: Wilson hand-calculated parity MUST NOT be deferred to post-implementation polish — it belongs in T005–T006
- Extend `report/` additively beside Feature 003 gate modules; do not modify `core/`, tier runners, autonomous runner, gate runner, or `export/` (FR-020)
- Cross-tier comparison is library-only — no `compare-tiers` CLI subcommand in v1 (FR-007)
- Refresh path (`CACHE_MODE=refresh`) remains available via runners but is not CI-gated (FR-013)
- Total tasks: **44** (Bootstrap 22, Foundational 3, US1 3, US2 2, US3 5, US5 2, Polish 7)

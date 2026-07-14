# Tasks: Live Role Cache Seeding

**Input**: Design documents from `/specs/007-live-role-cache-seed/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/committed-cache-tree.md, contracts/offline-replay-tests.md, quickstart.md

**Tests**: MANDATORY per Constitution Principle II — the four offline replay acceptance
test files land on the branch and FAIL (cache miss) **before** any cache entries are
committed. Sequencing below binds the plan's Test-First Sequencing table.

**Organization**: Tasks are grouped by user story. Ordering follows the operator flow:
setup → replay test scaffolding (US3) → operator refresh execution (US2) → commit cache
artifacts + offline verification (US1) → README on-ramp (US4) → polish.

**⚠ CI exclusion**: Tasks marked **[NOT-CI / OPERATOR]** require provider credentials and
network. They run only on the operator's local machine and are **excluded from the CI
merge gate** (FR-011). Default CI stays offline, keyless (`uv run pytest -v` with
`addopts = -m "not live"` unchanged).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (committed cache), US2 (operator refresh), US3 (CI replay tests), US4 (README)
- Include exact file paths in descriptions

## Path Conventions

Single-package layout at repository root (unchanged from Features 001–006): committed
data under `cache/`, tests under `tests/{runners,gate,autonomous,cli}/`, docs at
`README.md` and `specs/007-live-role-cache-seed/`.

---

## Phase 1: Setup (Baseline Verification)

**Purpose**: Prove the pre-feature state is green and cold so the test-first cycle fails
for the right reason.

- [ ] T001 Verify clean offline baseline on branch `007-live-role-cache-seed`: `uv sync`, then `uv run pytest -v` with `CACHE_MODE=offline` and `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`MODEL_API_KEY` unset — all Features 001–006 suites green (FR-013 / SC-003 baseline)
- [ ] T002 [P] Pin parity targets by counting committed primary cache: `cache/primary/t2/` = 10 entries (2 subjects), `cache/primary/adversarial_gate/` = 450 entries (90 case dirs × 5 samples), `cache/primary/autonomous/` = 10 entries — record counts against research.md R1 (FR-003/004/005)
- [ ] T003 [P] Confirm cold live-role namespaces: `cache/claude-sonnet-5/` and `cache/gemini-3.5-flash/` do not exist on the branch, so the new replay tests in Phase 3 will fail with `CacheMissError` for the right reason (Constitution II)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None required — Feature 007 adds no runtime code. The factory
(`create_model_seam`), live adapters, credential resolution, cache helpers, runners, and
CLI are consumed exactly as shipped in Feature 006 (FR-006; plan Scope Guardrails).

*No tasks. Phase 1 completion is the only gate before user story work begins.*

**Checkpoint**: Baseline green, namespaces cold — test scaffolding can begin.

---

## Phase 3: User Story 3 — CI-Gated Offline Replay Acceptance for Live Roles (Priority: P1) 🎯 Test scaffolding first

**Goal**: Land the four keyless offline replay acceptance test files per
[contracts/offline-replay-tests.md](./contracts/offline-replay-tests.md). They MUST fail
on the cold namespaces before any cache entries are committed (Constitution II).

**Independent Test**: `uv run pytest tests/runners/test_acceptance_live_role_t2_replay.py tests/gate/test_acceptance_live_role_gate_replay.py tests/autonomous/test_acceptance_live_role_autonomous_replay.py tests/cli/test_acceptance_cli_live_roles.py -v` with zero keys — fails with cache-miss errors now; passes after Phase 5 commits the cache.

### Tests for User Story 3 (MANDATORY — write first, ensure FAIL) ⚠️

- [ ] T004 [P] [US3] Write `tests/runners/test_acceptance_live_role_t2_replay.py`: `run_t2_sweep` with `SweepConfig(model_id="claude-sonnet-5", cache_mode="offline")` and a call-recording `FakeModelSeam`; assert sweep completes (no `CacheMissError`), `adjudicate_calls == []`, coverage = 2 subjects × samples 0–4, two-run determinism of serialized verdicts/rates, result `model_id == "claude-sonnet-5"` and `cache_mode == "offline"` (contract assertions 1–5)
- [ ] T005 [P] [US3] Write `tests/gate/test_acceptance_live_role_gate_replay.py`: `run_adversarial_gate_sweep` with `GateSweepConfig(model_id="gemini-3.5-flash")` and call-recording seam; assert completion, `classify_calls == []`, `slice_case_count == 90` with all 5 sample rollups, two-run outcome determinism, result metadata (pattern from `tests/gate/test_acceptance_gate_cache_offline.py`)
- [ ] T006 [P] [US3] Write `tests/autonomous/test_acceptance_live_role_autonomous_replay.py`: autonomous sweep with `model_id="claude-sonnet-5"` offline; assert completion, zero seam calls, 2 subjects × samples 0–4, two-run determinism including tool-call traces, every session's `tool_calls` items validate as `ToolCallTrace` with contiguous `sequence`, and at least one session per subject has a non-empty trace (contract assertion 6; research R6)
- [ ] T007 [P] [US3] Write `tests/cli/test_acceptance_cli_live_roles.py`: subprocess `dpdp-eval t2 --json` and `dpdp-eval autonomous --json` (env `MODEL_ID=claude-sonnet-5`) and `dpdp-eval adversarial-gate --json` (env `MODEL_ID=gemini-3.5-flash`), all with `CACHE_MODE=offline` and `ANTHROPIC_API_KEY`/`GEMINI_API_KEY`/`MODEL_API_KEY` stripped from the child env; assert exit 0, payload `model_id` echoes the role, `cache_mode == "offline"`, and byte-identical stdout JSON on repeat (pattern from `tests/cli/test_acceptance_cli.py`)
- [ ] T008 [US3] Run the four new test files and confirm each FAILS for the right reason — runner suites raise `CacheMissError` naming runner/case/sample; CLI suite exits nonzero on cache miss — then commit the test files to the branch **before any cache entries land** (Constitution II; plan Test-First Sequencing rows 1–4)

**Checkpoint**: Red acceptance suite committed — operator seeding may begin.

---

## Phase 4: User Story 2 — Operator Refresh Workflow for Live-Role Cache Generation (Priority: P1)

**Goal**: Execute the quickstart Part 2 runbook to seed all three live-role namespaces
via Feature 006 refresh infrastructure unchanged (FR-006). Refresh order per plan:
T2 (claude-sonnet-5) → adversarial gate (gemini-3.5-flash) → autonomous (claude-sonnet-5).

**Independent Test**: Follow [quickstart.md](./quickstart.md) Part 2 with valid
credentials; verify entries land only under the correct live-role namespaces; switch to
offline mode and confirm replay parity (US2 acceptance scenarios 1–5).

**⚠ EXCLUDED FROM CI MERGE GATE**: Every task in this phase is **[NOT-CI / OPERATOR]** —
local machine only, provider billing required, never run in GitHub Actions (FR-011).

### Implementation for User Story 2

- [ ] T009 [US2] **[NOT-CI / OPERATOR]** Refresh preflight per quickstart.md Part 2 prerequisites: copy `.env.example` to `.env`, set billing-enabled `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`, acknowledge cost envelope ≈$3–6 total / hard ceiling <$10 / ≤560 provider requests (research R3; Constitution VIII)
- [ ] T010 [US2] **[NOT-CI / OPERATOR]** Execute quickstart Step 1 — T2 refresh with Claude Sonnet 5: `CACHE_MODE=refresh`, `MODEL_ID=claude-sonnet-5`, `uv run dpdp-eval t2 --json --output t2-refresh.json`; verify exactly 10 new files under `cache/claude-sonnet-5/t2/` (2 subjects × samples 0–4; ~10 adjudication calls, ≤$0.20)
- [ ] T011 [US2] **[NOT-CI / OPERATOR]** Execute quickstart Step 2 — adversarial-gate refresh with Gemini 3.5 Flash: `CACHE_MODE=refresh`, `MODEL_ID=gemini-3.5-flash`, `uv run dpdp-eval adversarial-gate --json --output gate-refresh.json`; verify 450 new files under `cache/gemini-3.5-flash/adversarial_gate/` (90 case dirs × 5 samples; ~450 classification calls, ≤$2.75 — the expensive sweep; interrupted runs are resumed by re-running, hits replay free)
- [ ] T012 [US2] **[NOT-CI / OPERATOR]** Execute quickstart Step 3 — autonomous refresh with Claude Sonnet 5: `CACHE_MODE=refresh`, `MODEL_ID=claude-sonnet-5`, `uv run dpdp-eval autonomous --json --output autonomous-refresh.json`; verify exactly 10 new files under `cache/claude-sonnet-5/autonomous/`, each carrying `tool_calls` traces where tool use occurred (10 sessions × ≤10 rounds, ≤$2.60)
- [ ] T013 [US2] **[NOT-CI / OPERATOR]** Execute quickstart Step 4 — refresh↔offline parity: re-run each sweep with `CACHE_MODE=offline` and the same `MODEL_ID`, diff refresh vs offline JSON output for byte-equal payloads (research R4 guarantee 1); then run `uv run pytest -v` offline with all provider keys removed from the environment; do **not** stage `*-refresh.json` / `*-offline.json` scratch reports
- [ ] T014 [US2] Reconcile the runbook with observed refresh behavior in `specs/007-live-role-cache-seed/quickstart.md` (actual call counts, costs, anomalies) — doc-only edits; if refresh exposed a Feature 006 contract violation, stop and surface per research.md R9 bugfix boundary (Constitution X) rather than patching adapters silently

**Checkpoint**: All three namespaces fully seeded locally, parity verified — commit preparation can begin.

---

## Phase 5: User Story 1 — Committed Live-Role Cache for Thesis Evaluation (Priority: P1)

**Goal**: Commit the 470-entry live-role cache tree per
[contracts/committed-cache-tree.md](./contracts/committed-cache-tree.md) and prove
offline replay flips the Phase 3 acceptance suite red → green.

**Independent Test**: Clean clone, no API keys, `CACHE_MODE=offline`; run T2,
adversarial-gate, and autonomous sweeps with the live `MODEL_ID`s — each exits 0 with
deterministic results from committed cache (US1 acceptance scenarios 1–5).

### Implementation for User Story 1

- [ ] T015 [US1] Validate the working-tree cache against `specs/007-live-role-cache-seed/contracts/committed-cache-tree.md`: entry counts exactly 10 (`cache/claude-sonnet-5/t2/`) + 450 (`cache/gemini-3.5-flash/adversarial_gate/`) + 10 (`cache/claude-sonnet-5/autonomous/`); no forbidden namespaces (no `claude-sonnet-5/{t1,t3,adversarial_gate}/`, no `gemini-3.5-flash/{t1,t2,t3,autonomous}/`); path segments agree with embedded `model_id`/`runner_id`/`case_id`/`prompt_hash`/`sample_index`; verdicts ∈ {erase, retain, escalate}, gate outcomes ∈ {clean, adversarial}; autonomous `tool_calls` validate as `ToolCallTrace` with any empty trace confirmed as a genuine no-tool-use session (FR-014; research R6)
- [ ] T016 [US1] Execute quickstart Step 5 — protected-path invariant: `git diff --stat main -- cache/primary export` MUST print nothing; `git status --short` shows only `cache/claude-sonnet-5/`, `cache/gemini-3.5-flash/`, tests, and docs (FR-002; research R7; Constitution III)
- [ ] T017 [US1] Commit the 470 cache entry JSON files to branch `007-live-role-cache-seed` — operator-driven commit with human diff review deferred to PR (FR-015); agent MUST NOT merge to `main` (Constitution VII)
- [ ] T018 [US1] Offline verification — run the four Phase 3 replay test files with `CACHE_MODE=offline` and zero provider keys: all PASS against committed cache (red → green flip completing the Constitution II cycle; plan Test-First Sequencing rows 1–4 "Then deliver" column)

**Checkpoint**: Committed cache replays offline; acceptance suite green. US1/US2/US3 functionally complete.

---

## Phase 6: User Story 4 — README On-Ramp for Live-Role Evaluations (Priority: P2)

**Goal**: Thesis readers discover the live-role replay path from the README without
hunting through feature docs.

**Independent Test**: Follow README instructions with `MODEL_ID=claude-sonnet-5` or
`gemini-3.5-flash` and `CACHE_MODE=offline`; evaluation commands complete from committed
cache without API keys (US4 acceptance scenarios 1–2).

### Implementation for User Story 4

- [ ] T019 [US4] Add a live-role evaluation subsection to `README.md` near "Running evaluations": reader-facing names (records-augmented, adversarial-gate, autonomous retrieval) mapped to `MODEL_ID` values and `CACHE_MODE=offline` commands, offline/no-key default stated, link to `specs/007-live-role-cache-seed/quickstart.md` for refresh and verification (FR-012; research R8); verify vocabulary — no "pillar"/"condition", internal tier ids only in code paths (Constitution V)

**Checkpoint**: All four user stories complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final regression, lint, timing, and sign-off artifacts.

- [ ] T020 Full merge-gate regression: `uv run pytest -v` with `CACHE_MODE=offline` and all provider keys unset — 100% pass including Features 001–006 regression suites and the four new replay files (SC-002; SC-003; FR-013)
- [ ] T021 [P] Lint and format gate on new/changed files: `uv run ruff check .` and `uv run ruff format --check .` (CI parity)
- [ ] T022 [P] SC-004 timing validation: on a clean clone after `uv sync`, run the three CLI replay paths (`dpdp-eval t2`, `dpdp-eval adversarial-gate`, `dpdp-eval autonomous` with their live `MODEL_ID`s, offline) and confirm all complete in under 5 minutes total
- [ ] T023 Complete the SC-002 completion checklist in `specs/007-live-role-cache-seed/quickstart.md` (all nine items checked) and update item statuses in `specs/007-live-role-cache-seed/checklists/cache-seeding.md` (SC-001; SC-005)
- [ ] T024 Verify zero-runtime-change invariant before PR: `pyproject.toml`, `uv.lock`, `.github/workflows/`, `core/`, `runners/`, `cli/`, and `export/` show no diff vs `main` except as allowed by plan Project Structure (cache namespaces, 4 test files, `README.md`, `specs/007-live-role-cache-seed/` docs); open PR for human review and merge (Constitution VII — no agent merge)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Empty — Phase 1 is the only gate
- **US3 tests (Phase 3)**: After Phase 1. T004–T007 in parallel; T008 after all four
- **US2 refresh (Phase 4)**: After T008 (tests MUST be committed red first). T009 before T010–T012; T010 → T011 → T012 per runbook order; T013 after T012; T014 after T013. **Entire phase excluded from CI.**
- **US1 commit (Phase 5)**: After Phase 4. T015 → T016 → T017 → T018 strictly sequential (validate → invariant → commit → verify)
- **US4 README (Phase 6)**: After Phase 5 (documents the now-working replay path). T019 independent of Phase 7 lint
- **Polish (Phase 7)**: After Phases 5–6. T021/T022 parallel; T023 after T020; T024 last

### User Story Dependencies

- **US3 (tests)** has no upstream story dependency but intentionally lands first — its red state gates US2
- **US2 (refresh)** depends on US3's committed failing tests (test-first) and Feature 006 (external, complete)
- **US1 (committed cache)** depends on US2's seeded namespaces — the cache artifacts are US2's output, committed and verified in US1
- **US4 (README)** depends on US1 so documented commands actually work

### Parallel Opportunities

- **Phase 1**: T002 and T003 in parallel after T001
- **Phase 3**: T004, T005, T006, T007 — four different test files, fully parallel
- **Phase 4**: T010–T012 touch disjoint namespaces and could run concurrently with both keys set, but the runbook order (T2 → gate → autonomous) is recommended for a single operator tracking spend
- **Phase 7**: T021 and T022 in parallel

## Parallel Example: User Story 3

```bash
# Launch all four replay test files together (different files, no dependencies):
Task: "Write tests/runners/test_acceptance_live_role_t2_replay.py"
Task: "Write tests/gate/test_acceptance_live_role_gate_replay.py"
Task: "Write tests/autonomous/test_acceptance_live_role_autonomous_replay.py"
Task: "Write tests/cli/test_acceptance_cli_live_roles.py"

# Then confirm they all fail for the right reason before any seeding:
uv run pytest tests/runners/test_acceptance_live_role_t2_replay.py \
  tests/gate/test_acceptance_live_role_gate_replay.py \
  tests/autonomous/test_acceptance_live_role_autonomous_replay.py \
  tests/cli/test_acceptance_cli_live_roles.py -v   # expect CacheMissError failures
```

---

## Implementation Strategy

### MVP First (US3 + US2 + US1 as one delivery spine)

This feature's stories form a single delivery spine rather than independent increments:
the failing tests (US3) define done, the operator refresh (US2) produces the artifacts,
and the commit + verification (US1) satisfies both. The MVP is Phases 1–5: committed
470-entry cache with a green keyless replay suite. US4 (README) and Polish complete the
on-ramp and sign-off.

### Incremental Delivery

1. Phase 1 → baseline green, namespaces cold
2. Phase 3 → red acceptance suite committed (reviewable checkpoint)
3. Phase 4 → namespaces seeded locally, parity verified (operator-only; not in CI)
4. Phase 5 → cache committed, suite green (MVP — SC-001 satisfied)
5. Phase 6 → README on-ramp (SC-004 path documented)
6. Phase 7 → regression, lint, timing, checklist sign-off → PR for human merge

### Operator/CI Boundary (FR-011)

| Phase | Runs in CI merge gate? |
|-------|------------------------|
| 1, 3, 5, 6, 7 | Yes — offline, zero provider keys |
| 4 (T009–T014) | **No — operator-local only, requires `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` and billing** |

---

## Notes

- No runtime code tasks exist by design — any adapter change beyond the research R9
  bugfix boundary requires re-planning, not a side-edit (Constitution X)
- Cache entries are frozen once merged (Constitution III): corrections are additive
  re-seeds in a new feature, never in-place edits
- Commit after each task or logical group; never stage `.env`, keys, or scratch
  `*-refresh.json` / `*-offline.json` reports
- Definition of done: SC-001–SC-005 — 470 committed entries at full parity, merge gate
  green offline with zero keys, `cache/primary/` and `export/` untouched, README +
  quickstart on-ramp complete

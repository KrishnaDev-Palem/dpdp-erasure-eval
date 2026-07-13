# Research: 007-live-role-cache-seed

**Date**: 2026-07-12
**Feature**: Live role cache seeding (Claude Sonnet 5 + Gemini 3.5 Flash committed replay cache)

All decisions consume Feature 006 infrastructure unchanged (FR-006). No adapter, factory,
cache-helper, or runner code changes are planned; this feature adds committed cache data,
acceptance tests, and operator documentation.

## R1 — Authoritative coverage matrices (resolves checklist CHK003, CHK004, CHK005)

**Decision**: Pin coverage to the committed `cache/primary/` matrix, verified by direct count
on 2026-07-12:

| Namespace | Cases | Samples | Entries | Source of case list |
|-----------|-------|---------|---------|---------------------|
| `cache/claude-sonnet-5/t2/` | 2 scored subjects (`floor-inside-subject`, `mixed-fanout-subject`) | 0–4 | **10** | Frozen export subjects (Feature 002) |
| `cache/gemini-3.5-flash/adversarial_gate/` | **90** extended-slice cases (46 adversarial + 44 benign) | 0–4 | **450** | Feature 003 committed slice (`load_extended_slice`) |
| `cache/claude-sonnet-5/autonomous/` | 2 subjects (same as T2) | 0–4 | **10** | Feature 004 autonomous runner |

The spec's "~450" resolves to exactly **450**: `Get-ChildItem cache/primary/adversarial_gate
-Recurse -Filter *.json` counts 450 files across 90 case directories. T2 and autonomous each
count 10 committed primary entries across 2 case directories. No other live-role/runner
combinations are created (no `gemini-3.5-flash/t2/`, no `claude-sonnet-5/adversarial_gate/`,
no T1/T3 live namespaces).

**Rationale**: FR-003/004/005 require full parity with primary seeding; counting the committed
tree is authoritative versus restating spec assumptions.

**Alternatives considered**: Representative gate subset — rejected by clarification session
2026-07-12 (full parity required); deriving counts from fixture YAML — rejected, committed
cache is the binding artifact CI replays.

## R2 — Refresh execution shape (one CLI sweep per runner path)

**Decision**: Each runner path is refreshed by a **single CLI invocation** under
`CACHE_MODE=refresh` with the bound `MODEL_ID`:

| Runner path | Command | Role | Live calls on cold namespace |
|-------------|---------|------|------------------------------|
| T2 tier sweep | `uv run dpdp-eval t2` | `claude-sonnet-5` | 10 adjudications |
| Adversarial gate | `uv run dpdp-eval adversarial-gate` | `gemini-3.5-flash` | 450 classifications |
| Autonomous | `uv run dpdp-eval autonomous` | `claude-sonnet-5` | 10 adjudications × tool rounds (bounded ≤10 rounds each by `LiveAdapterConfig.max_tool_rounds`) |

Sweep runners already iterate all subjects/cases × sample indices 0–4 per invocation
(`runners/spine.py`, `runners/adversarial_gate/runner.py`, `runners/autonomous/runner.py`),
and cache helpers call the live seam only on miss. Re-running after an interruption is
therefore idempotent: hits replay, only misses trigger live calls.

**Rationale**: Reuses Feature 005 CLI and Feature 006 factory exactly as shipped; no new
seeding scripts. Interrupted-refresh recovery (spec edge case) falls out of miss-only
refresh semantics.

**Alternatives considered**: Dedicated seeding script — rejected, duplicates sweep
orchestration and adds surface the constitution's cost/scope discipline discourages;
per-sample CLI loops — unnecessary, sweeps cover all samples in one run.

## R3 — Cost estimate for full seeding (Constitution VIII; resolves CHK022, CHK023)

**Decision**: Document both API-call counts and a monetary ceiling in quickstart.

Pricing verified 2026-07-12 (Constitution Principle VI):

- **Claude Sonnet 5**: $2 / MTok input, $10 / MTok output (introductory through 2026-08-31;
  $3/$15 thereafter) — https://platform.claude.com/docs/en/about-claude/pricing and
  https://www.anthropic.com/news/claude-sonnet-5
- **Gemini 3.5 Flash**: $1.50 / MTok input, $9.00 / MTok output (thinking tokens billed as
  output) — https://ai.google.dev/gemini-api/docs/pricing

Volume estimate (upper bounds):

| Sweep | Calls | Est. input/call | Est. output/call | Est. cost |
|-------|-------|-----------------|------------------|-----------|
| T2 (Sonnet 5) | 10 | ≤4K tok (context bundle JSON) | ≤1K tok | ≤ $0.20 |
| Gate (Gemini 3.5 Flash) | 450 | ≤1K tok (note text + instructions) | ≤0.5K tok (incl. low thinking) | ≤ $2.75 |
| Autonomous (Sonnet 5) | 10 sessions, ≤10 rounds each → ≤100 requests | ≤8K tok/request (growing transcript) | ≤1K tok/request | ≤ $2.60 |
| **Total full seed** | ≤560 provider requests | | | **≈ $3–6, hard ceiling < $10** |

The autonomous bound is stated as **≤10 adjudication sessions, each capped at 10 provider
rounds** — the checkable form of SC-005's "≤10 adjudication calls (with tool rounds)".

**Rationale**: Well inside the tens-of-dollars constitution ceiling even at 2–3× token
estimates; the intro-pricing window (through 2026-08-31) makes seeding now cheaper.

**Alternatives considered**: Batch APIs (50% discount) — rejected, adds async plumbing for a
one-shot < $10 operation.

## R4 — Definition of "deterministic / identical results" (resolves CHK002, CHK006)

**Decision**: Two distinct guarantees, verified at different times:

1. **Refresh↔offline parity (operator-verified once, at seed time)**: immediately after
   refresh, the operator re-runs the same sweep with `CACHE_MODE=offline` and compares the
   emitted JSON report (`--json` / `--output`) for byte-equal payloads. Parity holds by
   construction — offline reads the exact entries refresh wrote — so this is a
   namespace/coverage smoke check, recorded in the quickstart SC-002 checklist.
2. **Offline replay determinism (CI-verified continuously)**: repeated offline runs against
   committed entries produce identical verdicts, classification outcomes, tool-call traces,
   and report payloads, with **zero cache misses and zero seam invocations**. This is what
   the new acceptance tests assert (exit code 0 + stable JSON + no `FakeModelSeam` calls).

CI cannot verify guarantee 1 directly (it has no keys); it verifies guarantee 2 against the
committed artifacts that guarantee 1 vouched for at review time.

**Rationale**: Keeps the merge gate keyless (Constitution IV) while making "identical results"
concrete and checkable per comparison surface.

**Alternatives considered**: Committing refresh-run report JSON for CI diffing — rejected,
duplicates cache-derived state and creates a second artifact to keep in sync.

## R5 — Acceptance test placement and mechanics (resolves CHK016, CHK020, CHK030, CHK031, CHK033)

**Decision**: New offline replay tests, all keyless and in the default merge gate:

| File | Asserts |
|------|---------|
| `tests/runners/test_acceptance_live_role_t2_replay.py` | `run_t2_sweep` with `SweepConfig(model_id="claude-sonnet-5", cache_mode="offline")` against committed `cache/`: completes, zero seam calls, verdict/rate payload deterministic across two runs |
| `tests/gate/test_acceptance_live_role_gate_replay.py` | `run_adversarial_gate_sweep` with `GateSweepConfig(model_id="gemini-3.5-flash")`: 90 cases × 5 samples resolved, zero misses/zero classify calls, outcomes deterministic |
| `tests/autonomous/test_acceptance_live_role_autonomous_replay.py` | `resolve_autonomous_entry`-backed sweep with `model_id="claude-sonnet-5"`: sessions replay with `tool_calls` traces validating against `ToolCallTrace`, zero seam calls |
| `tests/cli/test_acceptance_cli_live_roles.py` | Subprocess `dpdp-eval t2` / `autonomous` (env `MODEL_ID=claude-sonnet-5`) and `adversarial-gate` (env `MODEL_ID=gemini-3.5-flash`) with `CACHE_MODE=offline` and provider keys stripped from env: exit 0, JSON `model_id` echoes the role |

Division of responsibility (CHK020): runner-suite tests exercise in-process sweep functions
with injected config and a call-recording `FakeModelSeam` (proving zero live-path usage);
the CLI suite exercises the end-to-end factory path via environment variables only.

Zero-miss assertion mechanics: offline mode raises `CacheMissError` on any gap, so sweep
completion is itself the zero-miss proof; tests additionally assert
`fake_seam.adjudicate_calls == []` / `classify_calls == []` (pattern already used in
`tests/gate/test_acceptance_gate_cache_offline.py`).

**Rationale**: Mirrors the existing per-suite layout requested in user input
(tests/runners, tests/gate, tests/autonomous, tests/cli); keeps runner suites fast and the
CLI suite as the only subprocess layer.

**Alternatives considered**: One consolidated `tests/live_replay/` package — rejected, user
input and existing suite organization bind tests to their runner suites.

## R6 — Autonomous `tool_calls` policy (resolves CHK007, CHK008)

**Decision**: Governing contracts are Feature 004 `contracts/tool-call-trace.md` (trace
schema/ordering) and Feature 006 `contracts/live-adapters.md` (session result shape). Policy
for committed autonomous entries:

- Every entry MUST contain the `tool_calls` field (guaranteed by `write_cache`).
- Every trace item MUST validate against `ToolCallTrace` with contiguous `sequence` ordering.
- Entries where the live model used tools MUST carry the ordered non-empty trace; an
  empty trace is schema-valid but flagged in the quickstart review checklist — the operator
  MUST confirm empty-trace entries reflect genuine no-tool-use sessions before commit, since
  the autonomous evaluation's purpose is tool-mediated retrieval.
- Acceptance tests assert schema validity and replay equality for all entries and that at
  least one committed entry per subject carries a non-empty trace.

**Rationale**: Reconciles FR-005 ("traces included in each entry") with US2-AS3 ("where
tool-use occurred") without inventing a hard non-emptiness rule the model may legitimately
violate; puts the judgment call at human review per FR-015.

## R7 — Namespace isolation verification (resolves CHK010, CHK011, CHK012, CHK013)

**Decision**: Three layers, none requiring new runtime code:

1. **By construction**: cache keys embed `model_id` as the first path segment
   (`core/cache/store.py::_entry_path`); a refresh run with `MODEL_ID=claude-sonnet-5`
   cannot address `cache/primary/`. Silent fallback to another namespace or to live calls
   in offline mode does not exist in the helpers (offline miss → `CacheMissError`).
2. **Operator verification (quickstart, pre-commit)**: `git status`/`git diff --stat main --
   cache/primary export` MUST be empty; only `cache/claude-sonnet-5/` and
   `cache/gemini-3.5-flash/` may appear as additions. "Unchanged" covers modification,
   overwrite, deletion, **and addition** under the protected paths.
3. **PR review checklist (FR-015)**: reviewer verifies namespace paths, entry counts
   (10/450/10), schema fields, and empty protected-path diff.

**Rationale**: Principle III makes `cache/primary/` and `export/` frozen; enforcement via
diff-scope review matches how Features 002–004 protected the same trees.

**Alternatives considered**: A pytest asserting `cache/primary/` file counts — rejected as
brittle (future additive features legitimately grow primary) and redundant with review.

## R8 — README and vocabulary (resolves CHK034; Constitution V)

**Decision**: Extend the existing README "Running evaluations" area with a live-role
subsection using reader-facing names — records-augmented (T2), adversarial-gate,
autonomous retrieval — mapping each to its role and `MODEL_ID`, stating offline/no-key
default, and linking to `specs/007-live-role-cache-seed/quickstart.md`. The Feature 006
README section remains; 007 adds the replay-consumer path.

## R9 — Feature 006 stability boundary (resolves CHK028, CHK035, CHK036, CHK037)

**Decision**:

- Feature 006 code is consumed as-is. A "bugfix discovered during refresh" is a change that
  makes an adapter satisfy an **already-written** 006 contract clause (e.g., malformed
  request shape rejected by the provider); anything altering contract behavior, prompts, or
  cache shape requires re-planning, not a 007 side-change.
- SC-001 tension with "006 complete and stable": 006's *code seam* is complete; its SC-002
  (committed live cache at sweep cardinality) is the deliverable 007 completes. No conflict.
- Provider model ids re-verified 2026-07-12: `claude-sonnet-5` (Anthropic pricing/news pages)
  and `gemini-3.5-flash` (Google AI pricing page) both current GA ids — unchanged from 006
  research pins.
- Feature 005 CLI honoring `MODEL_ID`/`CACHE_MODE` is verified capability: runners resolve
  both via `load_model_config()` (`runners/types.py`, `runners/adversarial_gate/types.py`,
  `runners/autonomous/types.py`), and CLI constructs the seam via `create_model_seam()`
  (`cli/main.py`).

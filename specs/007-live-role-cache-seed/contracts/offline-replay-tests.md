# Offline Replay Acceptance Tests Contract

**Version**: 1.0.0
**Feature**: 007-live-role-cache-seed
**Depends on**: [committed-cache-tree.md](./committed-cache-tree.md)

All tests below run in the default merge gate (`uv run pytest -v`), with `CACHE_MODE=offline`,
**zero provider API keys, zero network**. They read the committed repository `cache/` tree
(not tmp fixtures) because the committed entries are the artifact under test.

## Test files and responsibilities

| File | Layer | Role under test |
|------|-------|-----------------|
| `tests/runners/test_acceptance_live_role_t2_replay.py` | In-process sweep (`run_t2_sweep`) | `claude-sonnet-5` |
| `tests/gate/test_acceptance_live_role_gate_replay.py` | In-process sweep (`run_adversarial_gate_sweep`) | `gemini-3.5-flash` |
| `tests/autonomous/test_acceptance_live_role_autonomous_replay.py` | In-process sweep (`run_autonomous_sweep`) | `claude-sonnet-5` |
| `tests/cli/test_acceptance_cli_live_roles.py` | Subprocess `dpdp-eval` CLI + factory + env | both |

Boundary rule: runner-suite tests inject `SweepConfig` / `GateSweepConfig` /
`AutonomousSweepConfig` with the live `model_id` and `cache_mode="offline"` plus a
call-recording `FakeModelSeam` — they prove replay never touches the seam. The CLI suite is
the only place the factory/environment path (`MODEL_ID`, `CACHE_MODE` env vars) is exercised
end-to-end.

## Required assertions — runner suites

For each sweep against the committed cache root:

1. **Completes without cache miss**: sweep returns a result (offline miss would raise
   `CacheMissError`, failing the test with the runner/case/sample named).
2. **Zero seam invocations**: injected `FakeModelSeam` records no `adjudicate`/`classify_note`
   calls (`adjudicate_calls == []` / `classify_calls == []`).
3. **Coverage cardinality**: result covers the full matrix — T2: 2 subjects × samples 0–4;
   gate: `slice_case_count == 90`, all 5 sample rollups present; autonomous: 2 subjects ×
   samples 0–4.
4. **Determinism**: running the sweep twice yields equal serialized results
   (verdicts / outcomes / rates; tool-call traces for autonomous).
5. **Result metadata**: `model_id` on the sweep result equals the live role;
   `cache_mode == "offline"`.
6. **Autonomous traces**: every replayed session's `tool_calls` items validate as
   `ToolCallTrace` with contiguous `sequence`; at least one session per subject has a
   non-empty trace.

## Required assertions — CLI suite

Subprocess invocations (pattern from `tests/cli/test_acceptance_cli.py`), with
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and `MODEL_API_KEY` removed from the child env:

| Invocation | Env | Asserts |
|------------|-----|---------|
| `dpdp-eval t2 --json` | `MODEL_ID=claude-sonnet-5`, `CACHE_MODE=offline` | exit 0; payload `model_id == "claude-sonnet-5"`, `cache_mode == "offline"`; adjudication JSON keys present |
| `dpdp-eval autonomous --json` | `MODEL_ID=claude-sonnet-5`, `CACHE_MODE=offline` | exit 0; same key checks |
| `dpdp-eval adversarial-gate --json` | `MODEL_ID=gemini-3.5-flash`, `CACHE_MODE=offline` | exit 0; gate JSON keys present |
| Determinism | repeat any one subcommand | byte-identical stdout JSON |

## Exclusions

- No new `@pytest.mark.live` or `@pytest.mark.refresh` tests are required by this feature;
  existing markers and the `addopts = "-m 'not live'"` merge-gate exclusion are unchanged
  (FR-011).
- Tests MUST NOT write to the repository `cache/` tree.

## Regression guarantee

Features 001–006 suites run unchanged in the same gate; this feature adds files only — no
edits to existing test modules except (optionally) shared fixtures in suite `conftest.py`
files, which MUST remain backward-compatible.

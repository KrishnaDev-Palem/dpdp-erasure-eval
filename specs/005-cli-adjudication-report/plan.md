# Implementation Plan: CLI and Adjudication Report

**Branch**: `005-cli-adjudication-report` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-cli-adjudication-report/spec.md`

## Summary

Deliver the cross-cutting integration layer deferred from Features 001–004: Wilson-augmented adjudication report tables (`build_tier_adjudication_report`, `build_cross_tier_comparison`) consuming `TierSweepResult` and `AutonomousSweepResult`; human and JSON formatters; and a unified `dpdp-eval` CLI with subcommands `t1`, `t2`, `t3`, `autonomous`, and `adversarial-gate`. The gate subcommand reuses existing `build_gate_report` / `format_gate_report` without reimplementation. Cross-tier comparison is library-only (no CLI subcommand in v1). Default execution replays committed cache in offline mode with no live model in CI. Acceptance suites under `tests/report/` and `tests/cli/` are written before implementation and must pass fully offline per merge gate `uv run pytest tests/report tests/cli -v`.

**Current codebase note**: Report builders, formatters, CLI dispatch, and acceptance suites already exist on the feature branch and currently pass the merge gate (16 tests). Phase 2 `tasks.md` MUST still sequence any remaining spec gaps (vocabulary in human stdout, config-discipline CLI tests, `--output` help text, output-path error handling) as failing-then-passing tasks before treating the feature complete.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Inherited from Feature 001 — `pyyaml`, `pydantic` v2; Wilson intervals via stdlib `math` in `report/wilson.py` (no new runtime deps)  
**Storage**: Filesystem — `export/` (frozen subjects, read-only), `cache/` (committed tier/autonomous/gate entries), `fixtures/adversarial_slice/` (gate corpus)  
**Testing**: `pytest`; acceptance tests under `tests/report/` and `tests/cli/`; merge gate `uv run pytest tests/report tests/cli -v`  
**Target Platform**: Linux/macOS/Windows dev; GitHub Actions CI (offline, no API key)  
**Project Type**: Library-style Python package + reporting module + CLI entrypoint + committed cache replay  
**Performance Goals**: Full report + CLI acceptance suite completes in <60s offline on a standard dev machine  
**Constraints**: No Postgres, no live agent in CI, frozen export and Features 001–004 runner/core/export modules immutable (FR-020), `CACHE_MODE=offline` default, N=5 samples only (planning §9), Wilson math only in `report/wilson.py`  
**Scale/Scope**: 5 CLI subcommands; 3 tier + 1 autonomous + 1 gate runner consumed; 4-row cross-tier comparison table; adjudication report per sweep with 5 sample rollups

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | Evidence |
|-----------|--------|----------|
| **I. Deterministic Ground Truth** | **PASS** | Report layer wraps runner scoring only; rate numerators/denominators and confusion matrix come from `AdjudicationScoringResult` unchanged; no live agent or Postgres ([001/contracts/frozen-export.md](../001-shared-core/contracts/frozen-export.md)) |
| **II. Acceptance-Spec Before Implementation** | **PASS** | Contracts in [contracts/](./contracts/); acceptance suites at `tests/report/test_acceptance_adjudication_report.py` and `tests/cli/test_acceptance_cli.py` planned and present; Phase 2 tasks sequence any remaining gaps as failing-first |
| **III. Frozen-Interface / Frozen-Export Discipline** | **PASS** | No edits to committed `export/`, tier runners, autonomous runner, gate runner, or `core/scoring`; additive `report/adjudication_*.py`, `cli/`, and tests only (FR-020) |
| **IV. Reproducibility and Offline Verification** | **PASS** | `uv` + `uv.lock`; default `CACHE_MODE=offline`; merge gate `uv run pytest tests/report tests/cli -v` without `MODEL_API_KEY`; deterministic replay verified by acceptance tests |
| **V. Vocabulary and Wording Discipline** | **PASS** (with Phase 2 follow-up) | Contracts specify reader-facing evaluation names in human stdout (FR-019); current `format_adjudication_report` uses developer tier ids — Phase 2 task to map t1→request-only etc. without changing JSON keys |
| **VI. Currency Before Communication** | **PASS** | No new statute claims; rates read from committed export scoring only |
| **VII. Git Flow and Human Merge Gate** | **PASS** | Branch `005-cli-adjudication-report`; PR + human merge; agent does not merge to `main` |
| **VIII. Dependency and Cost Discipline** | **PASS** | No database/pgvector; Wilson via stdlib; no new runtime deps; bounded matrix: 5 subcommands × N=5 samples × existing runners |
| **IX. Tracked Artifacts, Not Ephemeral Chat** | **PASS** | spec/plan/research/data-model/contracts/quickstart committed under `specs/005-cli-adjudication-report/` |
| **X. Stop and Surface Over Silent Choices** | **PASS** | Research resolves report layout, CLI dispatch, gate formatter reuse, sample_index semantics, and library-only cross-tier; no unresolved NEEDS CLARIFICATION |

*Post-design re-check (2026-07-07): **PASS** — no violations requiring Complexity Tracking.*

## Scope Guardrails (planning §9)

- **No Postgres** — filesystem export, fixtures, and cache only.
- **No live agent in CI** — default `CACHE_MODE=offline`; refresh path documented in [quickstart.md](./quickstart.md) but excluded from merge gate.
- **Bounded dependencies** — reuse Feature 001 stack; any addition beyond `pyyaml`/`pydantic` requires PR justification in Complexity Tracking.
- **Bounded cardinality** — N=5 samples per case (`sample_index` 0–4); five CLI subcommands; cross-tier comparison is four rows at one sample index, not a fifth runner.
- **No runner/core/export edits** — Features 001–004 modules remain frozen reference implementations.
- **Wilson isolation** — `report/wilson.py` only; not in `core/scoring`.
- **No cross-tier CLI subcommand** — `build_cross_tier_comparison` is library + acceptance-tested only (spec clarification 2026-07-07).

## Test-First Sequencing

Constitution Principle II requires acceptance tests before implementation. Phase 2 `tasks.md` (via `/speckit-tasks`) MUST sequence failing acceptance tests ahead of implementation — mirroring Features 003/004:

| Phase | Tests first (MUST FAIL) | Then implement |
|-------|-------------------------|----------------|
| Adjudication types | `test_acceptance_adjudication_report.py` (Wilson parity, rate fidelity, zero-denominator nulls, prohibited fields) | `report/adjudication_types.py` |
| Adjudication builders | same file (confusion matrix passthrough, five rollups, variance passthrough) | `report/adjudication_tables.py` (`build_tier_adjudication_report`) |
| Cross-tier comparison | same file (four rows, sample_index consistency, rate fidelity) | `build_cross_tier_comparison` in `adjudication_tables.py` |
| Human formatters | same file or dedicated formatter tests (section headers, rollups omitted from stdout) | `format_adjudication_report`, `format_cross_tier_comparison` |
| CLI subcommands | `test_acceptance_cli.py` (offline exit 0, JSON keys, human headers, `--output`, `--sample-index`) | `cli/main.py`, `pyproject.toml` console script |
| Gate subcommand wiring | `test_acceptance_cli.py` (gate JSON keys, `Adversarial gate report` header) | reuse `build_gate_report` / `format_gate_report` |
| Config discipline | `test_acceptance_cli.py` (assert `MODEL_ID`, `CACHE_MODE` from env reflected in report metadata) | CLI passes through runner config loading via `load_model_config()` inside runners |
| Vocabulary audit | CLI human-output tests (reader-facing tier names in title) | tier label map in `format_adjudication_report` |

**Definition of done**: acceptance tests fail for the right reason before report/CLI code lands, then pass when the feature completes. Full merge gate green offline per SC-001: `uv run pytest tests/report tests/cli -v`.

## Project Structure

### Documentation (this feature)

```text
specs/005-cli-adjudication-report/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── adjudication-report.md
│   └── cli.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
report/
├── __init__.py
├── wilson.py                 # Feature 003 (unchanged)
├── types.py                  # RateWithCI, WilsonInterval, GateReportTables (unchanged)
├── adversarial_tables.py     # build_gate_report (Feature 003, unchanged)
├── format_gate.py            # format_gate_report (Feature 003, unchanged)
├── adjudication_types.py     # NEW — TierAdjudicationReportTables, CrossTierComparisonTable, ...
└── adjudication_tables.py    # NEW — build_*, format_adjudication_report, format_cross_tier_comparison

cli/
├── __init__.py
├── __main__.py               # python -m cli
└── main.py                   # argparse subcommands, dispatch to runners + formatters

runners/
├── t1.py, t2.py, t3.py       # Feature 002 (unchanged)
├── spine.py, pairing.py, variance.py, types.py  # Feature 002 (unchanged)
├── adversarial_gate/         # Feature 003 (unchanged)
└── autonomous/               # Feature 004 (unchanged)

core/                         # Feature 001 (unchanged — no scoring or export edits)

export/                       # unchanged committed frozen export
cache/                        # unchanged committed cache (tier, autonomous, gate)

tests/
├── core/                     # Feature 001 (unchanged)
├── runners/                  # Feature 002 (unchanged)
├── gate/                     # Feature 003 (unchanged)
├── autonomous/               # Feature 004 (unchanged)
├── report/                   # NEW
│   ├── conftest.py
│   └── test_acceptance_adjudication_report.py
└── cli/                      # NEW
    └── test_acceptance_cli.py
```

**Structure Decision**: Per planning §7 integration layer, reporting formatters live in `report/` beside existing gate report modules; CLI lives in top-level `cli/` package registered as `dpdp-eval` in `pyproject.toml`. Runners orchestrate sweeps; report layer wraps Wilson CIs and formatting only; CLI wires runner → builder → formatter/JSON emit. Cross-tier comparison stays in `report/adjudication_tables.py` with no CLI surface.

## Integration Spine (design summary)

### Adjudication report path

1. **Run sweep** — tier or autonomous runner returns `TierSweepResult` / `AutonomousSweepResult`.
2. **Build tables** — `build_tier_adjudication_report(sweep, sample_index=N)` selects primary sample for `primary_metrics` and `confusion_matrix`; wraps all three standalone rates with Wilson CIs via `_wrap_rate` → `wilson_interval`; builds five `SampleMetricsSummary` rollups; passes `variance` through unchanged.
3. **Emit** — `format_adjudication_report` for human stdout (title, primary rates, confusion matrix, variance — no rollups); `model_dump(mode="json")` for `--json` stdout and `--output` file.

### Gate subcommand path

1. **Run sweep** — `run_adversarial_gate_sweep` returns `GateSweepResult`.
2. **Build tables** — `build_gate_report(scoring, sample_index=N)` from Feature 003.
3. **Emit** — `format_gate_report` for human stdout; JSON via `model_dump`.

### Cross-tier comparison (library only)

Callers with four completed sweeps invoke `build_cross_tier_comparison(t1, t2, t3, autonomous, sample_index=N)`. Optional `format_cross_tier_comparison` for human/debug output. Not exposed via CLI in v1.

## Complexity Tracking

> No constitution violations requiring justification. No new runtime dependencies.

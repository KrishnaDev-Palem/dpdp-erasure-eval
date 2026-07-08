# Research: 005-cli-adjudication-report

**Date**: 2026-07-07  
**Feature**: CLI and adjudication report (integration layer)

## R1 — Adjudication report type layout

**Decision**: Define Pydantic v2 frozen models in `report/adjudication_types.py` (`AdjudicationMetricsTable`, `SampleMetricsSummary`, `TierAdjudicationReportTables`, `CrossTierMetricRow`, `CrossTierComparisonTable`). Reuse shared `RateWithCI` and `WilsonInterval` from `report/types.py` (same as gate reporting). Build logic in `report/adjudication_tables.py`.

**Rationale**: Matches Feature 003 gate report pattern (`report/types.py` + `report/adversarial_tables.py`). Shared `RateWithCI` keeps Wilson wrapping and JSON serialization shape identical between gate and adjudication reports. Pydantic validators enforce prohibited-field absence and cross-tier row cardinality at construction time.

**Reconciliation with existing code**: Types and builders already implemented in repo; validators on `TierAdjudicationReportTables` and `CrossTierComparisonTable` scan `model_dump()` for prohibited keys. `SampleMetricsSummary` includes `total_subjects` and `scored_location_pairs` from upstream `SampleRollup` — richer than the partial contract draft but aligned with [002/contracts/sweep-result.md](../002-context-tier-sweep/contracts/sweep-result.md).

**Alternatives considered**:
- Separate `report/format_adjudication.py` module — rejected; Feature 003 colocates `format_gate_report` beside gate builders; adjudication formatters live in `adjudication_tables.py` for parity.
- Duplicate `RateWithCI` in adjudication types — rejected; violates DRY and breaks JSON schema consistency with gate output.
- Dataclasses instead of Pydantic — rejected; project standard is Pydantic v2 for report tables (Feature 003 precedent).

## R2 — CLI dispatch pattern

**Decision**: Single `cli/main.py` with `argparse` subparsers for `t1`, `t2`, `t3`, `autonomous`, `adversarial-gate`. Shared `_add_common_args()` attaches `--json`, `--output`, `--sample-index`, `--export-dir`, `--cache-root`. Dispatch dict maps subcommand name to runner callable + report builder. Console script `dpdp-eval = cli.main:main` in `pyproject.toml`; `python -m cli` via `cli/__main__.py`.

**Rationale**: Minimal dependency surface (stdlib `argparse` + `json`). One file keeps CLI thin — orchestration only, no scoring or Wilson math. Subcommand-per-evaluation matches spec FR-009 and planning §7 operator surface. Acceptance tests invoke `python -m cli` for subprocess isolation.

**Reconciliation with existing code**: Implementation matches decision. Known gaps vs spec:
- `--output` help text currently says "in addition to stdout when --json is set" — **incorrect** per clarification: `--output` always writes JSON; stdout format controlled by `--json` only (FR-012).
- `_run_adjudication_command` injects `FakeModelSeam()` directly; runners still call `load_model_config()` internally for `model_id` / `cache_mode` metadata — satisfies FR-014 at runner level; dedicated CLI config-discipline acceptance test still planned (FR-016 scenario 5).
- No validation for non-writable `--output` parent directory yet (edge case in spec).

**Alternatives considered**:
- `click` or `typer` — rejected; new dependency without justification (constitution VIII).
- One combined `run-all` subcommand — rejected; out of scope; callers run subcommands individually.
- Library-only (no CLI) — rejected; spec FR-008 requires `dpdp-eval` entrypoint.

## R3 — Reuse of gate formatters

**Decision**: Adversarial-gate CLI subcommand MUST call existing `build_gate_report` (`report/adversarial_tables.py`) and `format_gate_report` (`report/format_gate.py`). Do not duplicate gate human layout or Wilson wrapping in `cli/`.

**Rationale**: Spec FR-011 and assumption: "Gate report building and formatting from Feature 003 remain unchanged." Feature 005 wires the gate subcommand only. `_wrap_rate` pattern is duplicated between `adversarial_tables.py` and `adjudication_tables.py` at the module level (acceptable — adjudication rates differ from detection/false-alarm); human formatting is not duplicated.

**Reconciliation with existing code**: `_run_gate_command` selects `result.samples[args.sample_index].scoring`, passes to `build_gate_report`, formats with `format_gate_report`. Gate human headers match contract: `Adversarial gate report`, `Overall rates (Wilson 95% CI)`, `Detection` / `False-alarm`, optional `Per-family detection`.

**Alternatives considered**:
- Shared `_wrap_rate` in `report/types.py` — deferred; two-line helper duplication is acceptable to avoid modifying Feature 003 modules.
- Gate JSON schema fork for CLI — rejected; same `GateReportTables` model.

## R4 — `sample_index` semantics

**Decision**:

| Surface | Behavior |
|---------|----------|
| `build_tier_adjudication_report(..., sample_index=N)` | `primary_sample_index=N`; `primary_metrics` and `confusion_matrix` from `sweep.samples[N]`; `sample_rollups` always lists all five samples 0–4 |
| `build_cross_tier_comparison(..., sample_index=N)` | All four rows use metrics from sample N of each sweep |
| CLI `--sample-index N` | Passed to builders; `choices=[0,1,2,3,4]` at argparse level |
| Human stdout | Primary rates and confusion matrix reflect N; five rollups **omitted** from human text (JSON/`--output` only) |
| Gate subcommand | `--sample-index` selects which gate sample's `scoring` feeds `build_gate_report` |

**Rationale**: Spec clarification session 2026-07-07 and FR-010. Primary sample is the thesis-facing slice; rollups support JSON/automation without cluttering human stdout. Argparse `choices` rejects out-of-range before runner invocation (edge case).

**Reconciliation with existing code**: `build_tier_adjudication_report` validates `0 <= sample_index < len(sweep.samples)`. `format_adjudication_report` title includes `(sample {primary_sample_index})` and does not print rollups. CLI tests verify `primary_sample_index == 2` with `--sample-index 2`.

**Alternatives considered**:
- Omit rollups from JSON when non-primary sample selected — rejected; spec requires all five rollups always in structured output.
- Separate `--primary-sample` vs `--rollup-range` — rejected; YAGNI; single flag suffices.

## R5 — Cross-tier comparison CLI exposure

**Decision**: **Library-only in v1.** Expose `build_cross_tier_comparison` and optional `format_cross_tier_comparison` in `report/adjudication_tables.py`. Acceptance-tested in `tests/report/test_acceptance_adjudication_report.py`. **No** `compare-tiers` or combined CLI subcommand.

**Rationale**: Spec clarification 2026-07-07: "Library-only via `build_cross_tier_comparison`; acceptance-tested; no CLI subcommand in v1." Cross-tier requires four completed sweeps; CLI runs one evaluation per invocation. Future automation or thesis scripts call the library after individual CLI runs.

**Reconciliation with existing code**: No CLI reference to `build_cross_tier_comparison`. Report acceptance tests run four offline sweeps and assert four-row comparison. `format_cross_tier_comparison` exists for library consumers but is not CLI-wired.

**Alternatives considered**:
- `dpdp-eval compare-tiers` running all four sweeps — rejected; spec out of scope; combinatorial cache/time cost without v1 requirement.
- Embed cross-tier rows inside each tier report JSON — rejected; separate table type keeps tier reports isomorphic to single-sweep results.

## R6 — Wilson interval reuse

**Decision**: All adjudication Wilson intervals call `report/wilson.py:wilson_interval(rate, confidence_level=0.95)`. When `denominator == 0`, `_wrap_rate` sets `RateWithCI.interval = None` and preserves core `Rate.value = None`.

**Rationale**: Spec FR-003/FR-005; same parameters as gate report (Feature 003 research R3). Acceptance tests use independent hand-calculated Wilson in `tests/report/conftest.py` with tolerance `1e-9`.

**Reconciliation**: Implemented; `test_wilson_bounds_match_hand_calculated_adjudication_fixture` passes. No Wilson imports in `core/scoring`.

## R7 — Human stdout section layout (adjudication)

**Decision**: `format_adjudication_report` emits sections in order:

1. Title line: `Adjudication report — {reader-facing tier name} (sample N)` — **Phase 2**: map tier ids to reader-facing names per FR-019
2. Metadata line: model id, cache mode
3. `Primary rates (Wilson 95% CI):` with labels `Over-erasure`, `Over-retention`, `Mis-escalation`
4. `Confusion matrix (predicted × actual):` table
5. `Cross-sample variance:` with constancy lines per metric

Five `sample_rollups` excluded from human stdout; present in JSON/`--output`.

**Rationale**: Spec FR-010 and clarification session. Matches gate report pattern of labeled Wilson rows.

**Reconciliation with existing code**: Section order and labels match spec except title uses developer tier id (`t1`) instead of reader-facing name (`request-only`) — documented gap for Phase 2 vocabulary task.

## R8 — `--output` vs `--json` semantics

**Decision**:

| Flag | Effect |
|------|--------|
| (default) | Human-readable text to stdout |
| `--json` | JSON to stdout |
| `--output PATH` | Always writes JSON to PATH (regardless of `--json`) |
| Both `--json` and `--output` | JSON to stdout **and** JSON file |

**Rationale**: Spec clarification 2026-07-07 answer A. Keeps automation (`--output`) stable while human operators get readable stdout by default.

**Reconciliation**: `_emit_report` implements this correctly. CLI help string for `--output` needs correction in Phase 2.

## R9 — Merge gate command

**Decision**: Feature CI merge gate: `uv run pytest tests/report tests/cli -v`. Documented in spec SC-001, FR-013, FR-017, and [quickstart.md](./quickstart.md).

**Rationale**: Spec clarification; isolates integration-layer tests without re-running full harness on every Feature 005 PR (though quickstart recommends prerequisite suites for local validation).

**Reconciliation**: All 16 merge-gate tests currently pass offline on the feature branch.

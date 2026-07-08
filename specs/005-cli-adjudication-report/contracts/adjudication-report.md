# Adjudication Report Contract

**Version**: 1.1.0  
**Feature**: 005-cli-adjudication-report  
**Authority**: Spec FR-001–FR-007, FR-010–FR-012, FR-021; planning §7 integration layer; inherits scoring contract prohibitions

## Purpose

Define the reporting layer output for tier and autonomous adjudication evaluation:
Wilson confidence intervals on over-erasure, over-retention, and mis-escalation rates;
per-lane confusion matrix; N=5 sample rollups; cross-sample variance summary; and
cross-tier comparison tables. Consumes `TierSweepResult` and `AutonomousSweepResult`
from runners — does not recompute rate numerators/denominators or confusion matrix cells.

CLI dispatch, flags, and subcommand behavior are specified in [cli.md](./cli.md).

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Adjudication scoring shape | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |
| Tier sweep result | [002/contracts/sweep-result.md](../../002-context-tier-sweep/contracts/sweep-result.md) |
| Autonomous runner output | [004/contracts/autonomous-runner.md](../../004-autonomous-retrieval-eval/contracts/autonomous-runner.md) |
| Gate report pattern | [003/contracts/gate-report.md](../../003-adversarial-gate/contracts/gate-report.md) |
| Wilson interval | `report/wilson.py` |
| Data model | [../data-model.md](../data-model.md) |

Wilson computation MUST NOT live in `core/scoring` (FR-003).

## Module layout

```text
report/
├── adjudication_types.py   # TierAdjudicationReportTables, CrossTierComparisonTable, ...
├── adjudication_tables.py  # build_tier_adjudication_report, build_cross_tier_comparison,
│                           # format_adjudication_report, format_cross_tier_comparison
├── adversarial_tables.py   # build_gate_report (Feature 003, unchanged)
├── format_gate.py          # format_gate_report (Feature 003, unchanged)
├── wilson.py               # shared Wilson interval (unchanged)
└── types.py                # RateWithCI, WilsonInterval, GateReportTables (shared with gate)
```

## Wilson confidence interval

Same parameters as gate report ([003/contracts/gate-report.md](../../003-adversarial-gate/contracts/gate-report.md)):

| Parameter | Default |
|-----------|---------|
| `confidence_level` | `0.95` |
| `z` | `1.96` |

### Undefined interval rule

When `denominator == 0`:

- `Rate.value` is `null` per scoring contract.
- `WilsonInterval.lower` and `upper` MUST be `null`.
- `RateWithCI.interval` MUST be `null`.

Applies to all three standalone adjudication rates in primary metrics, sample rollups, and cross-tier rows.

### Acceptance tolerance

Hand-calculated fixtures in `tests/report/test_acceptance_adjudication_report.py` MUST match computed bounds within `1e-9` absolute tolerance on representative rational fixtures.

## Primary sample index

| Context | Default | Override |
|---------|---------|----------|
| `build_tier_adjudication_report` | `sample_index=0` | Selects primary metrics + confusion matrix |
| `build_cross_tier_comparison` | `sample_index=0` | All four rows use sample N |
| CLI adjudication subcommands | `--sample-index 0` | See [cli.md](./cli.md) |

All five sample rollups are **always** included in `sample_rollups` regardless of primary sample selection.

## TierAdjudicationReportTables

Produced by `build_tier_adjudication_report(sweep, *, sample_index=0)`.

| Field | Type | Description |
|-------|------|-------------|
| `tier` | string | `t1`, `t2`, `t3`, or `autonomous` |
| `runner_id` | string | Cache namespace |
| `model_id` | string | Model role from runner config |
| `cache_mode` | string | `offline` or `refresh` |
| `export_agent_sha` | string | Provenance from manifest |
| `primary_sample_index` | int | Selected sample for primary metrics |
| `primary_metrics` | AdjudicationMetricsTable | Wilson-augmented standalone rates |
| `confusion_matrix` | dict | From primary sample scoring (unchanged passthrough) |
| `sample_rollups` | list[SampleMetricsSummary] | Length exactly 5 (indices 0–4) |
| `variance` | VarianceSummary | From sweep result (unchanged passthrough) |

### AdjudicationMetricsTable

| Field | Type |
|-------|------|
| `over_erasure` | RateWithCI |
| `over_retention` | RateWithCI |
| `mis_escalation` | RateWithCI |

### SampleMetricsSummary

| Field | Type |
|-------|------|
| `sample_index` | int |
| `total_subjects` | int |
| `scored_location_pairs` | int |
| `metrics` | AdjudicationMetricsTable |

## CrossTierComparisonTable

Produced by `build_cross_tier_comparison(t1, t2, t3, autonomous, *, sample_index=0)`.

**Library-only in v1** — no CLI subcommand exposes this table (spec clarification 2026-07-07).

| Field | Type | Description |
|-------|------|-------------|
| `sample_index` | int | Sample used for all four rows |
| `rows` | list[CrossTierMetricRow] | Exactly four rows: t1, t2, t3, autonomous |

Each `CrossTierMetricRow` carries `tier`, `over_erasure`, `over_retention`, and `mis_escalation` as separate `RateWithCI` fields — no blended accuracy.

Optional human rendering: `format_cross_tier_comparison(table) -> str`.

## Human-readable output: format_adjudication_report

When CLI runs without `--json`, adjudication subcommands emit human stdout via `format_adjudication_report`. Required sections **in order** (FR-010):

1. **Title** — includes evaluation identity and primary sample index (reader-facing tier names per FR-019 in human title)
2. **Primary rates (Wilson 95% CI)** — rows labeled `Over-erasure`, `Over-retention`, `Mis-escalation`
3. **Confusion matrix (predicted × actual)** — table from primary sample
4. **Cross-sample variance** — constancy summary from passthrough `variance`

**Excluded from human stdout**: five `sample_rollups` (JSON and `--output` only).

## Prohibited fields

MUST NOT include in adjudication types or serialized JSON: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.

## Gate subcommand (by reference)

The `adversarial-gate` CLI subcommand emits `GateReportTables` via existing `build_gate_report` and `format_gate_report` — not reimplemented in adjudication modules. Human stdout MUST preserve Feature 003 section headers:

- `Adversarial gate report`
- `Overall rates (Wilson 95% CI)` with `Detection` and `False-alarm` rows
- Optional `Per-family detection` when families are present

See [cli.md](./cli.md) for flag semantics.

## Merge gate

Feature continuous integration merge gate:

```bash
uv run pytest tests/report tests/cli -v
```

Runs fully offline with no `MODEL_API_KEY` (FR-013, SC-001).

## Non-goals

- Per-subject variance tables
- Edits to runner orchestration, frozen export, or `core/scoring`
- Blended accuracy reporting
- CLI subcommand for cross-tier comparison (`compare-tiers` or equivalent)
- Combined CLI subcommand running all tiers and autonomous in one invocation

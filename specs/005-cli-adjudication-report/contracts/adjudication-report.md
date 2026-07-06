# Adjudication Report Contract

**Version**: 1.0.0  
**Feature**: 005-cli-adjudication-report  
**Authority**: Planning §7 integration layer; inherits scoring contract prohibitions

## Purpose

Define the reporting layer output for tier and autonomous adjudication evaluation:
Wilson confidence intervals on over-erasure, over-retention, and mis-escalation rates;
per-lane confusion matrix; N=5 sample rollups; cross-sample variance summary; and
cross-tier comparison tables. Consumes `TierSweepResult` and `AutonomousSweepResult`
from runners — does not recompute rate numerators/denominators.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Adjudication scoring shape | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |
| Tier sweep result | [002/contracts/sweep-result.md](../../002-context-tier-sweep/contracts/sweep-result.md) |
| Autonomous runner output | [004/contracts/autonomous-runner.md](../../004-autonomous-retrieval-eval/contracts/autonomous-runner.md) |
| Gate report pattern | [003/contracts/gate-report.md](../../003-adversarial-gate/contracts/gate-report.md) |
| Wilson interval | `report/wilson.py` |

Wilson computation MUST NOT live in `core/scoring`.

## Module layout

```text
report/
├── adjudication_types.py   # TierAdjudicationReportTables, CrossTierComparisonTable, ...
├── adjudication_tables.py  # build_tier_adjudication_report, build_cross_tier_comparison
├── format_gate.py          # format_gate_report (gate human-readable output)
├── wilson.py               # shared Wilson interval (unchanged)
└── types.py                # RateWithCI, WilsonInterval (shared with gate)
```

## Primary sample index

Cross-tier comparison and CLI primary rate tables use **`sample_index=0` by default**.
The `--sample-index N` CLI flag selects which of 0..4 drives the primary metrics and
confusion matrix. All five sample rollups are always included in `sample_rollups`.

## TierAdjudicationReportTables

Produced by `build_tier_adjudication_report(sweep, *, sample_index=0)`.

| Field | Type | Description |
|-------|------|-------------|
| `tier` | string | `t1`, `t2`, `t3`, or `autonomous` |
| `runner_id` | string | Cache namespace |
| `model_id` | string | Model role |
| `cache_mode` | string | `offline` or `refresh` |
| `export_agent_sha` | string | Provenance from manifest |
| `primary_sample_index` | int | Selected sample for primary metrics |
| `primary_metrics` | AdjudicationMetricsTable | Wilson-augmented standalone rates |
| `confusion_matrix` | dict | From primary sample scoring (unchanged) |
| `sample_rollups` | list[SampleMetricsSummary] | Length 5 |
| `variance` | VarianceSummary | From sweep result (unchanged) |

### AdjudicationMetricsTable

| Field | Type |
|-------|------|
| `over_erasure` | RateWithCI |
| `over_retention` | RateWithCI |
| `mis_escalation` | RateWithCI |

### Undefined interval rule

When `denominator == 0`: `Rate.value`, Wilson bounds, and `RateWithCI.interval` MUST
be `null` (same as gate report).

## CrossTierComparisonTable

Produced by `build_cross_tier_comparison(t1, t2, t3, autonomous, *, sample_index=0)`.

| Field | Type | Description |
|-------|------|-------------|
| `sample_index` | int | Sample used for all four rows |
| `rows` | list[CrossTierMetricRow] | Exactly four rows: t1, t2, t3, autonomous |

Each `CrossTierMetricRow` carries `over_erasure`, `over_retention`, and `mis_escalation`
as separate `RateWithCI` fields — no blended accuracy.

## Prohibited fields

MUST NOT include: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.

## CLI

Console script `dpdp-eval` dispatches subcommands `t1`, `t2`, `t3`, `autonomous`, and
`adversarial-gate`. Adjudication subcommands emit `TierAdjudicationReportTables`; gate
subcommand emits `GateReportTables` via existing `build_gate_report`.

Default seam: `FakeModelSeam` (offline replay). Respects `MODEL_ID` and `CACHE_MODE`.

## Non-goals

- Per-subject variance tables
- Edits to runner orchestration or frozen export
- Blended accuracy reporting

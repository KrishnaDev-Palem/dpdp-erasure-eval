# CLI Contract

**Version**: 1.0.0  
**Feature**: 005-cli-adjudication-report  
**Authority**: Spec FR-008–FR-014, FR-019; [adjudication-report.md](./adjudication-report.md)

## Purpose

Define the operator surface for the DPDP erasure evaluation harness: console script `dpdp-eval`, subcommands, flags, output semantics, and error behavior. The CLI orchestrates existing runners and report builders — it does not implement scoring or Wilson math.

## Entrypoint

| Mechanism | Target |
|-----------|--------|
| Console script | `dpdp-eval` → `cli.main:main` (`pyproject.toml`) |
| Module invocation | `python -m cli` → same `main()` |

## Subcommands

| Subcommand | Runner | Report builder | Output type |
|------------|--------|----------------|-------------|
| `t1` | `run_t1_sweep` | `build_tier_adjudication_report` | `TierAdjudicationReportTables` |
| `t2` | `run_t2_sweep` | `build_tier_adjudication_report` | `TierAdjudicationReportTables` |
| `t3` | `run_t3_sweep` | `build_tier_adjudication_report` | `TierAdjudicationReportTables` |
| `autonomous` | `run_autonomous_sweep` | `build_tier_adjudication_report` | `TierAdjudicationReportTables` |
| `adversarial-gate` | `run_adversarial_gate_sweep` | `build_gate_report` | `GateReportTables` |

**Not exposed in v1**: cross-tier comparison (`build_cross_tier_comparison`), combined multi-runner sweeps.

### Subcommand help text (reader-facing)

Parser help strings SHOULD use descriptive evaluation names where shown to operators:

| Subcommand | Help description |
|------------|------------------|
| `t1` | Run request-only (T1) tier sweep |
| `t2` | Run records-augmented (T2) tier sweep |
| `t3` | Run rule-augmented (T3) tier sweep |
| `autonomous` | Run autonomous retrieval evaluation sweep |
| `adversarial-gate` | Run adversarial-gate evaluation sweep |

Developer-facing identifiers (`t1`, `t2`, etc.) remain subcommand names and JSON `tier` / `runner_id` fields.

## Common flags

All subcommands accept:

| Flag | Type | Default | Semantics |
|------|------|---------|-----------|
| `--json` | boolean | false | When set, stdout is JSON. When unset, stdout is human-readable via the appropriate formatter |
| `--output PATH` | path | none | **Always writes JSON** report content to PATH, regardless of `--json`. May be combined with `--json` (JSON to both stdout and file) |
| `--sample-index` | int | `0` | Must be 0–4. Selects primary sample for adjudication reports; selects gate sample for adversarial-gate |
| `--export-dir` | path | repo `export/` | Frozen export root passed to tier/autonomous runners |
| `--cache-root` | path | repo `cache/` | Cache root passed to runners |

### Output semantics (normative)

```
default:           human text → stdout
--json:            JSON → stdout
--output PATH:     JSON → PATH; human text → stdout (unless --json also set)
--json --output:   JSON → stdout AND JSON → PATH
```

Human stdout for adjudication subcommands follows [adjudication-report.md](./adjudication-report.md) `format_adjudication_report` sections. Gate subcommand follows `format_gate_report` from Feature 003.

## Environment configuration

| Variable | Role | Default |
|----------|------|---------|
| `CACHE_MODE` | `offline` (replay) or `refresh` (live fetch) | `offline` |
| `MODEL_ID` | Model role for cache keys and report metadata | `primary` |
| `MODEL_API_KEY` | Required only for refresh path | unset in CI |

CLI MUST NOT hardcode provider or model identity. Runners load config via `load_model_config()`; report metadata reflects runner result fields (`model_id`, `cache_mode`).

Default model seam for CLI: `FakeModelSeam()` (offline replay). Runners resolve cache entries per [001/contracts/cache.md](../../001-shared-core/contracts/cache.md).

## Exit codes

| Code | Condition |
|------|-----------|
| `0` | Subcommand completed; report emitted |
| non-zero | Runner error (provenance failure, cache miss, validation error), argparse error, or I/O failure writing `--output` |

On runner failure: no partial report emitted (spec edge case: provenance verification failure).

## Validation errors (before runner invocation)

| Input | Behavior |
|-------|----------|
| `--sample-index` outside 0–4 | Argparse rejection with clear message |
| Unknown subcommand | Argparse error |
| `--output PATH` with missing/non-writable parent | Clear error naming PATH; no silent drop |

## JSON schema keys (acceptance contract)

### Adjudication subcommands (`t1`, `t2`, `t3`, `autonomous`)

Top-level keys MUST include:

`tier`, `runner_id`, `model_id`, `cache_mode`, `export_agent_sha`, `primary_sample_index`, `primary_metrics`, `confusion_matrix`, `sample_rollups`, `variance`

`primary_metrics` MUST contain `over_erasure`, `over_retention`, `mis_escalation`, each with nested `rate` and `interval`.

### Adversarial-gate subcommand

Top-level keys MUST include:

`detection`, `false_alarm`, `per_family`, `sample_index`

Per [003/contracts/gate-report.md](../../003-adversarial-gate/contracts/gate-report.md).

## Human stdout acceptance contract

### Adjudication subcommands

Stdout MUST contain (default mode):

- `Adjudication report` (title with sample index)
- `Over-erasure`, `Over-retention`, `Mis-escalation` rate labels
- `Confusion matrix` header
- `Cross-sample variance` section

Stdout MUST NOT include five sample rollup sections (JSON/`--output` only).

### Adversarial-gate subcommand

Stdout MUST contain:

- `Adversarial gate report`
- `Overall rates (Wilson 95% CI)`
- `Detection` and `False-alarm` rows

## Acceptance tests

| Suite | Path |
|-------|------|
| CLI | `tests/cli/test_acceptance_cli.py` |
| Report (library) | `tests/report/test_acceptance_adjudication_report.py` |

Merge gate: `uv run pytest tests/report tests/cli -v` — offline, no API key.

## Non-goals

- `compare-tiers` or any cross-tier CLI subcommand
- `--run-all` combined sweep
- Live provider integration in default/CI path
- Modifications to Features 001–004 runner/core/export modules

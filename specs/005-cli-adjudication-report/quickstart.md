# Quickstart: 005-cli-adjudication-report validation

**Feature**: CLI and adjudication report  
**Branch**: `005-cli-adjudication-report`

This guide validates the integration-layer acceptance contract: adjudication report tables, cross-tier comparison (library), and `dpdp-eval` CLI subcommands. It mirrors what continuous integration verifies — fully offline with no model API key.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Clone of `dpdp-erasure-eval` on branch `005-cli-adjudication-report`
- Features 001–004 prerequisite suites passing locally (recommended before merge):
  - `tests/core/` — shared core
  - `tests/runners/` — tier sweeps
  - `tests/gate/` — adversarial gate
  - `tests/autonomous/` — autonomous retrieval
- No `MODEL_API_KEY` required for default validation

## Setup

```bash
cd dpdp-erasure-eval
uv sync
```

Ensure default cache mode is offline:

```powershell
# PowerShell
$env:CACHE_MODE = "offline"
Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue
```

```bash
# Bash
export CACHE_MODE=offline
unset MODEL_API_KEY
```

## Merge gate (Feature 005 CI command)

```bash
uv run pytest tests/report tests/cli -v
```

**Expected**: All tests pass (16 tests as of plan date). No network calls. No API key warnings. Covers Wilson parity, rate fidelity, zero-denominator nulls, confusion matrix and five rollups, prohibited-field absence, four-row cross-tier comparison, offline CLI subcommands, JSON schema keys, human section headers, `--output` JSON file write, and `--sample-index`.

## Run all five CLI subcommands (offline)

Human-readable stdout (default):

```bash
uv run dpdp-eval t1
uv run dpdp-eval t2
uv run dpdp-eval t3
uv run dpdp-eval autonomous
uv run dpdp-eval adversarial-gate
```

**Expected**: Each command exits `0`. Adjudication subcommands print title with sample index, primary Wilson rate rows (`Over-erasure`, `Over-retention`, `Mis-escalation`), confusion matrix, and cross-sample variance. Gate subcommand prints `Adversarial gate report` with `Detection` and `False-alarm` rows. No blended accuracy fields.

JSON to stdout:

```bash
uv run dpdp-eval t1 --json
uv run dpdp-eval autonomous --json
uv run dpdp-eval adversarial-gate --json
```

**Expected**: Valid JSON on stdout. Adjudication payload includes `primary_metrics`, `confusion_matrix`, `sample_rollups` (length 5), and `variance`. Gate payload includes `detection`, `false_alarm`, `per_family`.

## `--output` writes JSON without `--json`

```bash
uv run dpdp-eval t2 --output /tmp/t2-report.json
```

PowerShell example:

```powershell
uv run dpdp-eval t2 --output "$env:TEMP\t2-report.json"
```

**Expected**: Exit `0`. File contains valid JSON with `"tier": "t2"`. Stdout remains human-readable (not JSON) unless `--json` is also set.

Combined JSON to stdout and file:

```bash
uv run dpdp-eval t3 --json --output /tmp/t3-report.json
```

**Expected**: JSON on stdout and identical JSON written to file.

## `--sample-index` flag

```bash
uv run dpdp-eval t1 --json --sample-index 2
```

**Expected**: JSON shows `"primary_sample_index": 2`. All five entries still present in `sample_rollups`. Human stdout title reflects sample 2.

Invalid sample index (should fail before runner):

```bash
uv run dpdp-eval t1 --sample-index 9
```

**Expected**: Non-zero exit; argparse error mentioning valid range 0–4.

## Spot-check: report library (cross-tier comparison)

Cross-tier comparison is library-only — not a CLI subcommand:

```bash
uv run pytest tests/report/test_acceptance_adjudication_report.py::test_cross_tier_comparison_includes_all_four_runners -v
```

**Expected**: Four rows (`t1`, `t2`, `t3`, `autonomous`) with Wilson-augmented rates from sample 0.

## Spot-check: Wilson parity

```bash
uv run pytest tests/report/test_acceptance_adjudication_report.py::test_wilson_bounds_match_hand_calculated_adjudication_fixture -v
```

**Expected**: Wilson bounds match hand-calculated values within `1e-9` tolerance using `report/wilson.py` only.

## Spot-check: zero-denominator nulls

```bash
uv run pytest tests/report/test_acceptance_adjudication_report.py::test_zero_denominator_rates_have_null_value_and_interval -v
```

**Expected**: `rate.value` and `interval` are both `null` when denominator is zero.

## Spot-check: CLI human output sections

```bash
uv run pytest tests/cli/test_acceptance_cli.py::test_cli_human_output_when_json_not_set -v
```

**Expected**: Human stdout contains `Adjudication report` and `Over-erasure`.

## Run prerequisite suites (recommended)

```bash
uv run pytest tests/core tests/runners tests/gate tests/autonomous -v
```

**Expected**: Features 001–004 still pass; Feature 005 adds report/CLI modules without modifying frozen runner/core/export code.

## Lint and format (CI parity)

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Clean lint and format — same gates as pull request CI.

## Optional: refresh path (local only, not CI)

Requires `MODEL_API_KEY` and `CACHE_MODE=refresh`. Excluded from merge gate.

```powershell
$env:CACHE_MODE = "refresh"
$env:MODEL_API_KEY = "<your-key>"
```

```bash
export CACHE_MODE=refresh
export MODEL_API_KEY="<your-key>"
```

Use only to regenerate cache entries after runner changes. Re-commit cache under review.

## Contract references

- Adjudication report: [contracts/adjudication-report.md](./contracts/adjudication-report.md)
- CLI surface: [contracts/cli.md](./contracts/cli.md)
- Data model: [data-model.md](./data-model.md)
- Research decisions: [research.md](./research.md)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `CacheMissError` on offline CLI run | Missing cache entry for runner/subject/sample | Ensure committed cache covers tier/autonomous/gate namespaces; run prerequisite feature quickstarts |
| `ProvenanceError` at sweep start | Export pin mismatch | Do not edit committed export; verify clone integrity |
| CLI exits 0 but JSON missing `sample_rollups` | Wrong subcommand or stale build | Use adjudication subcommands (`t1`–`autonomous`); rebuild env with `uv sync` |
| Gate human output missing family section | No families with non-zero attack cases in selected sample | Expected when all per-family denominators are zero; JSON still valid |
| Tests pass locally but fail in CI | Network or API key leakage | Set `CACHE_MODE=offline`; unset `MODEL_API_KEY` |
| `--output` file empty or missing | Non-writable parent directory | Create parent dir or choose writable path; CLI should error clearly |

## Success checklist

- [ ] `uv sync` completes without errors
- [ ] `uv run pytest tests/report tests/cli -v` — all green, no API key
- [ ] All five `dpdp-eval` subcommands exit 0 offline
- [ ] `--output` writes JSON while stdout stays human-readable (without `--json`)
- [ ] `--sample-index 2` reflected in `primary_sample_index`
- [ ] No `accuracy`, `micro_f1`, `blended_score`, or `blended_accuracy` in JSON output

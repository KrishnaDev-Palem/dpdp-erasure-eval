# Quickstart: 003-adversarial-gate validation

**Feature**: Adversarial gate evaluation  
**Branch**: `003-adversarial-gate`

This guide validates the adversarial-gate acceptance contract after implementation. It mirrors what continuous integration verifies: fully offline gate sweep and report tests with no model API key.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Clone of `dpdp-erasure-eval` on branch `003-adversarial-gate`
- Feature 001 shared core passing (`tests/core/`)
- Feature 002 tier runners passing (`tests/runners/`) — gate reuses cache/config patterns
- No `MODEL_API_KEY` required for default validation

## Setup

```bash
cd dpdp-erasure-eval
uv sync
```

Ensure default cache mode is offline:

```bash
# PowerShell
$env:CACHE_MODE = "offline"

# Bash
export CACHE_MODE=offline
```

## Run full gate acceptance suite (offline)

```bash
uv run pytest tests/gate -v
```

**Expected**: All tests pass. No network calls. No API key warnings. Tests cover extended slice fixture, gate runner sweep, label isolation, N=5 sampling, variance summary, Wilson intervals, per-family tables, env-based configuration, and offline cache replay.

## Run prerequisite suites

```bash
uv run pytest tests/core tests/runners -v
```

**Expected**: Feature 001 core and Feature 002 tier runners still pass; gate depends on export loader, model seam, cache, and adversarial scoring primitives.

## Spot-check: extended slice fixture

After slice loader implementation:

```bash
uv run pytest tests/gate/test_acceptance_adversarial_slice.py -v
```

**Expected**: Three frozen seeds present with byte identity to export; 80–100 cases; five attack families represented; attack/benign balance within documented bands.

## Spot-check: gate offline sweep

After gate runner implementation:

```bash
uv run python -c "
from core.model.fake import FakeModelSeam
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
result = run_adversarial_gate_sweep(seam=FakeModelSeam())
assert len(result.samples) == 5
assert result.runner_id == 'adversarial_gate'
print('Gate sweep OK:', result.slice_case_count, 'cases, sample 0 detection rate:',
      result.samples[0].scoring.detection_rate.value)
"
```

With committed cache (preferred integration path), run via acceptance tests instead of `FakeModelSeam` when verifying replay fidelity.

**Expected**: Five per-sample rollups; detection and false-alarm rates present; no blended accuracy field.

## Spot-check: label isolation

```bash
uv run pytest tests/gate/test_acceptance_label_isolation.py -v
```

**Expected**: Ground-truth `label` and `family` never appear in seam call kwargs or cache-canonicalized payloads; only `text` drives prompt hash.

## Spot-check: Wilson intervals and per-family tables

```bash
uv run pytest tests/gate/test_acceptance_gate_report.py -v
```

**Expected**: Wilson bounds and per-family detection rows match hand-calculated fixtures on representative numerators/denominators; zero-denominator families omitted from per-family table; overall rates with zero attack or zero benign pairs report null Wilson intervals.

## Spot-check: cache miss behavior (offline)

```bash
uv run pytest tests/gate -k cache_miss -v
```

**Expected**: Explicit failure identifying `case_id`, `sample_index`, and `runner_id` — no silent live model call.

## Spot-check: N=5 variance

```bash
uv run pytest tests/gate/test_acceptance_gate_sample_variance.py -v
```

**Expected**: Five distinct per-sample scoring results when cache entries exist for all indices; variance summary lists detection and false-alarm rates at every sample index with constancy flags.

## Lint (matches CI)

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: No violations.

## Refresh path (optional, requires API key)

Not run in CI. Use only when deliberately refreshing committed cache entries:

```bash
# PowerShell
$env:MODEL_API_KEY = "your-key-here"
$env:CACHE_MODE = "refresh"

# Bash
export MODEL_API_KEY=your-key-here
export CACHE_MODE=refresh
```

Run refresh against a narrow fixture or documented subset (full slice refresh is a manual, bounded operation):

```bash
uv run pytest tests/gate -m refresh -v
```

**Expected**: New JSON files written under `cache/{model_id}/adversarial_gate/...`. Commit additive entries only; do not edit export seeds or accepted slice cases.

Reset to offline before merge:

```bash
# PowerShell
$env:CACHE_MODE = "offline"
Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue
```

## Related artifacts

- Gate orchestration: [contracts/gate-runner.md](./contracts/gate-runner.md)
- Slice fixture: [contracts/adversarial-slice.md](./contracts/adversarial-slice.md)
- Report output: [contracts/gate-report.md](./contracts/gate-report.md)
- Gate-layer types: [data-model.md](./data-model.md)
- Feature 001 core contracts: [001/contracts/](../001-shared-core/contracts/)
- Feature 002 runner patterns: [002/contracts/runner-spine.md](../002-context-tier-sweep/contracts/runner-spine.md), [002/contracts/sweep-result.md](../002-context-tier-sweep/contracts/sweep-result.md)
- Implementation tasks: [tasks.md](./tasks.md) (after `/speckit-tasks`)

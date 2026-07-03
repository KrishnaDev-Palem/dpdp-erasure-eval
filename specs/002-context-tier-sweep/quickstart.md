# Quickstart: 002-context-tier-sweep validation

**Feature**: Context-tier adjudication sweep  
**Branch**: `002-context-tier-sweep`

This guide validates the tier runner acceptance contract after implementation. It mirrors what continuous integration verifies: fully offline T1/T2/T3 sweeps with no model API key.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Clone of `dpdp-erasure-eval` on branch `002-context-tier-sweep`
- Feature 001 shared core passing (`tests/core/`)
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

## Run full acceptance suite (offline)

```bash
uv run pytest tests/runners -v
```

**Expected**: All tests pass. No network calls. No API key warnings. Tests cover spine orchestration, all three tier runners, N=5 sampling, variance summary, ground-truth isolation, and env-based configuration.

## Run Feature 001 core (prerequisite check)

```bash
uv run pytest tests/core -v
```

**Expected**: All core tests still pass; runners depend on export loader, context builders, cache, seam, and scoring.

## Spot-check: T1 offline sweep

After runner implementation lands:

```bash
uv run python -c "
from core.model.fake import FakeModelSeam
from runners.t1 import run_t1_sweep
result = run_t1_sweep(seam=FakeModelSeam())
assert len(result.samples) == 5
assert result.runner_id == 't1'
print('T1 sweep OK:', result.samples[0].scoring.total_cases, 'pairs at sample 0')
"
```

With committed cache (preferred integration path), use a cache-backed seam or run via acceptance tests instead of `FakeModelSeam` when verifying replay fidelity.

**Expected**: Five per-sample rollups; standalone rates present; no blended accuracy field.

## Spot-check: T2 and T3 context isolation

```bash
uv run pytest tests/runners/test_acceptance_context_isolation.py -v
```

**Expected**: Model-facing bundles never contain `expected` keys; T2 includes records; T3 includes rules corpus.

## Spot-check: cache miss behavior (offline)

```bash
uv run pytest tests/runners -k cache_miss -v
```

**Expected**: Explicit failure identifying tier, subject, and sample index — no silent live model call.

## Spot-check: N=5 variance

```bash
uv run pytest tests/runners/test_acceptance_sample_variance.py -v
```

**Expected**: Five distinct per-sample scoring results when cache entries exist for all indices; variance summary lists each standalone rate at every sample index with constancy flags.

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

Run a single-tier refresh against a narrow fixture or documented subset (full export refresh is a manual, bounded operation):

```bash
uv run pytest tests/runners -m refresh -v
```

**Expected**: New JSON files written under `cache/{model_id}/{runner_id}/...`. Commit additive entries only; do not edit accepted export files.

Reset to offline before merge:

```bash
# PowerShell
$env:CACHE_MODE = "offline"
Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue
```

## Related artifacts

- Runner orchestration: [contracts/runner-spine.md](./contracts/runner-spine.md)
- Tier mapping: [contracts/tier-runner.md](./contracts/tier-runner.md)
- Output schema: [contracts/sweep-result.md](./contracts/sweep-result.md)
- Runner-layer types: [data-model.md](./data-model.md)
- Feature 001 core contracts: [001/contracts/](../001-shared-core/contracts/)
- Implementation tasks: [tasks.md](./tasks.md) (after `/speckit-tasks`)

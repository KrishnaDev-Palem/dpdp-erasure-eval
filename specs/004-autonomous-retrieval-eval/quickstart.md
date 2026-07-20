# Quickstart: 004-autonomous-retrieval-eval validation

**Feature**: Autonomous retrieval evaluation  
**Branch**: `004-autonomous-retrieval-eval`

This guide validates the autonomous retrieval acceptance contract after implementation. It mirrors what continuous integration verifies: fully offline autonomous sweep and acceptance tests with no model API key.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Clone of `dpdp-erasure-eval` on branch `004-autonomous-retrieval-eval`
- Feature 001 shared core passing (`tests/core/`)
- Feature 002 tier runners passing (`tests/runners/`) — autonomous reuses cache/config/pairing patterns
- Feature 003 adversarial gate passing (`tests/gate/`) — unchanged; confirms no regressions
- No provider API keys required for default validation

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

## Run full autonomous acceptance suite (offline)

```bash
uv run pytest tests/autonomous -v
```

**Expected**: All tests pass. No network calls. No API key warnings. Tests cover retrieval tool parity, autonomous runner sweep, label isolation, N=5 sampling, variance summary, env-based configuration, offline cache replay, and tool-call trace persistence.

## Run prerequisite suites

```bash
uv run pytest tests/core tests/runners tests/gate -v
```

**Expected**: Feature 001 core, Feature 002 tier runners, and Feature 003 gate still pass; autonomous adds new modules without modifying frozen interfaces.

## Spot-check: retrieval tool parity

After tool implementation:

```bash
uv run pytest tests/autonomous/test_acceptance_retrieval_tools.py -v
```

**Expected**: Tool outputs match T2/T3 builder outputs field-for-field (excluding `expected`); no ground-truth leakage.

## Spot-check: autonomous offline sweep

After runner implementation:

```bash
uv run python -c "
from core.model.fake import FakeModelSeam
from runners.autonomous.runner import run_autonomous_sweep
result = run_autonomous_sweep(seam=FakeModelSeam())
assert len(result.samples) == 5
assert result.runner_id == 'autonomous'
print('Autonomous sweep OK:', result.samples[0].total_subjects, 'subjects, sample 0 over-erasure rate:',
      result.samples[0].scoring.over_erasure_rate.value)
"
```

With committed cache (preferred integration path), run via acceptance tests instead of `FakeModelSeam` when verifying replay fidelity.

**Expected**: Five per-sample rollups; over-erasure, over-retention, and mis-escalation rates present; no blended accuracy field.

## Spot-check: label isolation

```bash
uv run pytest tests/autonomous/test_acceptance_autonomous_label_isolation.py -v
```

**Expected**: `expected` fields absent from tool responses, T1 initial context, and cache-canonicalized payloads.

## Spot-check: tool-call traces in cache

```bash
uv run pytest tests/autonomous/test_acceptance_tool_call_traces.py tests/autonomous/test_acceptance_autonomous_cache_offline.py -v
```

**Expected**: Autonomous cache entries include ordered `tool_calls` where applicable; tier-runner entries have empty `tool_calls`.

## Spot-check: sample variance

```bash
uv run pytest tests/autonomous/test_acceptance_autonomous_sample_variance.py -v
```

**Expected**: Five distinct per-sample aggregate scoring results; variance summary reports constancy flags for each standalone rate.

## Lint and format (CI parity)

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: Clean lint and format — same gates as pull request CI.

## Optional: refresh path (local only, not CI)

Requires a provider API key (`ANTHROPIC_API_KEY` or `GEMINI_API_KEY` for the active `MODEL_ID`) and `CACHE_MODE=refresh`. Documented for cache regeneration only; excluded from merge gate.

```bash
# PowerShell
$env:CACHE_MODE = "refresh"
$env:ANTHROPIC_API_KEY = "<your-key>"

# Bash
export CACHE_MODE=refresh
export ANTHROPIC_API_KEY="<your-key>"
```

Run refresh via project-specific cache generation script or runner entrypoint once implemented (see [contracts/autonomous-runner.md](./contracts/autonomous-runner.md)). Re-commit new autonomous cache entries under `cache/primary/autonomous/` after review.

## Contract references

- Retrieval tools: [contracts/retrieval-tools.md](./contracts/retrieval-tools.md)
- Autonomous runner: [contracts/autonomous-runner.md](./contracts/autonomous-runner.md)
- Tool-call traces: [contracts/tool-call-trace.md](./contracts/tool-call-trace.md)
- Data model: [data-model.md](./data-model.md)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `CacheMissError` on offline run | Missing autonomous cache entry for subject/sample | Ensure all location-bearing subjects (2 in current export) × 5 samples committed under `cache/.../autonomous/` (10 entries total) |
| `ProvenanceError` at sweep start | Export pin mismatch | Do not edit committed export; verify clone integrity |
| Tests fail with `expected` in payload | Tool or context leakage | Check retrieval tools strip `expected`; use `build_t1` only for initial context |
| Tier tests fail after autonomous work | Accidental tier/gate modification | Revert changes to `runners/t1.py`, `t2.py`, `t3.py`, `spine.py`, `adversarial_gate/` |

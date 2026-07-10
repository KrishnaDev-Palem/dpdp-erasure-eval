# Quickstart: 006-live-model-seam validation

**Feature**: Live model seam wiring  
**Branch**: `006-live-model-seam`

This guide validates offline CI behavior (default) and documents the opt-in refresh path for live provider adapters. Merge gate matches CI: full pytest offline with no API keys.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Clone of `dpdp-erasure-eval` on branch `006-live-model-seam`
- Features 001–005 acceptance suites passing as baseline
- **Offline validation**: no API keys
- **Refresh validation** (local only): `ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY` with billing-enabled accounts

## Setup

```bash
cd dpdp-erasure-eval
uv sync
```

Default offline mode:

```bash
# PowerShell
$env:CACHE_MODE = "offline"

# Bash
export CACHE_MODE=offline
```

## Run full acceptance suite (offline — CI parity)

```bash
uv run pytest -v
```

**Expected**: All tests pass. No network. No provider keys required. Includes Features 001–005 regression plus new factory/adapter contract tests under `tests/core/`.

## Run Feature 006 contract tests only

```bash
uv run pytest tests/core/test_acceptance_model_factory.py tests/core/test_acceptance_live_adapters.py tests/core/test_acceptance_provider_credentials.py -v
```

**Expected**: Factory returns `FakeModelSeam` in offline mode; refresh resolution errors are actionable; adapter contract tests pass with mocked SDK responses.

## Spot-check: factory offline default

```bash
uv run python -c "
from core.model.factory import create_model_seam
from core.model.fake import FakeModelSeam
seam = create_model_seam()
assert isinstance(seam, FakeModelSeam)
print('Factory offline OK')
"
```

**Expected**: `FakeModelSeam` instance even if API keys are present in the environment.

## Spot-check: refresh miss without keys fails before network

```bash
# PowerShell
$env:CACHE_MODE = "refresh"
$env:MODEL_ID = "claude-sonnet-5"
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:MODEL_API_KEY -ErrorAction SilentlyContinue

# Bash
export CACHE_MODE=refresh
export MODEL_ID=claude-sonnet-5
unset ANTHROPIC_API_KEY MODEL_API_KEY
```

```bash
uv run python -c "
from core.model.factory import create_model_seam
try:
    create_model_seam()
except Exception as exc:
    assert 'ANTHROPIC_API_KEY' in str(exc) or 'credential' in str(exc).lower()
    print('Credential guard OK:', type(exc).__name__)
else:
    raise SystemExit('Expected ConfigurationError')
"
```

**Expected**: Clear error naming required credential; no HTTP traffic.

## Spot-check: existing refresh tests (FakeModelSeam stand-in)

```bash
uv run pytest -m refresh -v
```

**Expected**: Refresh-path cache write/replay tests pass using `FakeModelSeam` — no live keys.

## Refresh workflow (local operator — excluded from CI)

Copy environment template:

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY or GEMINI_API_KEY, MODEL_ID, CACHE_MODE=refresh
```

Supported roles and pinned provider ids (see [research.md](./research.md)):

| `MODEL_ID` | Credential | Provider model id |
|------------|------------|-------------------|
| `claude-sonnet-5` | `ANTHROPIC_API_KEY` | `claude-sonnet-5` |
| `gemini-3.5-flash` | `GEMINI_API_KEY` | `gemini-3.5-flash` |

Regenerate **one** cache entry on miss (example — adjust subject/runner as needed):

```bash
# PowerShell example: T2 single subject via CLI after implementation
$env:CACHE_MODE = "refresh"
$env:MODEL_ID = "claude-sonnet-5"
uv run dpdp-eval t2 --sample-index 0

# Bash
export CACHE_MODE=refresh
export MODEL_ID=claude-sonnet-5
uv run dpdp-eval t2 --sample-index 0
```

Use a writable cache root or temporary directory if experimenting — **do not commit live-generated entries to `main` without explicit review** (spec FR-012).

Verify offline replay:

```bash
$env:CACHE_MODE = "offline"   # or export CACHE_MODE=offline
uv run dpdp-eval t2 --sample-index 0
```

**Expected**: Same verdicts from written cache entry; no live call on hit.

## Opt-in live smoke (not in CI)

```bash
uv run pytest tests/live -m live -v
```

Requires valid keys in environment. Merge gate does **not** run this marker.

## Prerequisite regression

```bash
uv run pytest tests/core tests/runners tests/gate tests/autonomous tests/report tests/cli -v
```

**Expected**: Features 001–005 suites remain green without modification to `export/` or committed `cache/`.

## References

- Factory contract: [contracts/model-seam-factory.md](./contracts/model-seam-factory.md)
- Live adapters: [contracts/live-adapters.md](./contracts/live-adapters.md)
- Data model: [data-model.md](./data-model.md)
- Model seam base: [001/contracts/model-seam.md](../001-shared-core/contracts/model-seam.md)
- Cache refresh semantics: [001/contracts/cache.md](../001-shared-core/contracts/cache.md)

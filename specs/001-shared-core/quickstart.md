# Quickstart: 001-shared-core validation

**Feature**: Shared core  
**Branch**: `001-shared-core`

This guide validates the shared core acceptance contract after implementation. It does not replace the acceptance suite; it is the human-readable path to reproduce green CI locally.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- Clone of `dpdp-erasure-eval` on branch `001-shared-core`
- No `MODEL_API_KEY` required for default validation

## Setup

```bash
cd dpdp-erasure-eval
uv sync
```

## Run acceptance suite (offline)

```bash
uv run pytest tests/core -v
```

**Expected**: All tests pass. No network calls. No API key warnings.

## Spot-check: provenance

```bash
uv run python -c "from core.export import load_export; e = load_export(); e.verify_provenance()"
```

**Expected**: Silent success (exit 0). A tampered `export/manifest.yaml` or wrong `PINNED_AGENT_SHA` must raise `ProvenanceError`.

## Spot-check: context tiers

```bash
uv run pytest tests/core/test_acceptance_context.py -v
```

**Expected**: T1 bundle has request only; T2 adds locations without `expected`; T3 adds rules corpus.

## Spot-check: adjudication scoring

```bash
uv run pytest tests/core/test_acceptance_scoring_adjudication.py -v
```

**Expected**: Hand-crafted fixture produces expected over-erasure rate; no blended accuracy field in result.

## Spot-check: cache replay

```bash
set CACHE_MODE=offline
uv run pytest tests/core/test_acceptance_cache.py -v
```

**Expected**: Cached response returned; cache miss raises explicit error (no silent live call).

## Lint (matches CI)

```bash
uv run ruff check .
uv run ruff format --check .
```

**Expected**: No violations.

## Refresh path (optional, requires API key)

Only when deliberately refreshing cache entries:

```bash
set MODEL_API_KEY=your-key-here
set CACHE_MODE=refresh
uv run pytest tests/core/test_acceptance_cache.py -k refresh -v
```

**Expected**: Selected tests write new cache files under `cache/`. Not run in CI.

## Related artifacts

- Data shapes: [data-model.md](./data-model.md)
- Interfaces: [contracts/](./contracts/)
- Implementation tasks: [tasks.md](./tasks.md)

# Feature 005: CLI and Adjudication Report

**Branch**: `005-cli-adjudication-report`

## Summary

Thin CLI entrypoint (`dpdp-eval`) and adjudication report layer consuming existing
runner results. Cross-cutting integration deferred from Features 001–004.

## Quick start

```bash
uv sync --all-extras
uv run dpdp-eval t1 --json
uv run dpdp-eval t2
uv run dpdp-eval t3
uv run dpdp-eval autonomous --json
uv run dpdp-eval adversarial-gate --json
uv run pytest tests/report tests/cli -v
```

No `MODEL_API_KEY` required. Default `CACHE_MODE=offline` replays committed cache.

## Contracts

- [adjudication-report.md](./contracts/adjudication-report.md)

## Scope

- `report/adjudication_tables.py`, `report/adjudication_types.py`
- `cli/` package with argparse subcommands
- Acceptance tests under `tests/report/` and `tests/cli/`
- Console script in `pyproject.toml`

## Out of scope

- Runner, export, or scoring math changes
- Live model provider
- Per-subject variance tables

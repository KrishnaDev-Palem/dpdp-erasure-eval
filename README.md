# DPDP Erasure Evaluation Harness

Thesis-first evaluation harness for measuring model adjudication behavior against a
deterministic frozen export from [dpdp-erasure-agent](https://github.com/KrishnaDev-Palem/dpdp-erasure-agent).

This repository implements the **shared core** (Feature 001): export loading with
provenance verification, injectable model seam, offline cache replay, adjudication and
adversarial scoring primitives, and T1/T2/T3 context assembly.

## Quick start (offline)

```bash
git clone https://github.com/KrishnaDev-Palem/dpdp-erasure-eval.git
cd dpdp-erasure-eval
uv sync --all-extras
uv run pytest -v
```

Feature 005 merge gate (report + CLI only):

```bash
uv run pytest tests/report tests/cli -v
```

No `MODEL_API_KEY` is required. CI runs the same path in offline mode.

## Live model seam (Feature 006)

Default runs use `FakeModelSeam` and committed cache — no provider API keys and no
network. To regenerate cache entries locally with live models, set `CACHE_MODE=refresh`
and the provider key for your target role:

| `MODEL_ID` | Credential |
|------------|------------|
| `claude-sonnet-5` | `ANTHROPIC_API_KEY` |
| `gemini-3.5-flash` | `GEMINI_API_KEY` |

Copy `.env.example` to `.env` for variable names (no secrets in the repo). Refresh is
operator opt-in and excluded from the CI merge gate; live smoke tests require
`-m live` explicitly.

See [`specs/006-live-model-seam/quickstart.md`](specs/006-live-model-seam/quickstart.md)
for offline validation, credential guards, and refresh workflow examples.

## Live-role evaluations (Feature 007)

Committed cache under `cache/claude-sonnet-5/` and `cache/gemini-3.5-flash/` lets
thesis readers reproduce live-model numbers offline with no API keys. Set
`CACHE_MODE=offline` and the role for each evaluation path:

| Evaluation path | Reader-facing name | `MODEL_ID` |
|-----------------|-------------------|------------|
| `dpdp-eval t2` | records-augmented | `claude-sonnet-5` |
| `dpdp-eval adversarial-gate` | adversarial-gate | `gemini-3.5-flash` |
| `dpdp-eval autonomous` | autonomous retrieval | `claude-sonnet-5` |

```powershell
# PowerShell
$env:CACHE_MODE = "offline"
$env:MODEL_ID = "claude-sonnet-5"
uv run dpdp-eval t2 --json
uv run dpdp-eval autonomous --json
$env:MODEL_ID = "gemini-3.5-flash"
uv run dpdp-eval adversarial-gate --json
```

```bash
# Bash
export CACHE_MODE=offline
MODEL_ID=claude-sonnet-5 uv run dpdp-eval t2 --json
MODEL_ID=claude-sonnet-5 uv run dpdp-eval autonomous --json
MODEL_ID=gemini-3.5-flash uv run dpdp-eval adversarial-gate --json
```

To regenerate entries locally, see
[`specs/007-live-role-cache-seed/quickstart.md`](specs/007-live-role-cache-seed/quickstart.md).

## Running evaluations

The `dpdp-eval` CLI runs each evaluation sweep from committed cache and emits
adjudication or gate report tables (human-readable stdout, optional `--json`):

```bash
uv run dpdp-eval t1 --json
uv run dpdp-eval t2
uv run dpdp-eval t3
uv run dpdp-eval autonomous --json
uv run dpdp-eval adversarial-gate --json
```

Use `--sample-index N` (0..4, default 0) to select the primary rate table sample.
See [`specs/005-cli-adjudication-report/quickstart.md`](specs/005-cli-adjudication-report/quickstart.md).

## Tier runners (Feature 002)

Context-tier adjudication sweeps (T1/T2/T3) live under `runners/`. See
[`specs/002-context-tier-sweep/quickstart.md`](specs/002-context-tier-sweep/quickstart.md)
for the full offline validation path.

```bash
uv run pytest tests/runners -v
```

![CI status](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/actions/workflows/ci.yml/badge.svg)

## Context tiers (reader-facing names)

| Tier | Name | Content |
|------|------|---------|
| T1 | request-only | Erasure request only |
| T2 | records-augmented | Request plus location records (no ground truth) |
| T3 | rule-augmented | T2 plus retention floors and governance map |

## Documentation

- Feature spec: [`specs/001-shared-core/spec.md`](specs/001-shared-core/spec.md)
- Quickstart validation: [`specs/001-shared-core/quickstart.md`](specs/001-shared-core/quickstart.md)
- ADR-0001 frozen export: [`docs/adr/0001-frozen-export-ground-truth.md`](docs/adr/0001-frozen-export-ground-truth.md)

## License

MIT — see [`LICENSE`](LICENSE).

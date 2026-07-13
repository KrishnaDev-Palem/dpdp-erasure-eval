# Quickstart: 007-live-role-cache-seed

**Feature**: Live role cache seeding
**Branch**: `007-live-role-cache-seed`

Two workflows:

1. **Offline replay validation** (default, CI parity) — anyone, no keys, no network.
2. **Operator refresh runbook** — seeding/re-seeding the committed live-role cache with
   provider credentials. Local only; excluded from the CI merge gate.

Contracts: [committed-cache-tree.md](./contracts/committed-cache-tree.md),
[offline-replay-tests.md](./contracts/offline-replay-tests.md). Coverage and cost numbers:
[research.md](./research.md) R1/R3.

## Prerequisites

- Python 3.11+, [uv](https://docs.astral.sh/uv/), clean clone on branch `007-live-role-cache-seed`
- `uv sync`
- **Offline replay**: nothing else — no API keys
- **Refresh runbook**: billing-enabled `ANTHROPIC_API_KEY` (Claude Sonnet 5) and
  `GEMINI_API_KEY` (Gemini 3.5 Flash); copy `.env.example` to `.env` for variable names

## Part 1 — Offline replay validation (no keys)

### Full merge-gate suite

```bash
uv run pytest -v
```

**Expected**: everything green, including the new live-role replay tests, with zero provider
keys and zero network.

### Live-role replay tests only

```bash
uv run pytest tests/runners/test_acceptance_live_role_t2_replay.py tests/gate/test_acceptance_live_role_gate_replay.py tests/autonomous/test_acceptance_live_role_autonomous_replay.py tests/cli/test_acceptance_cli_live_roles.py -v
```

### CLI replay per runner path

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

**Expected**: each exits 0; JSON `model_id` echoes the role; results are identical across
repeated runs; no cache miss errors. Target: all three complete in under 5 minutes on a
clean clone after `uv sync` (SC-004).

## Part 2 — Operator refresh runbook (local only, excluded from CI)

> **Do not run against `main`'s cache casually.** Refresh writes real entries under
> `cache/<role>/`. Entries are committed only after the verification checklist below and
> human PR review (FR-015). `cache/primary/` and `export/` must never change.

### Expected volume and cost (verified 2026-07-12)

| Sweep | Role | Live calls (cold) | Est. cost |
|-------|------|-------------------|-----------|
| T2 | `claude-sonnet-5` | 10 adjudications | ≤ $0.20 |
| Adversarial gate | `gemini-3.5-flash` | **450 classifications** (90 cases × 5 samples) | ≤ $2.75 |
| Autonomous | `claude-sonnet-5` | 10 sessions × ≤10 tool rounds (≤100 requests) | ≤ $2.60 |
| **Total** | | ≤560 requests | **≈ $3–6** (ceiling < $10) |

Pricing basis: Sonnet 5 $2/$10 per MTok (intro through 2026-08-31), Gemini 3.5 Flash
$1.50/$9 per MTok. Refresh is idempotent on re-run: cache hits replay for free; only misses
call the provider — an interrupted sweep is resumed by simply re-running it.

### Step 1 — T2 sweep (Claude Sonnet 5)

```powershell
# PowerShell
$env:CACHE_MODE = "refresh"
$env:MODEL_ID = "claude-sonnet-5"
$env:ANTHROPIC_API_KEY = "<key>"
uv run dpdp-eval t2 --json --output t2-refresh.json
```

```bash
# Bash
export CACHE_MODE=refresh MODEL_ID=claude-sonnet-5 ANTHROPIC_API_KEY=<key>
uv run dpdp-eval t2 --json --output t2-refresh.json
```

**Expected**: exactly 10 new files under `cache/claude-sonnet-5/t2/` (2 subjects × samples 0–4).

### Step 2 — Adversarial gate sweep (Gemini 3.5 Flash)

```powershell
# PowerShell
$env:CACHE_MODE = "refresh"
$env:MODEL_ID = "gemini-3.5-flash"
$env:GEMINI_API_KEY = "<key>"
uv run dpdp-eval adversarial-gate --json --output gate-refresh.json
```

```bash
# Bash
export CACHE_MODE=refresh MODEL_ID=gemini-3.5-flash GEMINI_API_KEY=<key>
uv run dpdp-eval adversarial-gate --json --output gate-refresh.json
```

**Expected**: 450 new files under `cache/gemini-3.5-flash/adversarial_gate/` (90 case
directories × 5 samples). This is the expensive sweep — plan for ~450 provider calls.

### Step 3 — Autonomous sweep (Claude Sonnet 5)

```powershell
# PowerShell
$env:CACHE_MODE = "refresh"
$env:MODEL_ID = "claude-sonnet-5"
$env:ANTHROPIC_API_KEY = "<key>"
uv run dpdp-eval autonomous --json --output autonomous-refresh.json
```

```bash
# Bash
export CACHE_MODE=refresh MODEL_ID=claude-sonnet-5 ANTHROPIC_API_KEY=<key>
uv run dpdp-eval autonomous --json --output autonomous-refresh.json
```

**Expected**: exactly 10 new files under `cache/claude-sonnet-5/autonomous/`, each with a
`tool_calls` trace where the model used retrieval tools.

### Step 4 — Offline parity verification (before commit)

Re-run each sweep offline and compare payloads:

```powershell
# PowerShell (repeat per subcommand/role)
$env:CACHE_MODE = "offline"
$env:MODEL_ID = "claude-sonnet-5"
uv run dpdp-eval t2 --json --output t2-offline.json
Compare-Object (Get-Content t2-refresh.json) (Get-Content t2-offline.json)   # no output = parity
```

```bash
# Bash (repeat per subcommand/role)
export CACHE_MODE=offline
MODEL_ID=claude-sonnet-5 uv run dpdp-eval t2 --json --output t2-offline.json
diff t2-refresh.json t2-offline.json    # empty = parity
```

Then run the full offline suite with keys removed from the environment:

```powershell
# PowerShell
Remove-Item Env:ANTHROPIC_API_KEY, Env:GEMINI_API_KEY, Env:MODEL_API_KEY -ErrorAction SilentlyContinue
$env:CACHE_MODE = "offline"
uv run pytest -v
```

```bash
# Bash
unset ANTHROPIC_API_KEY GEMINI_API_KEY MODEL_API_KEY
export CACHE_MODE=offline
uv run pytest -v
```

### Step 5 — Namespace verification (before commit)

```bash
git status --short                                  # only cache/claude-sonnet-5/, cache/gemini-3.5-flash/, tests, docs
git diff --stat main -- cache/primary export        # MUST print nothing
```

Do not stage the `*-refresh.json` / `*-offline.json` scratch reports.

## SC-002 completion checklist (Feature 006 → 007)

Check off before requesting PR review; the reviewer re-verifies each item on the diff.

- [ ] `cache/claude-sonnet-5/t2/` contains exactly 10 entries (2 subjects × samples 0–4)
- [ ] `cache/gemini-3.5-flash/adversarial_gate/` contains exactly 450 entries (90 cases × 5 samples)
- [ ] `cache/claude-sonnet-5/autonomous/` contains exactly 10 entries with `tool_calls` traces;
      any empty trace confirmed as genuine no-tool-use session
- [ ] Offline re-run of each sweep produced byte-equal JSON payload vs its refresh run (Step 4)
- [ ] `git diff main -- cache/primary export` is empty (Step 5)
- [ ] All entry files match the Feature 001 schema (path segments agree with embedded fields)
- [ ] `uv run pytest -v` green offline with all provider keys unset
- [ ] No secrets, `.env`, or scratch report files staged
- [ ] README links to this quickstart and documents live-role offline evaluation

## References

- Refresh path architecture: [006/plan.md](../006-live-model-seam/plan.md)
- Live adapters contract: [006/contracts/live-adapters.md](../006-live-model-seam/contracts/live-adapters.md)
- Cache semantics: [001/contracts/cache.md](../001-shared-core/contracts/cache.md)
- Tool-call trace schema: [004/contracts/tool-call-trace.md](../004-autonomous-retrieval-eval/contracts/tool-call-trace.md)

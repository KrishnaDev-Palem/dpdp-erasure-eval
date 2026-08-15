# Live Coverage Run

Generate the 350-case coverage-slice export to a side directory and run live T1, T2, T3, and autonomous against it at three samples, then prove the offline twins match. Leave the default pin, default `export/`, default `results/`, default `cache/`, and default writeup exactly as they are.

**Prior:** Archive v1 is merged ([PR #20](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/pull/20)). Tag `eval-v1.0.0` is on origin at the per-stratum-rates merge ([PR #19](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/pull/19)). The committed pin is still agent commit `3562059939cbaac3dc3500593f2940ef34c54c53`. The coverage slice (agent tag `export-v1.1.0`, SHA `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`, 350 cases) is not the committed answer key yet.

This is an operator session, not a branch. No git writes. No merge. No live calls until the cost section has been read. Do not replace the default path with the coverage slice here.

A **sample** is another try of the same case, not a new person.

---

## Goal

Produce a complete, replayable 350-case / 3-sample adjudication cache and results set against agent tag `export-v1.1.0`, without touching the published 16-person / 34-location tree. Live and offline pairs must match. The adversarial gate is not re-run. The committed pin stays `3562059…` until a later change replaces the default path.

## In scope / out of scope

**In scope**

- Generate the coverage-slice export to a side directory with `scripts/regenerate_export.py --pinned-tag export-v1.1.0 --output-dir <side-root>/export`. No `--overwrite-committed`.
- Live T1, T2, T3, and autonomous at `--samples 3` against that export and a new `--cache-root`.
- Offline twins of those four runners against the same two paths.
- Retrieval-versus-reasoning split of autonomous incorrect verdicts against the same autonomous cache (offline; it only reads traces).
- Mechanical live/offline pair checks on the four adjudication JSON files.

**Out of scope**

- Creating a branch, committing, tagging, opening a PR, or merging
- Flipping `export/PINNED_AGENT_SHA` or replacing `export/adjudication/subjects.yaml`
- `--overwrite-committed`, or any write to committed `export/`, `results/`, `cache/`, `docs/writeup.md`, `docs/figures/`, `archive/`, or the root `README.md`
- Re-running the adversarial gate (same 90 notes, same 44/45, same five samples)
- `dpdp-eval report figures` (the figures command re-sweeps at the default five samples and the agreement figure is locked to five-sample buckets; a three-sample cache will miss). Do not change `report/figures/`. Figures wait until the default path is the coverage slice.
- Building `cross-tier-comparison.json` (library-only; no CLI). A later publish change can build it from the four sweeps.
- Editing the July 2026 post, the personal-website repo, or any writeup permalink
- The 6,450-case pool as a committed artifact
- Engine / generator / agent-repository changes
- Replacing the default path with the coverage slice, ADR-0008 edits, or a later writeup that cites the coverage-slice rates

## Path decision

- **Side directory, not the default path.** Pick one root **outside** this git worktree. Do not put it under `export/`, `cache/`, `results/`, `archive/`, `docs/`, `briefs/`, or `brainstorming/`. Suggested: `C:\dpdp-coverage-run` (Windows) or `/tmp/dpdp-coverage-run` (Unix). Layout:

  ```
  <side-root>/
    export/     # regenerate_export.py --output-dir
    cache/      # --cache-root (claude-sonnet-5 only)
    results/    # --output JSON
  ```

- **Every runner invocation names both paths.** Forgetting `--export-dir` scores the committed 16-person / 34-location export. Forgetting `--cache-root` writes into committed `cache/`. Forgetting `--samples 3` requests five samples (~7,000 adjudications). If any of those three flags is omitted, stop. Do not continue from a mixed tree.
- **Refresh reuses existing keys.** `CacheStore.get_or_refresh` does not re-call the model when the key is already on disk. If a sweep dies, re-run the same command against the same `<side-root>/cache`. Do not delete the cache to "start clean" unless the export itself is wrong.
- **Loaders stay pointed at repository-root `export/` by default.** Do not add `<side-root>` to any default path, glob, fixture, or test. Do not teach the loader a second answer key.
- **T1 live location scope.** T1 context is request-only (empty locations). Live T1 resolves required location IDs by loading `export/` relative to the process working directory. Run live T1 with the working directory set to `<side-root>` so that relative `export/` is the coverage-slice export, not the committed 16-person / 34-location tree. Do not change the harness in this session.
- **Figures wait.** The existing `report figures` path cannot emit them from a three-sample cache without a harness change. That change belongs with the later publish work.
- **Durable copy of this note:** `briefs/live-coverage-run.md`. Committing this file must not stage anything under `<side-root>/`.

## Cost (read before any refresh)

Locked planning figure:

| Sweep | Role | Cases × samples | Planning calls |
|---|---|---|---|
| T1 | `claude-sonnet-5` | 350 × 3 | 1,050 |
| T2 | `claude-sonnet-5` | 350 × 3 | 1,050 |
| T3 | `claude-sonnet-5` | 350 × 3 | 1,050 |
| Autonomous | `claude-sonnet-5` | 350 × 3 | 1,050 adjudications, plus up to 10 tool rounds per session |
| **Adjudication total** | | | **~4,200** (350 × 4 × 3) |
| Gate | — | — | **0. Do not run.** |

Autonomous tool rounds are extra provider calls on top of the 1,050 sessions. Do not invent a dollar ceiling here. Do not start live adjudication until the operator has read this table.

The repo does not load `.env`. `ANTHROPIC_API_KEY`, `MODEL_ID`, and `CACHE_MODE` must be in the process environment. `GEMINI_API_KEY` is not required.

## Preconditions (human, before generating the export)

Confirm all of the following. If any check fails, stop.

1. `git fetch origin` and `git checkout main && git pull`. `HEAD` is `origin/main` (PR #20 merge or later).
2. `export/PINNED_AGENT_SHA` is `3562059939cbaac3dc3500593f2940ef34c54c53`.
3. `git tag -l eval-v1.0.0` is present. `archive/v1/` exists on `main` and is absent from `git ls-tree --name-only eval-v1.0.0`.
4. Default `export/`, `results/`, `cache/`, `docs/writeup.md`, and `docs/figures/` are unmodified relative to `origin/main`.
5. `<side-root>` does not exist, or is empty. The export command creates `export/`. Create `<side-root>/results` before the live sweeps (`--output` refuses a missing parent). `cache/` is created on the first refresh write.

## Git use

None during the run.

- Do not create a branch.
- Do not commit, stage, or add `<side-root>/`.
- Do not commit to `main`, merge, rebase, rewrite history, force-push, or tag as part of the run.
- Do not run `git add cache`, `git add export`, or `git add results`.

## Task 1: Generate the coverage-slice export

```bash
uv run python scripts/regenerate_export.py \
  --pinned-tag export-v1.1.0 \
  --output-dir <side-root>/export
```

Optional: `--agent-checkout <path-to-dpdp-erasure-agent>` only when that checkout's `HEAD` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`. If it is not, omit the flag and let the script clone the tag.

**Expected stdout**

- Pinned agent SHA: `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`
- `as_of`: `2026-02-15`
- Subjects / locations: `350 / 350`
- Expected pool hash: `d681eeecb5e77054402eec9bd3de8f8424333126dcaf4dcfc072b597dd343d21`
- Expected membership hash: `b93646fb429571eb690060285c1fca32ad015388ee7c14eb99d30f855924e464`

Confirm `<side-root>/export/PINNED_AGENT_SHA` equals that SHA and matches `agent_commit_sha` in `<side-root>/export/manifest.yaml`.

**Stop and surface if** the script asks for `--overwrite-committed`, if any hash or count is wrong, if the pin is `3562059…`, or if anything under repository-root `export/` changes.

## Task 2: Live adjudication

Sequential. T1, then T2, then T3, then autonomous. Do not run the four in parallel. Do not run `adversarial-gate`.

`mkdir <side-root>/results` if it does not exist. `--output` exits non-zero when the parent directory is missing.

Set once per shell (PowerShell: `$env:MODEL_ID = "claude-sonnet-5"`; `$env:CACHE_MODE = "refresh"`; `$env:ANTHROPIC_API_KEY` already set):

```bash
export MODEL_ID=claude-sonnet-5
export CACHE_MODE=refresh
```

Then, one runner at a time, with the working directory set to `<side-root>` for live T1 (see Path decision):

```bash
uv run dpdp-eval t1 --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t1-live.json

uv run dpdp-eval t2 --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t2-live.json

uv run dpdp-eval t3 --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t3-live.json

uv run dpdp-eval autonomous --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/autonomous-live.json
```

Each live JSON must have `model_id` `claude-sonnet-5`, `cache_mode` `refresh`, `export_agent_sha` `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`, three `sample_rollups`, and over-erasure denominator `350`. `by_cell` and `by_stratum` must be non-empty (the coverage-slice export carries `strata`).

Cache entries land under `<side-root>/cache/claude-sonnet-5/{t1,t2,t3,autonomous}/`. Expected cardinality after all four finish: 350 subjects × 4 runners × 3 samples = 4,200 files.

**Stop and surface if** a JSON has denominator 34, pin `3562059…`, five sample rollups, empty grouped tables, or if any file appears under repository-root `cache/` or `results/` that was not there before this task.

## Task 3: Offline twins

Same two paths. Same `--samples 3`. `CACHE_MODE=offline`. No API key required. No live calls.

```bash
export MODEL_ID=claude-sonnet-5
export CACHE_MODE=offline

uv run dpdp-eval t1 --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t1-offline.json

uv run dpdp-eval t2 --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t2-offline.json

uv run dpdp-eval t3 --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t3-offline.json

uv run dpdp-eval autonomous --samples 3 --json \
  --export-dir <side-root>/export \
  --cache-root <side-root>/cache \
  --output <side-root>/results/autonomous-offline.json
```

A cache miss here means the live sweep was incomplete. Re-run the matching live command; do not delete the cache.

## Task 4: Retrieval-versus-reasoning split

After the autonomous cache exists. Offline. Primary sample is index 0.

The official `dpdp-eval autonomous-retrieval-split` command walks samples 0–4 and the report type requires five rollups. This run only has samples 0, 1, and 2. Do not invent samples 3 and 4. Build the retrieval-split JSON from the existing three-sample autonomous cache using the same library helpers the command uses. Do not change the harness in this session.

Write `<side-root>/results/autonomous-retrieval-split-offline.json`. `export_agent_sha` must be `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`. Three `sample_rollups` (`sample_index` 0, 1, 2) is the correct shape for this cache.

The committed 16-person / 34-location tree only keeps a live retrieval-split file. One offline file is enough here.

## Task 5: Verify live/offline pairs

For each of `t1`, `t2`, `t3`, `autonomous`:

- `export_agent_sha` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22` on both files
- live `cache_mode` is `refresh`; offline `cache_mode` is `offline`
- both have exactly three `sample_rollups` (`sample_index` 0, 1, 2)
- over-erasure / over-retention / mis-escalation denominators are 350
- `by_cell` and `by_stratum` are non-empty on both
- every field other than `cache_mode` is identical

```python
import json
from pathlib import Path

sha = "7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22"
side = Path("<side-root>/results")
for name in ("t1", "t2", "t3", "autonomous"):
    live = json.loads((side / f"{name}-live.json").read_text(encoding="utf-8"))
    offline = json.loads((side / f"{name}-offline.json").read_text(encoding="utf-8"))
    assert live["export_agent_sha"] == offline["export_agent_sha"] == sha
    assert live["model_id"] == offline["model_id"] == "claude-sonnet-5"
    assert live["cache_mode"] == "refresh"
    assert offline["cache_mode"] == "offline"
    assert len(live["sample_rollups"]) == len(offline["sample_rollups"]) == 3
    assert live["primary_metrics"]["over_erasure"]["rate"]["denominator"] == 350
    assert live["by_cell"] and live["by_stratum"]
    live_cmp = {key: value for key, value in live.items() if key != "cache_mode"}
    offline_cmp = {key: value for key, value in offline.items() if key != "cache_mode"}
    assert live_cmp == offline_cmp, name
```

**Stop and surface if** any assertion fails. Do not flip the committed pin. Do not start the later publish change.

## Acceptance

- [ ] `<side-root>/export/PINNED_AGENT_SHA` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`; subjects / locations are 350 / 350; pool and membership hashes match Task 1
- [ ] Four live JSON files and four offline JSON files exist under `<side-root>/results/`; each pair matches except `cache_mode`
- [ ] Retrieval-split JSON exists, embeds pin `7b659e8…`, and has three sample rollups
- [ ] Side cache has 4,200 `claude-sonnet-5` adjudication entries (350 × 4 × 3) and no `gemini-3.5-flash` / `adversarial_gate` tree
- [ ] Default `export/PINNED_AGENT_SHA` is still `3562059939cbaac3dc3500593f2940ef34c54c53`
- [ ] Default `export/`, `results/`, `cache/`, `docs/writeup.md`, `docs/figures/`, `archive/v1/`, and `fixtures/` are unmodified
- [ ] Gate was not invoked
- [ ] No branch, no commit of the side directory, no `--overwrite-committed`

## CI expectations

No workflow edits. No pool generation in CI. No live model in CI. This session does not change the merge-gate suite.

## Handoff

After the pairs match, the default tree is still the 16-person / 34-location experiment. The side root is the input to a later publish change: the committed export becomes the 350-case coverage slice, the pin flips to `7b659e8…`, adjudication `results/` and the adjudication cache are replaced, the writeup / README / figures are rewritten, tests that assume 16-person / 34-location subjects, `mixed_fanout`, or pin `3562059` are fixed, and the archive identity tests are deleted or inverted. Gate files stay. Do not start that change here.

## Human actions after this brief completes

1. Confirm repository-root `export/PINNED_AGENT_SHA` is still `3562059…` and `git status` does not show default-path edits.
2. Keep `<side-root>` on disk. The later publish change copies from it; do not regenerate unless a hash check failed.
3. Ask for a brief that replaces the default path with the coverage-slice export, results, cache, and writeup. Do not write it in this session.

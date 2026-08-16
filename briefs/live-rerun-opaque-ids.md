# Live Re-run Under Opaque Identifiers

Re-run the adversarial gate and the four adjudication settings against the committed coverage-slice export
using the Phase A harness, in which no design-cell name or label reaches a prompt. Write everything to a side
directory. Leave the committed `export/`, `results/`, `cache/`, `docs/`, and README exactly as they are.

**Prior:** Phase A of [`briefs/prompt-boundary-isolation.md`](./prompt-boundary-isolation.md) is complete on
`feat/prompt-boundary-isolation`, its acceptance list is signed off, and the suite is green except the
enumerated live-role replay tests. The committed export is already the coverage slice (350 / 350, pin
`7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`) and is **not** regenerated here. The contaminated baseline stays
at `c6b7f87`.

This is an operator session, not a branch. No git writes. No merge. No live calls until the cost section has
been read.

A **sample** is another try of the same case, not a new person.

---

## Goal

A complete, replayable set of results and cache entries produced under opaque identifiers: 450 gate entries
at five samples and 4,200 adjudication entries at three samples, with live and offline twins matching. The
committed tree is untouched. The side root is the input to Phase B.

## In scope / out of scope

**In scope**

- Live adversarial gate at five samples against `fixtures/adversarial_slice/cases.yaml`.
- Live T1, T2, T3, autonomous at three samples against the committed `export/`.
- Offline twins of all five sweeps against the same side cache.
- Retrieval-versus-reasoning split from the new autonomous traces.
- Proof that the new cache keys differ from the committed ones, and that no cell name or label survives in
  any rendered prompt for the cases actually run.

**Out of scope**

- Creating a branch, committing, staging, tagging, opening a PR, or merging.
- Any write to committed `export/`, `results/`, `cache/`, `docs/`, `archive/`, `fixtures/`, or `README.md`.
- Regenerating the export. `scripts/regenerate_export.py` is not run in this session. The pin does not move.
- Harness changes of any kind. If the run reveals a harness defect, stop and surface; fix it in Phase A, not
  here.
- Copying the side root onto the committed paths. That is Phase B.
- Figures, writeup, README, or the blog.

## Path decision

- **No side export.** Unlike the previous coverage run, the committed `export/` is already the correct answer
  key at the correct pin. Read from it directly. The side root needs only `cache/` and `results/`.
- **Side root outside the worktree.** Not under `export/`, `cache/`, `results/`, `archive/`, `docs/`,
  `briefs/`, or `brainstorming/`. Suggested `C:\dpdp-opaque-run` (Windows) or `/tmp/dpdp-opaque-run` (Unix):

  ```
  <side-root>/
    cache/      # --cache-root (claude-sonnet-5 and gemini-3.5-flash)
    results/    # --output JSON
  ```

- **Run from the Phase A working tree.** This is the one deviation from `briefs/live-coverage-run.md`, which
  ran against clean `main`. This run requires the Phase A code — the whole point is the new prompts and the
  new keys. Confirm `git rev-parse --abbrev-ref HEAD` is `feat/prompt-boundary-isolation` and `git status` is
  clean before any live call. A run from `main` or from a dirty tree is void; discard the side cache and
  start over.
- **`--cache-root` on every invocation.** Forgetting it writes into committed `cache/`. If it is omitted
  once, stop, and inspect `git status` before continuing.
- **No working-directory trick for T1.** The previous brief required `cwd = <side-root>` because live T1
  resolved location ids by loading a relative `export/`. Phase A Task 2 removed that: T1 ids come from the
  bundle. Run from the repo root.
- **Gate first.** It is 450 calls against the cheap role and exercises the new prompt path and the new key
  end to end. Do not begin the 4,200-call adjudication sweep until the gate has completed and Task 2 passes.
- **Refresh reuses existing keys.** A key already on disk is not re-called. If a sweep dies, re-run the same
  command against the same side cache. Do not delete the cache to "start clean" unless a leak check fails.
- **Durable copy of this note:** `briefs/live-rerun-opaque-ids.md`.

## Cost (read before any refresh)

| Sweep | Role | Cases × samples | Planning calls |
|---|---|---|---|
| Adversarial gate | `gemini-3.5-flash` | 90 × 5 | 450 |
| T1 | `claude-sonnet-5` | 350 × 3 | 1,050 |
| T2 | `claude-sonnet-5` | 350 × 3 | 1,050 |
| T3 | `claude-sonnet-5` | 350 × 3 | 1,050 |
| Autonomous | `claude-sonnet-5` | 350 × 3 | 1,050 sessions, plus up to 10 tool rounds each |
| **Total** | | | **4,650**, plus autonomous tool rounds |

Autonomous tool rounds are extra provider calls on top of the 1,050 sessions; the committed baseline shows
three tool calls per session. Do not invent a dollar ceiling here. Do not start live adjudication until the
operator has read this table.

Unlike the previous run, **both** provider keys are required. The repo does not load `.env`;
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `MODEL_ID`, and `CACHE_MODE` must be in the process environment.

## Preconditions

Confirm all of the following. If any check fails, stop.

1. `git rev-parse --abbrev-ref HEAD` is `feat/prompt-boundary-isolation`; `git status` is clean.
2. Phase A acceptance in `briefs/prompt-boundary-isolation.md` is signed off, including the enumerated
   expected-red list.
3. `uv run pytest -q` fails **only** on the enumerated live-role replay tests. Any other failure voids the
   run.
4. `export/PINNED_AGENT_SHA` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`; `load_export` reports 350 / 350.
5. `<side-root>` does not exist or is empty. Create `<side-root>/results` before the sweeps; `--output`
   refuses a missing parent. `cache/` is created on the first refresh write.
6. Both API keys are set and valid.

## Git use

None during the run.

- Do not create a branch, commit, stage, or `git add <side-root>/`.
- Do not run `git add cache`, `git add export`, or `git add results`.
- Do not merge, rebase, rewrite history, force-push, or tag.

## Task 1: Live adversarial gate

```bash
export MODEL_ID=gemini-3.5-flash
export CACHE_MODE=refresh

uv run dpdp-eval adversarial-gate --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/gate-live.json
```

Five samples is the gate's fixed shape; `--samples` is rejected by design. Expect 450 entries under
`<side-root>/cache/gemini-3.5-flash/adversarial_gate/`.

**Stop and surface if** the sweep completes in a fraction of the ~11 minutes the contaminated run took, if
fewer than 450 entries land, or if any file appears under repository-root `cache/` or `results/`.

## Task 2: Prove the gate key actually changed

The single most important check in this session. If the gate cache key did not change, Task 1 replayed
nothing and produced nothing new — but it would still look like a successful run.

```python
from pathlib import Path

committed = {p.name for p in Path("cache/gemini-3.5-flash/adversarial_gate").glob("*/*")}
side = {p.name for p in Path("<side-root>/cache/gemini-3.5-flash/adversarial_gate").glob("*/*")}
assert committed and side, "both trees must be populated"
assert not (committed & side), f"{len(committed & side)} prompt hashes carried over — key did not change"
print(f"committed {len(committed)}  side {len(side)}  overlap 0")
```

Those directory names are the `prompt_hash` component of the cache path. Zero overlap is the requirement.

**Stop and surface if** the overlap is non-zero. Do not continue to adjudication. The Phase A cache-key
change did not take effect and the contaminated responses are being reused.

## Task 3: Live adjudication

Sequential. T1, then T2, then T3, then autonomous. Do not run them in parallel. Run from the repo root.

```bash
export MODEL_ID=claude-sonnet-5
export CACHE_MODE=refresh

uv run dpdp-eval t1 --samples 3 --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t1-live.json

uv run dpdp-eval t2 --samples 3 --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t2-live.json

uv run dpdp-eval t3 --samples 3 --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/t3-live.json

uv run dpdp-eval autonomous --samples 3 --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/autonomous-live.json
```

Each live JSON must carry `model_id` `claude-sonnet-5`, `cache_mode` `refresh`, `export_agent_sha`
`7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`, three `sample_rollups`, denominators of 350, and non-empty
`by_cell` / `by_stratum`. Expected cardinality after all four: 4,200 files under
`<side-root>/cache/claude-sonnet-5/`.

Apply the Task 2 overlap check to `cache/claude-sonnet-5/t1` against the side tree once T1 finishes, before
spending the remaining three sweeps.

**Stop and surface if** a JSON has denominator 34, pin `3562059…`, five rollups, empty grouped tables, or if
any adjudication response fails to parse. A parse failure means the model returned an id the harness cannot
map back; that is a Phase A defect, not something to work around here.

## Task 4: Offline twins

Same side cache. Same `--samples 3`. No API key required, no live calls.

```bash
export CACHE_MODE=offline

MODEL_ID=gemini-3.5-flash uv run dpdp-eval adversarial-gate --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/gate-offline.json

export MODEL_ID=claude-sonnet-5
uv run dpdp-eval t1 --samples 3 --json --cache-root <side-root>/cache --output <side-root>/results/t1-offline.json
uv run dpdp-eval t2 --samples 3 --json --cache-root <side-root>/cache --output <side-root>/results/t2-offline.json
uv run dpdp-eval t3 --samples 3 --json --cache-root <side-root>/cache --output <side-root>/results/t3-offline.json
uv run dpdp-eval autonomous --samples 3 --json --cache-root <side-root>/cache --output <side-root>/results/autonomous-offline.json
```

A cache miss here means the matching live sweep was incomplete. Re-run that live command; do not delete the
cache.

## Task 5: Retrieval-versus-reasoning split

After the autonomous cache exists. Offline, primary sample 0. The official command walks the samples that
exist, so it works against a three-sample cache.

```bash
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval autonomous-retrieval-split --json \
  --cache-root <side-root>/cache \
  --output <side-root>/results/autonomous-retrieval-split-offline.json
```

Three `sample_rollups` and pin `7b659e8…` are the correct shape.

Record the retrieval / reasoning split for the writeup, and note the tool-call count per session. If it is
again three calls per session, the §4 framing correction in Phase B stands as written.

## Task 6: Verify live/offline pairs

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
    assert live["cache_mode"] == "refresh" and offline["cache_mode"] == "offline"
    assert len(live["sample_rollups"]) == len(offline["sample_rollups"]) == 3
    assert live["primary_metrics"]["over_erasure"]["rate"]["denominator"] == 350
    assert live["by_cell"] and live["by_stratum"]
    assert {k: v for k, v in live.items() if k != "cache_mode"} == \
           {k: v for k, v in offline.items() if k != "cache_mode"}, name

gate_live = json.loads((side / "gate-live.json").read_text(encoding="utf-8"))
gate_offline = json.loads((side / "gate-offline.json").read_text(encoding="utf-8"))
assert gate_live == gate_offline
print("pairs match")
```

**Stop and surface if** any assertion fails.

## Task 7: Leak check on what was actually run

Independent of the Phase A tests, confirm on this run's own inputs that nothing leaked.

```python
from pathlib import Path
from core.export.loader import load_export
from core.context.tiers import build_t1, build_t2, build_t3
from core.model.adapter_common import build_adjudication_prompt, build_classification_prompt
from runners.adversarial_gate.slice_loader import load_extended_slice

b = load_export(Path("export"))
cells = {l.cell_id for s in b.subjects for l in s.locations}
for s in b.subjects:
    for ctx in (build_t1(s.request, s), build_t2(s.request, s), build_t3(s.request, s, b.rules)):
        p = build_adjudication_prompt(context=ctx, case_id=s.subject_id)
        hit = next((c for c in cells if c in p), None)
        assert hit is None, f"{s.subject_id}: cell name {hit!r} in prompt"

for case in load_extended_slice(Path("fixtures/adversarial_slice/cases.yaml"), verify_seeds=False).cases:
    p = build_classification_prompt(text=case.text, case_id=case.case_id)
    assert case.case_id not in p and "adv-" not in p and "benign-" not in p, case.case_id
print("no cell name or label in any rendered prompt")
```

Note: `case_id` is still passed to `build_adjudication_prompt` because it addresses the cache entry; the
assertion is that the *cell name* inside it does not survive into the prompt text.

## Acceptance

- [ ] Run performed from `feat/prompt-boundary-isolation` with a clean tree
- [ ] Side cache: 450 `gemini-3.5-flash` gate entries and 4,200 `claude-sonnet-5` adjudication entries
- [ ] Zero `prompt_hash` overlap between committed and side caches, gate **and** adjudication
- [ ] Five live JSON and five offline JSON under `<side-root>/results/`; pairs match except `cache_mode`; gate pair byte-identical
- [ ] Retrieval-split JSON exists with three rollups and pin `7b659e8…`; tool-call count per session recorded
- [ ] Task 7 leak check passes over all 350 subjects and all 90 gate cases
- [ ] Token / cost figures captured from the run and recorded for the writeup
- [ ] Committed `export/`, `results/`, `cache/`, `docs/`, `archive/`, `fixtures/`, `README.md` unmodified — `git status` clean
- [ ] No branch, no commit, no `--overwrite-committed`, no harness edit

## CI expectations

No workflow edits. No live model in CI. This session does not change the merge-gate suite.

## Handoff

After the pairs match, the committed tree is still the contaminated coverage slice and the side root holds
the clean run. Phase B of `briefs/prompt-boundary-isolation.md` copies it in, rebuilds the comparison and
split, regenerates figures, and rewrites the writeup and README with the before/after delta against
`c6b7f87`. Do not start Phase B in this session.

## Human actions after this brief completes

1. Confirm `git status` shows no default-path edits and the pin is still `7b659e8…`.
2. Record the headline rates from the five offline JSON files next to the `c6b7f87` baseline. That table is
   the finding; it is written up in Phase B, not here.
3. Keep `<side-root>` on disk until the pull request is merged. Do not regenerate it.
4. Begin Phase B.

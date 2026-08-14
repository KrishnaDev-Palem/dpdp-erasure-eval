# Archive v1

Freeze the published 16-person / 34-location experiment in place, then leave the default pin, default `export/`, default `results/`, and default writeup exactly as they are.

**Parent:** `brainstorming/archive-then-write-on-top.md` (gitignored decision note). Per-stratum rates is merged ([PR #19](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/pull/19)). The live pin is still agent commit `3562059939cbaac3dc3500593f2940ef34c54c53`. The coverage slice (agent tag `export-v1.1.0`, SHA `7b659e8…`, 350 cases) is not the committed answer key yet.

**This brief is step 1 of 3.** Step 2 is the live coverage run against a side directory. Step 3 is the write-on-top PR. Do not start either here.

Branch: `feat/archive-v1`. Cursor performs the git operations listed under **Git use**, as a documented exception to the project's human-only git rule. Tagging is a human action, listed first, and must happen before this branch exists.

---

## Goal

Keep the first published paper replayable after a later write-on-top overwrites the default path. A git tag is the full replay handle (export + cache + results + writeup + figures). A thin `archive/v1/` is the in-repo copy a reader can find without `git log`. Default paths stay the 16/34 experiment. Tests stay green. No live calls.

## In scope / out of scope

**In scope**

- Human tags `eval-v1.0.0` on today's `origin/main` **before** any file is added or moved.
- Additive `archive/v1/` on a branch cut from that tagged commit: copy of committed `export/`, copy of committed `results/` JSON, copy of `docs/writeup.md`, copy of `docs/figures/`, and a short `archive/v1/README.md`.
- One sentence in the root `README.md` pointing at `archive/v1/` and the tag. No other README rewrite.
- Tests that lock the archive's identity (pin `3562059…`, no `cache/`, README names the tag and the replay command) without teaching the loader to treat `archive/v1/export` as the default answer key.

**Out of scope**

- Retargeting or editing the July 2026 post, the personal-website repo, hosted figures, or any writeup permalink. That is a human action outside this brief.
- Flipping `export/PINNED_AGENT_SHA` or replacing `export/adjudication/subjects.yaml`
- Editing default `results/`, default `docs/writeup.md`, or default `docs/figures/`
- Copying `cache/`, the 6,450-case pool, `fixtures/adversarial_slice/`, or the gate cache
- `regenerate_export.py`, `--overwrite-committed`, or any write to committed `export/`
- Live model calls, cache refresh, re-running T1/T2/T3/autonomous or the gate
- Write-on-top of the 350-case slice, ADR-0008, or a second post
- Engine / generator / agent-repository changes

## Path decision

- **Tag first, copy second.** `eval-v1.0.0` points at current `origin/main` (PR #19 merge, `5528dc70e6d9d5f2c2661f68980a0541041dafb8` at the time this brief was written). The tag is the published v1 tree. It must not include `archive/v1/`.
- **Start from that tagged commit**, not from the stale local `main` (it is many commits behind) and not from `feat/per-stratum-rates`.
- **Layout.** Preserve the original relative paths so the archived writeup's figure links keep working after step 3 overwrites `docs/figures/`:

  ```
  archive/v1/
    README.md
    export/          # byte-identical copy of committed export/
    results/         # byte-identical copy of the twelve committed JSON files
    docs/
      writeup.md     # byte-identical copy of docs/writeup.md
      figures/       # byte-identical copy of docs/figures/*.png
  ```

  `docs/figures/` is not named in the parent decision note. Include it anyway: the writeup embeds `figures/…` relatively, and step 3 will replace `docs/figures/` with coverage-slice figures. Omitting the PNGs would make the archived paper inherit the next experiment's pictures.
- **Copy, do not rewrite.** Archived `export/`, `results/`, `docs/writeup.md`, and `docs/figures/` are verbatim. No path rewrites inside the writeup. No SHA edits. No regeneration.
- **Loaders stay pointed at repository-root `export/`.** Do not add `archive/` to any default path, glob, or fixture. `tests/report/test_results_export_agent_sha.py` already globs `results/*.json` only; leave that as-is.
- **Root README.** One sentence under "Ground truth you can audit" or in the repo map, naming `archive/v1/` and `git checkout eval-v1.0.0`. Do not change the 16/34 numbers, the pin link, or the reproduce commands.
- **Durable copy of this note:** `briefs/archive-v1.md`.

## Preconditions (human, before the branch)

Confirm all of the following, then tag. If any check fails, stop. Do not create the branch.

1. `git fetch origin` and `git checkout main && git pull`. `HEAD` is `origin/main`.
2. `export/PINNED_AGENT_SHA` is `3562059939cbaac3dc3500593f2940ef34c54c53`.
3. `git tag -l eval-v1.0.0` is empty on both local and `origin`.
4. Working tree clean.

Then:

```bash
git tag -a eval-v1.0.0 -m "Published 16-person / 34-location experiment"
git push origin eval-v1.0.0
```

Do not move or add files before the push returns. The tag is the freeze.

## Git use (this branch only)

After the tag exists on `origin`:

- `git checkout -b feat/archive-v1 eval-v1.0.0`
- One commit after the archive tree, README sentence, and tests are in and the offline suite is green. Message: a short imperative summary, no attribution footer.
- Push `feat/archive-v1` to origin after that commit.
- Never commit to `main`, never merge, never rebase or rewrite history, never force-push, never tag, never touch any other branch. Opening the PR and merging are human actions.
- If the test suite fails, do not commit; fix or stop and surface.

## Task 1: Copy the thin archive

Copy from the tagged tree (the current checkout), not from some other branch.

| Source | Destination |
|---|---|
| `export/` (entire tree) | `archive/v1/export/` |
| `results/*.json` (all twelve) | `archive/v1/results/` |
| `docs/writeup.md` | `archive/v1/docs/writeup.md` |
| `docs/figures/*.png` | `archive/v1/docs/figures/` |

Include the gate results files (`gate-live.json`, `gate-offline.json`). They are part of the published `results/` set. Do not copy `fixtures/`, `cache/`, or anything else.

**Stop and surface if** any source file is missing, if `export/PINNED_AGENT_SHA` is not `3562059…`, or if a copy would require editing default-path files.

## Task 2: Write `archive/v1/README.md`

Short. Factual. No new numbers. Contents, in order:

1. Title that this is the v1 archive (16 subjects, 34 locations).
2. Agent pin SHA `3562059939cbaac3dc3500593f2940ef34c54c53` and the tag name `eval-v1.0.0`.
3. Link to the July 2026 post: `https://krishnadev.me/writing/should-an-ai-decide-what-gets-erased-i-measured-it/`
4. What this directory is: a thin in-repo copy of `export/`, `results/`, the writeup, and the figures. Not the live pin. Not a second answer key.
5. How to replay the full experiment: `git checkout eval-v1.0.0`, then the offline reproduce commands from the root README (`uv sync`, then the six `CACHE_MODE=offline` runner commands). State that the tag, not this directory, holds the cache.
6. One sentence: do not load `archive/v1/export` as the default answer key.

## Task 3: Point the root README at the archive

Add one sentence. Candidate location: the "Ground truth you can audit" section, after the pin paragraph, or a single line in the repo map.

Name `archive/v1/` and `eval-v1.0.0`. Do not change headline rates, reproduce commands, pin URL, or test counts.

## Task 4: Lock the archive with tests

Add a small acceptance test (new file under `tests/`, next to the other path-identity tests). Assert:

- `archive/v1/export/PINNED_AGENT_SHA` equals `3562059939cbaac3dc3500593f2940ef34c54c53`
- `archive/v1/export/` is byte-identical to repository-root `export/` (same relative paths, same bytes)
- `archive/v1/results/` is byte-identical to repository-root `results/` (same twelve filenames, same bytes)
- `archive/v1/docs/writeup.md` is byte-identical to `docs/writeup.md`
- `archive/v1/docs/figures/` is byte-identical to `docs/figures/`
- `archive/v1/README.md` contains `eval-v1.0.0` and `3562059939cbaac3dc3500593f2940ef34c54c53`
- no `cache/` directory exists under `archive/`

These identity assertions are true only while the default path is still v1. The write-on-top brief (step 3) must delete or invert them. Do not put a comment in the test "reminding" step 3; the step-3 brief will handle it.

Do not load `archive/v1/export` through `load_export` as a second default. Do not parametrize existing results/export tests over the archive tree.

## Acceptance

- [ ] `eval-v1.0.0` exists on `origin` and points at the pre-archive `main` tip (PR #19 merge). The tag commit does not contain `archive/`
- [ ] `archive/v1/` holds verbatim copies of `export/`, `results/*.json`, `docs/writeup.md`, and `docs/figures/`
- [ ] `archive/v1/README.md` names the pin, the tag, the July post, and `git checkout eval-v1.0.0`
- [ ] Default `export/PINNED_AGENT_SHA` is still `3562059939cbaac3dc3500593f2940ef34c54c53`
- [ ] Default `export/`, `results/`, `docs/writeup.md`, `docs/figures/`, `cache/`, and `fixtures/` are unmodified
- [ ] Loaders, runners, and `test_results_export_agent_sha.py` still read only the default paths
- [ ] Root README has one pointer sentence and the same 16/34 numbers
- [ ] `ruff` + `pytest` green; no workflow edits; no live model

## CI expectations

No workflow edits. No pool generation. No live model. Offline suite only.

## Handoff

After this lands, the default tree is still the 16/34 experiment and the tag plus `archive/v1/` are the freeze. Step 2 is an operator session: generate the 350-case export to a side directory with `regenerate_export.py --pinned-tag export-v1.1.0 --output-dir <side-dir>` (no `--overwrite-committed`), then live T1/T2/T3/autonomous at `--samples 3` against that directory. Do not flip the committed pin until those runs finish and live/offline pairs match.

## Human actions after this brief completes

1. Confirm `eval-v1.0.0` is on `origin` and `git checkout eval-v1.0.0` still has no `archive/` directory.
2. Review the single commit on `feat/archive-v1`: copies only, plus the archive README, the one root-README sentence, and the new tests.
3. Open the PR to `main`, confirm CI green, merge.

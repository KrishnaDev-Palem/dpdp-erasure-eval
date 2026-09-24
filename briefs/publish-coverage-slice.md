# Publish the Coverage Slice

Make the committed answer key the 350-case coverage slice. Copy the already-run three-sample adjudication cache and results onto the default path, fix the harness and tests so clone-and-replay matches that cache, and stop. Leave `docs/writeup.md`, the root README, and `docs/figures/` for a writing session on the same branch.

**Prior:** Archive v1 is merged ([PR #20](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/pull/20)). Tag `eval-v1.0.0` is on origin at the per-stratum-rates merge ([PR #19](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/pull/19)). The live coverage run is complete at `C:\dpdp-coverage-run` against agent tag `export-v1.1.0` (SHA `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`). The committed pin is still `3562059939cbaac3dc3500593f2940ef34c54c53`.

This is **one pull request, two phases**. Do not merge between them. `main` must not show 350-case results next to the 16-person / 34-location writeup.

A **sample** is another try of the same case, not a new person.

---

## Goal

The default path becomes the coverage slice: pin `7b659e8…`, 350 subjects / 350 locations, three-sample adjudication cache and results, offline twins matching except `cache_mode`. The adversarial gate stays the published 90-note / five-sample tree. After Phase A the suite is green and the published paper files are still the 16-person / 34-location writeup, README rates, and figures. Phase B rewrites those three together.

## In scope / out of scope

**Phase A — in scope (mechanical session)**

- Thread the runner's export directory into live T1 location-ID resolution. Stop loading cwd `export/` from `resolve_adjudication_location_ids`.
- Teach retrieval-versus-reasoning split to walk the samples that were run (3 or 5). Stop requiring five rollups.
- Teach figures agreement buckets to accept a three-sample cache. Do not regenerate `docs/figures/` here.
- Default adjudication CLI / runner sample list becomes `[0, 1, 2]` so clone-and-replay matches the committed cache. Gate stays `[0, 1, 2, 3, 4]`. `--samples 5` remains legal for a five-sample cache.
- Copy `C:\dpdp-coverage-run\export` over committed `export/`. Flip `PINNED_AGENT_SHA`.
- Replace adjudication `results/` from the side directory. Rebuild `cross-tier-comparison.json` from the four sweeps. Emit retrieval-split through the official CLI once the harness accepts three samples.
- Replace adjudication cache under `cache/claude-sonnet-5/{t1,t2,t3,autonomous}/` from the side directory (4,200 files). Drop the 16-person / 34-location adjudication entries from HEAD.
- Re-seed `cache/primary/{t1,t2,t3,autonomous}/` against the new export at three samples so the fake-seam / CI path stays offline.
- Fix tests that assume 16 subjects, 34 locations, `mixed_fanout`, pin `3562059`, five adjudication rollups on the default path, or `archive/v1` export/results identical to the default tree.

**Phase B — in scope (writing session, same branch, after Phase A)**

- Generate coverage-slice adjudication figures into `docs/figures/`.
- Rewrite `docs/writeup.md`.
- Rewrite the root README (headline rates, subject / location counts, pin, `--samples 3` / default-three wording, test count). Keep the `archive/v1/` and `eval-v1.0.0` pointer.
- Invert the remaining archive identity assertions that require default writeup and figures to match `archive/v1`.

**Out of scope (both phases)**

- Live model calls. Do not refresh the coverage-slice cache. Do not re-run T1/T2/T3/autonomous or the gate.
- Regenerating the export with `scripts/regenerate_export.py` (including `--overwrite-committed`). Copy the already-verified side export.
- Editing `archive/v1/` contents. The snapshot stays the 16-person / 34-location paper.
- Editing the July 2026 post's rates or hosted figures. Retargeting its writeup permalink is a human action before merge.
- The 6,450-case pool as a committed artifact.
- Engine / generator / agent-repository changes. ADR-0008 already lives in the agent repo.
- A later post that cites the coverage-slice rates.
- Staging anything under `C:\dpdp-coverage-run`.

## Path decision

- **Copy, do not regenerate.** Source of truth is `C:\dpdp-coverage-run`. Pool hash `d681eeecb5e77054402eec9bd3de8f8424333126dcaf4dcfc072b597dd343d21` and membership hash `b93646fb429571eb690060285c1fca32ad015388ee7c14eb99d30f855924e464` were already checked there.
- **One branch.** Suggested: `feat/publish-coverage-slice`, cut from current `origin/main` (PR #20 or later, including `briefs/live-coverage-run.md` if that commit is on `main`).
- **Individual commits.** One concern per commit. Short imperative subjects. No attribution footer.
- **Loaders stay pointed at repository-root `export/`.** After the copy, that directory *is* the coverage slice. Do not add `C:\dpdp-coverage-run` to any default path, glob, fixture, or test.
- **Tests that need the 16-person / 34-location subject tags** (`mixed_fanout`, `floor_inside`, multi-location pairing) load `archive/v1/export` by explicit path. That is the archived snapshot, not a second default answer key. Do not parametrize the whole suite over both trees.
- **Tests of the live pin** use repository-root `export/` and assert 350 / 350, pin `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`, and present `strata` / `cell_id`.
- **Archive identity.** Phase A inverts export-identical and results-identical. Leave writeup-identical, figures-identical, archive README, archive pin, and no-cache assertions in place so Phase A can finish with the old paper files still matching the archive. Phase B inverts writeup-identical and figures-identical.
- **T1 location IDs.** `resolve_adjudication_location_ids` in `core/model/adapter_common.py` (and `core/model/anthropic_adapter.py`) must receive the same export directory the sweep loaded. Do not put `expected`, `strata`, or `cell_id` into T1 context.
- **Retrieval-versus-reasoning split.** `build_retrieval_split_report` walks the sample indices that exist (3 or 5). `RetrievalSplitReport` accepts rollup length 3 or 5. Official `dpdp-eval autonomous-retrieval-split` must succeed against the new cache.
- **Figures code.** `compute_verdict_agreement_by_tier` already takes `sample_indices`. `load_figure_inputs` and the agreement buckets must use the samples that were run. For three samples the buckets are `3/3 unanimous`, `2/3`, and `split`. Title text must not say `N=5` when the run was three. Gate figure input still comes from the five-sample gate cache. Do not write PNGs in Phase A.
- **Adjudication default is three samples.** `SweepConfig.from_env`, autonomous config, and CLI `--samples` default become 3. `ALLOWED_ADJUDICATION_SAMPLE_INDICES` still allows `[0, 1, 2, 3, 4]`. Gate types stay exactly five.
- **Gate files stay.** Do not touch `cache/gemini-3.5-flash/adversarial_gate/`, `cache/primary/adversarial_gate/`, `results/gate-live.json`, `results/gate-offline.json`, or `fixtures/adversarial_slice/`.
- **Durable copy of this note:** `briefs/publish-coverage-slice.md`.

## Side directory (do not modify)

```
C:\dpdp-coverage-run\
  export/     pin 7b659e8… ; 350 / 350
  cache/      claude-sonnet-5/{t1,t2,t3,autonomous}/  (1,050 files each)
  results/    t1/t2/t3/autonomous live+offline ; autonomous-retrieval-split-offline.json
```

Do not delete this tree until the PR is merged. Do not commit it.

## Preconditions

Confirm all of the following. If any check fails, stop. Do not create the branch.

1. `git fetch origin` and `git checkout main && git pull`. `HEAD` is `origin/main` (PR #20 merge or later).
2. Default `export/PINNED_AGENT_SHA` is still `3562059939cbaac3dc3500593f2940ef34c54c53`.
3. `archive/v1/` exists on `main` and is absent from `git ls-tree --name-only eval-v1.0.0`.
4. `C:\dpdp-coverage-run\export\PINNED_AGENT_SHA` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`. Subjects / locations 350 / 350.
5. Side cache has 4,200 `claude-sonnet-5` adjudication files and no gate / gemini tree.
6. Side live/offline pairs still match except `cache_mode` (the check in `briefs/live-coverage-run.md` Task 5).
7. Default `docs/writeup.md`, root README, and `docs/figures/` are unmodified relative to `origin/main` except for any already-merged archive sentence.

## Git use (this branch only)

- `git checkout -b feat/publish-coverage-slice`
- Individual commits as Phase A lands. Suggested split: harness, export copy, results, adjudication cache, primary-cache seed, tests.
- Never commit to `main`. Never merge, rebase, rewrite history, force-push, or tag. Opening the PR and merging are human actions after Phase B.
- Never `git add` `C:\dpdp-coverage-run`.
- Phase A must not stage `docs/writeup.md`, `docs/figures/`, or a README rewrite. The archive pointer sentence already on `main` stays.
- If the suite fails, do not commit; fix or stop and surface.

## Phase A

### Task 1: Harness

Do this before copying the export so the official retrieval-split command and a three-sample figures path exist.

1. Pass `export_dir` into `resolve_adjudication_location_ids`. Thread it from the live Anthropic adapter / seam construction using the directory the runner already has. Add a test that T1 live resolution against a non-default export does not load repository-root `export/`.
2. `report/retrieval_split.py` and `RetrievalSplitReport`: walk `range(n)` for `n` in `{3, 5}` (or an explicit `sample_indices` argument). Tests: three rollups against a three-sample cache; five rollups still valid.
3. Figures: `load_figure_inputs` passes the adjudication sample list through to the sweeps and to `compute_verdict_agreement_by_tier`. Three-sample buckets as in Path decision. Keep generating the six filenames Phase B will write. Tests stay on fixtures; do not assert against `docs/figures/` bytes here.
4. Default adjudication sample list `[0, 1, 2]` on CLI `--samples` and `from_env`. Update `tests/cli/test_acceptance_cli.py` (`test_cli_default_adjudication_still_five_samples` becomes a three-sample default; `--samples 5` still accepted). Gate rejects `--samples` as today.

**Stop and surface if** any of these changes alter gate types, gate cache keys, or T2/T3 context contents.

### Task 2: Copy the coverage-slice export

Copy the entire side `export/` tree over repository-root `export/` (pin file, `manifest.yaml`, `adjudication/subjects.yaml`, rules, seeds).

Confirm:

- `export/PINNED_AGENT_SHA` == `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`
- `export/manifest.yaml` `agent_commit_sha` matches
- `as_of` is `2026-02-15`
- `load_export` reports 350 subjects / 350 locations
- every location carries `strata` and `cell_id`
- `archive/v1/export/PINNED_AGENT_SHA` is still `3562059…`

Do not run `regenerate_export.py`. Do not edit `archive/v1/export`.

Update the "do not flip the pin yet" comments in `core/export/coverage.py` and `scripts/regenerate_export.py` so they describe the committed pin as the coverage slice.

### Task 3: Replace adjudication results

| Source (`C:\dpdp-coverage-run\results\`) | Destination (`results/`) |
|---|---|
| `t1-live.json` | `t1-live.json` |
| `t1-offline.json` | `t1-offline.json` |
| `t2-live.json` | `t2-live.json` |
| `t2-offline.json` | `t2-offline.json` |
| `t3-live.json` | `t3-live.json` |
| `t3-offline.json` | `t3-offline.json` |
| `autonomous-live.json` | `autonomous-live.json` |
| `autonomous-offline.json` | `autonomous-offline.json` |

Keep `gate-live.json` and `gate-offline.json`.

After Task 1, emit retrieval-split with the official command (offline, default sample 0) to `results/autonomous-retrieval-split-offline.json`. Remove `results/autonomous-retrieval-split-live.json` if it still embeds pin `3562059` or five rollups.

Rebuild `results/cross-tier-comparison.json` with `build_cross_tier_comparison` from the four offline sweeps at `sample_index=0`. No new CLI.

Every adjudication JSON except the two gate files must embed `export_agent_sha` `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`. Gate files keep `3562059…` only if that is what they already embed; do not rewrite them. If `test_results_export_agent_sha.py` requires every `results/*.json` to match the new pin, exclude the gate files or split the assertion — do not restamp the gate results.

### Task 4: Replace the adjudication cache

- Delete repository-root `cache/claude-sonnet-5/{t1,t2,t3,autonomous}/` and copy the matching trees from `C:\dpdp-coverage-run\cache\claude-sonnet-5\`. Expected: 1,050 JSON files each (350 × 3).
- Delete repository-root `cache/primary/{t1,t2,t3,autonomous}/`. Re-seed those four runners against the new export at sample indices 0, 1, 2 with the existing fake-seam seeder (`scripts/seed_runner_cache.py`). Update that script: stop assuming `range(5)` and stop special-casing `mixed_fanout` for the committed export. Expected: 1,050 files each.
- Leave `cache/claude-sonnet-5` without a gate tree. Leave `cache/gemini-3.5-flash/adversarial_gate/` and `cache/primary/adversarial_gate/` untouched.

**Stop and surface if** any gate cache file changes or if the copied `claude-sonnet-5` adjudication count is not 4,200.

### Task 5: Fix tests

Minimum set (search will find more):

- `tests/report/test_archive_v1_identity.py` — invert export-identical and results-identical. Archive export/results stay the 16-person / 34-location snapshot; default no longer matches. Keep pin, README, no-cache, writeup-identical, figures-identical.
- `tests/core/test_acceptance_coverage_adapter.py` — `test_committed_export_stays_v1_default` becomes a coverage-slice identity test (pin `7b659e8…`, 350 / 350, strata present). `test_v1_location_dump_omits_coverage_fields` moves to `archive/v1/export`.
- `tests/core/test_acceptance_export.py` — committed-export size and `REQUIRED_TAGS` / `mixed_fanout` assertions cannot target the coverage slice. Point tag and multi-location tests at `archive/v1/export`. Assert coverage-slice properties on the default export (one location per subject, `location_id` == `case_id` shape, `strata` present).
- Every `subject_with_tag(..., "mixed_fanout")` that today reads the default export — pass `archive/v1/export` (or a tmp copy of it) as `export_dir`.
- CLI and report tests that require five default rollups against the committed tree — expect three. Tests that pass `--samples 3` stay. Tests that use fixtures and five synthetic rollups stay at five.
- `tests/report/test_acceptance_retrieval_split.py` — committed-cache path expects three rollups.

`ruff` + `pytest` green. No workflow edits.

### Task 6: Offline replay smoke

From the repo root, no API key:

```bash
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval t1 --json
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval autonomous-retrieval-split --json
MODEL_ID=gemini-3.5-flash CACHE_MODE=offline uv run dpdp-eval adversarial-gate --json
```

Adjudication commands must exit 0 without `--samples 3` (default is now three). Each adjudication JSON has denominator 350, pin `7b659e8…`, three rollups. Gate still five samples, same 90-note slice.

**Stop and surface if** a command cache-misses, if adjudication default-walks sample 3 or 4, or if the gate result changes.

## Phase A stop

Do not open `docs/writeup.md` for a rewrite. Do not change README headline rates, subject counts, sample wording, or the reproduce block. Do not write PNGs under `docs/figures/`. Do not generate figures "to see how they look."

Phase A is done when the suite is green and the paper files are still the 16-person / 34-location writeup, README, and figures.

## Phase A acceptance

- [ ] Default `export/PINNED_AGENT_SHA` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`; 350 / 350; `strata` present
- [ ] `archive/v1/export/PINNED_AGENT_SHA` is still `3562059939cbaac3dc3500593f2940ef34c54c53`
- [ ] Adjudication results embed `7b659e8…`, three rollups, denominator 350; live/offline pairs match except `cache_mode`
- [ ] Official `autonomous-retrieval-split` offline JSON exists and has three rollups
- [ ] `cross-tier-comparison.json` rebuilt from the four sweeps at sample 0
- [ ] `cache/claude-sonnet-5` adjudication trees have 4,200 files; gate caches unchanged
- [ ] `cache/primary` adjudication trees re-seeded at three samples; primary gate cache unchanged
- [ ] Live T1 location resolution uses the runner export directory
- [ ] Adjudication default sample list is `[0, 1, 2]`; gate remains five
- [ ] `docs/writeup.md`, README rates / reproduce block, and `docs/figures/` unchanged
- [ ] `ruff` + `pytest` green; no workflow edits; no live model

## Phase B (do not execute in the mechanical session)

Same branch. One sitting. Shared vocabulary: retention floor, anchor, trigger, over-erasure, over-retention, mis-escalation, stratum, context tier, coverage slice, frozen export. A sample is another try of the same case. No "part 2", no "v2 paper", no claims of novelty, no legal advice.

1. Generate figures with `dpdp-eval report figures` against the committed export and `claude-sonnet-5` cache. Adjudication figures come from the three-sample cache. The gate figure may regenerate from the existing five-sample gate cache. Keep the same six filenames unless a figure is dropped with a reason.
2. Rewrite `docs/writeup.md` against the new results: 350 locations, three samples, per-stratum / per-cell tables, retrieval-versus-reasoning split, Wilson intervals. Cite committed paths. Do not rewrite `archive/v1/docs/writeup.md`.
3. Rewrite the root README: pin permalink `7b659e8…`, 350 subjects / 350 locations, three samples per case on adjudication, updated test count. Keep the `archive/v1/` / `git checkout eval-v1.0.0` sentence. Do not change July 2026 post numbers.
4. Invert `test_archive_writeup_is_byte_identical_to_default_writeup` and `test_archive_figures_are_byte_identical_to_default_figures`. Archive files stay; they are no longer copies of the default path.
5. `ruff` + `pytest` green.

## CI expectations

No workflow edits. No pool generation. No live model. Offline suite only. Gate tests stay in the merge gate.

## Handoff

After Phase B the default tree is the coverage slice and `archive/v1/` plus `eval-v1.0.0` remain the 16-person / 34-location replay. A later post may cite the 350-case rates. That post is not this PR.

## Human actions

1. Before this PR merges: retarget the July 2026 post and the project-page writeup link from `blob/main/docs/writeup.md` to `blob/eval-v1.0.0/docs/writeup.md`. Do not change the post's rates or hosted figures.
2. Review Phase A on `feat/publish-coverage-slice` before starting Phase B.
3. Write Phase B (figures, writeup, README) on that branch.
4. Open the PR to `main`, confirm CI green, merge.
5. Keep `C:\dpdp-coverage-run` until the merge is on `origin`. Do not regenerate it.

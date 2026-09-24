# Prompt-Boundary Isolation

Close the two identifier leakage channels, rebind both cache keys to the rendered prompt, re-run the four
adjudication settings and the gate against opaque identifiers, and publish the coverage slice once — clean.
Per [`specs/010-prompt-boundary-isolation/spec.md`](../specs/010-prompt-boundary-isolation/spec.md) and
[ADR-0003](../docs/adr/0003-prompt-boundary-isolation.md).

**Prior:** `feat/publish-coverage-slice` is **unmerged** and sits at `0faee31`. `main` is still the
16-subject / 34-location paper at pin `3562059`. The coverage slice (350 / 350, pin `7b659e8…`) is complete
on the branch — harness, export, results, 4,650 cache entries, figures, rewritten writeup — and its numbers
are contaminated by design-cell names in case identifiers. **Nothing contaminated has been published.**
Tag `eval-v1.0.0` is on origin and `archive/v1/` holds the 16-subject snapshot.

This is **one pull request, two phases, with an operator run between them**. Do not merge between phases.
`main` must never show opaque-id gate results beside leaked-id adjudication results.

The contaminated run stays reachable at `c6b7f87` as the before/after baseline. It is a branch commit, not a
published result.

A **sample** is another try of the same case, not a new person.

---

## Goal

One published 350-case paper in which no design-cell name, label, or eval-only field ever reached a model.
Every headline rate re-measured against opaque identifiers. The delta against `c6b7f87` reported as a finding
about eval design.

## In scope / out of scope

**Phase A — in scope (mechanical session, no live calls)**

- Substitution primitive with collision guard, and its unit tests.
- Context builders emit opaque identifiers. T1 carries the opaque location-id list in the bundle.
- Retrieval-tool registry accepts and emits opaque identifiers.
- Both cache keys digest the rendered prompt.
- Gate prompt drops `case_id`.
- Token and cost capture on the live adapters.
- Re-seed `cache/primary/*` so the fake-seam CI path stays green offline.
- Prompt-level isolation tests over all 350 subjects and all 90 gate cases.
- Enumerate, by name, the live-role replay tests that go red pending the re-run.

**Phase B — in scope (writing session, same branch, after the run)**

- Copy the new cache and results onto the committed paths.
- Rebuild `cross-tier-comparison.json` and the retrieval split through the official CLI.
- Regenerate `docs/figures/`.
- Rewrite `docs/writeup.md` against the new numbers, with a methods section on the closed channels and a
  before/after delta table.
- Rewrite the root README (headline rates, pin, sample counts, test count — it is stale on all four today).
- Restore the live-role replay tests to green.

**Out of scope (both phases)**

- Editing `export/`, `PINNED_AGENT_SHA`, `manifest.yaml`, or either coverage hash. ADR-0001 stands.
- Regenerating the export or re-selecting the coverage slice. `scripts/regenerate_export.py` is not run.
- Agent-repository or generator changes.
- Editing `archive/v1/` or the `eval-v1.0.0` tag.
- Any metric definition, Wilson helper, scoring primitive, or report table shape.
- Prompt engineering. Wording, ordering, and the JSON output contract stay byte-stable apart from removing
  leaked tokens and substituting identifiers.
- Changing the 90 adversarial notes, their labels, or their families.
- The 6,450-case pool as a committed artifact.
- The blog post.

## Path decision

- **Branch.** Cut `feat/prompt-boundary-isolation` from `0faee31`. The coverage-slice commits are ancestors
  and travel with it; the new name describes what actually ships. Leave `feat/publish-coverage-slice` in
  place as the baseline pointer.
- **Substitution lives in `core/pseudonymize.py`**, imported by both `core/context/` and `core/tools/`. Not
  under `core/context/`, because the tool registry is not a context builder.
- **Token substitution, never field enumeration.** Eight field paths carry the cell name today, one nested
  (`parent_customer.customer_id`) and one a file path (`synthetic/gen-…-00008.pdf`). A field list is the
  failure mode being fixed. Walk every string value recursively and replace map keys as substrings, longest
  first.
- **T1 carries opaque location ids in the bundle.** Today `build_t1` returns `locations=[]` and
  `resolve_adjudication_location_ids` reaches into the export at prompt-render time to fill the
  `Required location_ids` line. Put `[{"location_id": <opaque>}]` in the bundle instead. This does not change
  what the model sees — it already saw those ids — it makes the bundle faithful and removes `export_dir`
  from the prompt path. That removal is what makes the next decision cheap.
- **Cache key signature is unchanged.** `make_cache_key(context=…, model_id, runner_id, case_id,
  sample_index)` keeps its parameters and internally digests `build_adjudication_prompt(...)`. Four
  production callers (`runners/spine.py`, `runners/autonomous/cache.py`, `report/figures/variance.py`,
  `report/retrieval_split.py`) and every test keep compiling. Do **not** thread a prompt string through call
  sites.
- **Gate key digests the rendered classification prompt**, replacing `prompt_hash({"text": text})`. This is
  the one place the old key would otherwise survive a prompt change and silently replay 450 contaminated
  responses. Verify the miss explicitly; see Phase A Task 8.
- **Verdicts translate opaque → real immediately after parsing**, before `runners/pairing.py`. Pairing,
  scoring, grouped tables, and the retrieval split then operate on real ids exactly as today.
- **Floors stay real.** `get_retention_floors` and `get_governance_map` outputs are verified clean; do not
  touch them. `report/retrieval_split.py` keys on `floor_ids` and needs no change.
- **Durable copy of this note:** `briefs/prompt-boundary-isolation.md`.

## Preconditions

Confirm all of the following. If any check fails, stop. Do not create the branch.

1. `git status` clean. `HEAD` is `0faee31` on `feat/publish-coverage-slice`.
2. `c6b7f87` exists and is an ancestor of `HEAD`.
3. `export/PINNED_AGENT_SHA` is `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`; `load_export` reports 350 / 350.
4. `cache/claude-sonnet-5/{t1,t2,t3,autonomous}/` hold 1,050 entries each;
   `cache/gemini-3.5-flash/adversarial_gate/` holds 450.
5. `specs/010-prompt-boundary-isolation/spec.md` and `docs/adr/0003-prompt-boundary-isolation.md` are
   committed.
6. `uv run pytest -q` is green at `HEAD` (384 passed, 1 skipped, 2 deselected).

## Git use (this branch only)

- `git checkout -b feat/prompt-boundary-isolation`
- Individual commits, one concern each. Short imperative subjects ending in a period. **No attribution
  footer of any kind.**
- Never commit to `main`. Never merge, rebase, rewrite history, force-push, or tag. Opening the PR and
  merging are human actions after Phase B.
- If the suite fails for a reason not listed in Phase A Task 9, do not commit; fix or stop and surface.

## Phase A

### Task 1: Substitution primitive

New `core/pseudonymize.py`. Tests first, under `tests/core/test_acceptance_pseudonymize.py`.

1. `opaque_case_id(subject_id) -> "case-" + sha256(subject_id).hexdigest()[:12]`
2. `opaque_location_id(location_id) -> "loc-" + sha256(location_id).hexdigest()[:12]`
3. `build_substitution_map(subject) -> dict[str, str]` covering the subject id and every location id.
4. `substitute(payload, mapping)` — recursive over dicts, lists, and nested models; replaces map keys as
   substrings in every string value, **longest key first**.
5. `invert(mapping) -> dict[str, str]` for verdict translation.

Hard requirements: pure function of the input, no RNG, no salt, no `PYTHONHASHSEED` dependence, no map file
on disk. Two distinct ids mapping to one token raises; it does not warn or overwrite.

### Task 2: Context builders

`core/context/tiers.py`:

- `build_t1` returns `locations=[{"location_id": <opaque>} for each location]`. Request fields substituted.
- `build_t2` / `build_t3` substitute the whole location payload after the existing
  `_EVAL_ONLY_LOCATION_FIELDS` scrub. Keep that scrub; it is correct and still required.
- Rules corpora pass through untouched.

`core/model/adapter_common.py`: `resolve_adjudication_location_ids` reads the ids from the bundle for all
tiers and no longer loads the export. Drop the `export_dir` parameter and its call sites once nothing needs
it.

### Task 3: Retrieval-tool registry

`core/tools/registry.py` and `core/tools/location_records.py`:

- `RetrievalToolRegistry` precomputes `{opaque_case_id(s.subject_id): s.subject_id for s in bundle.subjects}`.
- `get_location_records` accepts the opaque id, resolves it, and substitutes its returned payload. An
  unknown id, or a real id passed where an opaque one is expected, raises. It never returns an empty result
  silently.
- `get_retention_floors` and `get_governance_map` are untouched.
- `summarize_tool_result` will now record opaque ids in traces. Expected; no change needed there.

### Task 4: Cache keys

`core/cache/store.py`: `make_cache_key` digests the rendered adjudication prompt instead of the
`ContextBundle`. Signature unchanged (see Path decision).

`runners/adversarial_gate/cache.py`: `make_gate_cache_key` digests the rendered classification prompt
instead of `{"text": text}`.

### Task 5: Gate prompt

`core/model/adapter_common.py`: `build_classification_prompt` drops the `case_id` line entirely.
`classify_note` keeps `case_id` in its signature for cache addressing and error messages only.

### Task 6: Verdict translation

Translate opaque location ids back to real ids immediately after parsing a model or cache response, before
`runners/pairing.py` sees them. Apply in `runners/spine.py` and `runners/autonomous/cache.py`. Everything
downstream — pairing, scoring, grouped tables, retrieval split — is unchanged.

### Task 7: Token and cost capture

Record per-call input and output token counts on the live adapters and persist them on the cache entry. Do
not add a pricing table; counts only. Offline replay must not require the field to be present on legacy
entries.

### Task 8: Isolation tests

New `tests/core/test_acceptance_prompt_isolation.py` and additions under `tests/gate/`.

1. For all **350** subjects and all four settings, the rendered prompt contains no export `cell_id` as a
   substring, and no `expected` / `strata` / `cell_id` key.
2. For all **90** gate cases, the rendered prompt contains no case id, no `adv` / `benign` identifier prefix,
   and no `label` or `family`.
3. A synthetic location payload with a newly added string field embedding a subject or location id is
   substituted, with that field named nowhere in harness code.
4. Round-trip: opaque verdicts from a fake seam translate back to exact real ids; pairing yields the same
   pairs as before the change on the same fixture.
5. Collision guard raises.
6. One byte changed in rendered prompt text changes the key — asserted on both key builders.
7. **A cache entry written under a pre-change key is a miss under the new key, offline, for both
   adjudication and gate.** This encodes the stale-replay hazard and is the single most important test in
   this feature.
8. `get_location_records` with an opaque id returns the right subject with every identifier opaque; with a
   real or unknown id, raises.
9. Floor ids and governance categories are byte-identical before and after substitution.

Also update the two tests that permitted the leak, rather than deleting them:

- `tests/gate/test_acceptance_label_isolation.py` — the `set(call.keys()) <= {"text", "case_id"}` assertion
  stays, but a new assertion forbids `case_id` from reaching the prompt.
- `tests/autonomous/test_acceptance_autonomous_label_isolation.py` — keep the `ContextBundle` assertions and
  add the prompt-level equivalents.

### Task 9: Re-seed the primary cache and enumerate expected-red tests

Re-seed `cache/primary/{t1,t2,t3,autonomous}/` and `cache/primary/adversarial_gate/` against the new keys
with `scripts/seed_runner_cache.py` and `scripts/reseed_frozen_gate_cache.py`, so the fake-seam CI path is
green with no provider key.

Then run the full suite and record, **by name and with its failure line**, every test that fails only
because a live-role cache entry now misses. Expected members of that set, to be confirmed rather than
assumed:

- `tests/runners/test_acceptance_live_role_t2_replay.py`
- `tests/autonomous/test_acceptance_live_role_autonomous_replay.py`
- `tests/gate/test_acceptance_live_role_gate_replay.py`
- `tests/cli/test_acceptance_cli_live_roles.py`
- `tests/report/test_acceptance_retrieval_split.py` (committed-cache path)
- `tests/gate/test_acceptance_gate_cache_offline.py`
- `tests/autonomous/test_acceptance_autonomous_cache_offline.py`

Write that list into the pull request description. Do not delete, skip, or `xfail` any of them — they are the
proof the cache was genuinely invalidated, and Phase B turns them green.

## Phase A stop

Do not run a live model. Do not touch `docs/writeup.md`, `docs/figures/`, the README, `results/`, or
`cache/claude-sonnet-5/` and `cache/gemini-3.5-flash/`. Do not generate figures "to see how they look."

Phase A is done when the suite is green except the enumerated live-role tests, and the paper files are
untouched.

## Phase A acceptance

- [ ] `core/pseudonymize.py` exists; substitution is recursive, longest-key-first, collision-guarded, deterministic across processes
- [ ] All 350 subjects × 4 settings: no `cell_id` substring in any rendered prompt
- [ ] All 90 gate cases: no case id, no `adv` / `benign` prefix in any rendered prompt
- [ ] T1 bundle carries opaque location ids; `resolve_adjudication_location_ids` no longer loads the export
- [ ] Both cache keys digest the rendered prompt; `make_cache_key` signature unchanged
- [ ] Pre-change cache entries miss under the new keys, adjudication **and** gate
- [ ] `get_location_records` resolves opaque ids and raises on real or unknown ids
- [ ] Floor ids and governance categories byte-identical after substitution
- [ ] Verdicts translate back to real ids; pairing output unchanged on the same fixture
- [ ] Token / cost capture recorded on live adapters; offline replay tolerates its absence
- [ ] `cache/primary/*` re-seeded; CI path green without a provider key
- [ ] Expected-red live-role tests enumerated by name in the PR description; none skipped or deleted
- [ ] `export/`, `PINNED_AGENT_SHA`, `manifest.yaml`, both coverage hashes, `archive/v1/` unchanged
- [ ] `ruff` clean; no workflow edits; no live model call

## The live re-run

Between the phases, per [`briefs/live-rerun-opaque-ids.md`](./live-rerun-opaque-ids.md). Operator session,
side directory, no git writes, run from the Phase A commit of this branch. Gate first (450 calls), then the
four adjudication settings (4,200 calls plus autonomous tool rounds). Do not start Phase B until the offline
twins match.

## Phase B

Same branch, one sitting, after the run.

1. Copy the new cache onto `cache/claude-sonnet-5/{t1,t2,t3,autonomous}/` and
   `cache/gemini-3.5-flash/adversarial_gate/`. Copy the new results onto `results/`.
2. Rebuild `cross-tier-comparison.json` from the four offline sweeps at sample 0, and emit the retrieval
   split through `dpdp-eval autonomous-retrieval-split`.
3. Regenerate `docs/figures/` with `dpdp-eval report figures`. Same six filenames.
4. Rewrite `docs/writeup.md`. It must carry, beyond the new numbers:
   - a methods paragraph stating that identifiers crossing the seam are opaque and that the invariant is
     asserted on the rendered prompt over all 350 cases;
   - a before/after delta table against `c6b7f87` on every headline rate;
   - the honest reading of §4 — the retrieval bucket is unreachable while `get_retention_floors` returns the
     full corpus in one call and every session calls all three tools, so the split shows that no error is
     explained by a missing fetch, not that it discriminated;
   - the inference regime: zero-shot, `thinking` disabled on the adjudication role, `max_tokens=4096`, one
     shared prompt template across all four settings;
   - the coverage slice read as design-weighted rather than representative, and the `split` stratum noted as
     confounded with `floor_set` (eval is exactly the five securities cells).
5. Rewrite the root README. It is stale on the headline table, subject and location counts, the five-sample
   claim, pin `3562059`, the `txn-016` narrative, and the test count in three places.
6. Restore the enumerated live-role replay tests to green against the new cache.

## Phase B acceptance

- [ ] Adjudication and gate results embed the new cache; live/offline pairs differ only in `cache_mode`
- [ ] `dpdp-eval` offline replay reproduces every committed results file with no provider key
- [ ] Figures regenerated; six filenames; no stale `N=5` or leaked-id text
- [ ] Writeup carries the isolation methods paragraph, the delta table, and the four framing corrections
- [ ] README consistent with the new numbers, pin, sample count, and test count
- [ ] Every live-role replay test green; none skipped
- [ ] `ruff` + `pytest` fully green
- [ ] `archive/v1/`, `eval-v1.0.0`, and `export/` untouched

## CI expectations

No workflow edits. No pool generation. No live model. Offline suite only. Gate tests stay in the merge gate.

## Handoff

After Phase B the default tree is the coverage slice measured under opaque identifiers, `archive/v1/` plus
`eval-v1.0.0` remain the 16-subject replay, and `c6b7f87` remains the contaminated baseline for the delta.
The blog post is a later, separate piece of work.

## Human actions

1. Review Phase A on `feat/prompt-boundary-isolation` before authorising the live run.
2. Read the cost table in the run brief before any refresh.
3. Run the live re-run session.
4. Review Phase B.
5. Open the PR to `main`, confirm CI green, merge.
6. Tag the merge commit. Decide the tag name at that point; the contaminated baseline stays reachable at
   `c6b7f87` regardless.

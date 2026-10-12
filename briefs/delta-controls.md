# Paired Test and Two Live Controls

Three checks on the before/after delta in `docs/writeup.md` §6, each replacing a hedge with a result. One is
offline and two are live. The expected outcomes and the reading of each result are fixed here, before any
data is read or any provider is called.

**Prior:** `main` at `a0ce6f2e`. The clean run is published at `eval-v2.0.0`. The leaked baseline is kept at
tag `baseline-leaked-ids` (`c6b7f87`); its cache and results are not on `main`. The export is the same at
both tags (pin `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`, 350 / 350).

A **sample** is another try of the same case, not a new person.

---

## Hedges this replaces

| Where | Current text |
|---|---|
| Writeup §6, "The delta" | "A three-sample spread is a rough yardstick, and no significance test is claimed." |
| Writeup §8 | "no significance claims are made" |
| Writeup §2 and §8 | a provider-side change between the runs "cannot be ruled out" / "nothing in the data can separate it out" |
| Writeup §2, "Identifier isolation" | at T1 the clean prompt lists the location under `locations` (`{"location_id": token}`); the leaked prompt had `"locations": []` |

## Hard rules

- **No control writes into the committed `cache/`.** Each live control gets its own fresh, empty root under
  `cache-controls/`. The published replay stays byte-identical; `git diff --stat main -- cache results/*-offline.json results/gate-*.json` must be empty at the end.
- `build_t1`, `build_adjudication_prompt` and every default code path stay unchanged.
- No live call before this brief is committed and the operator has confirmed.

---

## A1. Paired test per setting (offline, free)

**Question.** For each setting, is the change from the leaked baseline to the clean run larger than chance,
case by case?

**Data.** The first-try (sample 0) verdict per case at both tags, matched by real case id. The clean run's
entries are in `cache/claude-sonnet-5/<tier>/` on `main`. The leaked baseline's entries exist only at tag
`baseline-leaked-ids`; they are extracted with `git archive` into a committed per-case table,
`results/baseline-leaked-first-try.json`, which records its tag, commit and source paths. Every case has
exactly one prompt-hash directory at each tag. Per-case error flags use `core.scoring.adjudication.score_adjudication`
on the single pair, so the definitions are the published ones.

**Self-check.** The per-case flags must sum to the published first-try numerators at both tags (for
example T1 over-erasure 88 and 224). The script fails otherwise.

**Test.** Exact two-sided McNemar on the discordant pairs (binomial, p = 0.5), per setting, for over-erasure
and mis-escalation: 8 tests, Holm-corrected as one family. Reported separately and not in the family: the
gate, original run against the clean run, first try, attack notes caught (detection).

**Expected outcome.**
- Significant after Holm: T1 over-erasure (88 → 224), T1 mis-escalation (149 → 74), T3 mis-escalation
  (42 → 78), autonomous over-erasure (66 → 41) and autonomous mis-escalation (29 → 80).
- Possibly not significant: T2 over-erasure (129 → 142), T2 mis-escalation (99 → 119), T3 over-erasure
  (53 → 59). Over-retention is too rare to test and is not in the family.
- Gate: 5 notes caught → missed, 0 missed → caught, so exact p = 0.0625. **Not significant on the first try
  alone.** Stated now so the result cannot be reframed after the fact.

**Deliverables.** `report/paired_delta.py` (pure functions, no I/O beyond reading cache trees), a test,
`results/baseline-leaked-first-try.json`, `results/paired-delta.json`, and the writeup §6 and §8 sentences.

## A2. Provider-drift control (live)

**Question.** Did the provider change what sits behind the model ids between the leaked baseline and the
clean run?

**Method.** A separate `git worktree` at `baseline-leaked-ids` with its own `uv sync`, so the old prompt
builder and the old key are used. From the worktree root (its relative `export/` is the same 350-case
export), with `CACHE_MODE=refresh` and a fresh, empty `--cache-root`:
- T1, 350 × 3, `MODEL_ID=claude-sonnet-5`;
- the gate, 90 × 5, `MODEL_ID=gemini-3.5-flash`.

This re-sends exactly the old leaked prompts today. The cache is copied to `cache-controls/drift/` on the
branch; a test re-scores it from the raw entries against the export and the gate fixture.

**Compare against the recorded per-try spread** (rates and spreads, not single answers):
T1 over-erasure 88, 89, 94; T1 mis-escalation 149, 155, 148; gate detection 44 or 45 of 45 on every try.
Secondary: per-case agreement between the recorded first try and the re-sent first try, against the
agreement between two recorded tries of the leaked baseline.

**Pre-registered reading.**
- **No evidence of drift** if every re-sent try's T1 over-erasure is in 78 to 104, its mis-escalation in 138
  to 165 (the recorded range widened by 10 each side), and gate detection is at least 42 of 45 on every try.
- **Partial drift** if the re-sent numbers fall outside that band *toward* the clean run (over-erasure up,
  mis-escalation down, gate detection down). The writeup must then say that part of the change is the
  provider, with the size.
- **Other** (outside the band, away from the clean run): reported as found, without a reading.

**Limitation stated up front.** This covers T1 and the gate only. T2, T3 and the autonomous setting are
not re-sent. A change and a revert inside the window would also escape it.

## A3. T1 location-entry control (live)

**Question.** Does the bare `{"location_id": token}` entry, which the clean T1 prompt has and the leaked one
didn't, change the model's behaviour?

**Method.** `scripts/control_t1_empty_locations.py` renders the clean (opaque-id) T1 prompt with
`"locations": []` while keeping the token on the `Required location_ids` line, sends it through a subclass
of the live Anthropic adapter, and scores against that token. The default builder can't be used: the clean
prompt builder and the spine both read the required ids from `context.locations`, so emptying the list
would drop the line too. A test checks that the control prompt equals the default T1 prompt with only the
`locations` array emptied. 350 × 3 into `cache-controls/t1-empty-locations/`; the script replays offline
from that root.

**Compare against the clean run's T1 spread:** over-erasure 224, 221, 225; mis-escalation 74, 81, 83;
first-try verdict mix 296 erase, 54 escalate, 0 retain.

**Pre-registered reading.**
- **The entry doesn't matter** if every try's over-erasure is in 211 to 235 and mis-escalation in 64 to 93
  (the clean range widened by 10 each side). The location-entry caveat becomes one clause.
- Outside that band, the writeup reports how much of the T1 shift comes from the entry.

## Cost (estimate before running)

At the writeup's list prices ($2 / $10 per million input / output tokens for `claude-sonnet-5`, $1.50 / $9.00
for `gemini-3.5-flash`), scaled from the clean run's recorded tokens:

| Control | Calls | Estimate |
|---|---|---|
| A2 T1 (leaked prompts) | 1,050 | about $0.95 (slightly shorter prompt than the clean run's $0.99) |
| A2 gate | 450 | about $0.61 (mostly thinking tokens, so it varies) |
| A3 T1 (empty list) | 1,050 | about $0.99 |
| **Total** | **2,550** | **about $2.55; ceiling $5** |

The code at `baseline-leaked-ids` does not record token usage in its cache entries, so A2's actual cost is
estimated from the per-call token means of the matching clean sweep. A3's is summed exactly from its cache.
Actuals are recorded below after the run.

## Acceptance

- [ ] Brief committed before any live call
- [ ] A1: self-check passes at both tags; `results/paired-delta.json` committed; test green
- [ ] A2: 1,050 T1 and 450 gate entries under `cache-controls/drift/`, written by the code at `baseline-leaked-ids`; reading applied as pre-registered
- [ ] A3: 1,050 entries under `cache-controls/t1-empty-locations/`; offline replay reproduces the results JSON; reading applied as pre-registered
- [ ] Committed `cache/`, `export/` and the published results unchanged
- [ ] Writeup §2, §6 and §8 updated; actual cost recorded here
- [ ] CI green on the PR and on `main`; tag `eval-v2.1.0` on the merge commit

## Results

Recorded after the run. Readings are applied as pre-registered above.

**A1 (offline).** As expected. Significant after Holm: T1 over-erasure (16 vs 152 discordant), T1
mis-escalation (124 vs 49), T3 mis-escalation (26 vs 62), autonomous over-erasure (30 vs 5) and autonomous
mis-escalation (14 vs 65); all adjusted p < 0.001. Not significant: T2 over-erasure (adjusted p 0.43), T2
mis-escalation (0.29), T3 over-erasure (0.43). Gate: 5 caught → missed, 0 the other way, exact p = 0.0625.
`results/paired-delta.json`.

**A2 (live).** No evidence of drift; every value is inside the band. T1 re-sent per try: over-erasure 90,
90, 87 (recorded 88, 89, 94); mis-escalation 150, 152, 150 (recorded 149, 155, 148); first-try mix 159
erase, 176 escalate, 15 retain (recorded 159, 177, 14). Per-case agreement with the recorded first try
92.9%, against 92.3% to 93.7% between two recorded tries. Gate re-sent: 45, 44, 45, 45, 45 of 45, no
false alarms. Prompt hashes equal the committed ones at `baseline-leaked-ids`. The gate sweep stopped once
(after 113 entries) on a response with no JSON object and was resumed against the same cache, as
`briefs/live-rerun-opaque-ids.md` prescribes. `results/control-provider-drift.json`.

**A3 (live).** Outside the band, in the opposite direction from the clean run. With `"locations": []`,
per try: over-erasure 1, 1, 0; mis-escalation 321, 323, 322; first-try mix 1 erase, 349 escalate, 0
retain (clean run with the entry: 296 erase, 54 escalate). All 28 uncomputable cases are escalated
(clean run: 4 escalated, 24 erased), and `gen-uncomputable_kyc-00023` is escalated on all three tries.
So most of the T1 shift between the leaked baseline and the clean run comes from the location entry, not
from the ids. Like for like (empty list in both), removing the cell names moves T1 from 177 escalate / 159
erase / 14 retain to 349 escalate / 1 erase. Two diagnostic calls with the raw text kept reproduced the
effect on one case (erase with the entry, escalate without); the model returns JSON only.
`results/control-t1-empty-locations.json`.

Correction to "Hedges this replaces": the last row is not writeup text; the writeup never mentioned the
location entry.

**Actual cost.** A3 $1.08 (1,050 calls; 234,990 input and 61,199 output tokens, exact). A2 about $1.60
(1,050 + 450 calls, estimated from the clean run's per-call token means; the old code records no usage),
plus one failed gate call and two diagnostic calls, under $0.01. Total about $2.69 against a $5 ceiling.

**Open.** How the writeup (§3, §6, §7, README) states the T1 result given A3 is decided in the next
session; nothing about T1 has been rewritten yet.

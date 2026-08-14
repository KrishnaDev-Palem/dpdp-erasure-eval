# Per-stratum Rates and Three-Sample Adjudication

The coverage-slice adapter stores `strata` and `cell_id` on loaded locations. Scoring, reports, and the T1/T2/T3/autonomous runners still treat every location as one undifferentiated pool and still require five samples. This change carries those tags through scoring and reporting, and lets the four adjudication runners run three samples without touching the adversarial gate.

A **sample** is another try of the same case, not a new person.

## Goal

Report the three standalone adjudication rates (over-erasure, over-retention, mis-escalation) per `cell_id` and per locked `strata` field, with the same Wilson intervals the aggregate tables already use. Allow T1, T2, T3, and autonomous to run with sample indices `[0, 1, 2]` while the gate remains five samples (`[0, 1, 2, 3, 4]`). Default adjudication replay of the committed export stays at five samples so existing offline tests stay green.

## In scope / out of scope

**In scope**

- Group scored location pairs by `cell_id` and by each export-schema `1.0.0` `strata` field (`entity_type`, `floor_set`, `collision_arity`, `anchor_computable`, `boundary_flag`, `trigger_shape`, `re_engagement`, `split`). Read `split`; do not re-derive it.
- Reuse `score_adjudication` on each group. Do not invent a second definition of the three rates.
- Attach those grouped rates to the existing tier / autonomous report tables, with Wilson 95% intervals from `report/wilson.py`.
- Human-readable report prints the per-cell and per-stratum tables when any scored location carries `strata`.
- T1 / T2 / T3 / autonomous accept sample indices `[0, 1, 2]` or `[0, 1, 2, 3, 4]`. Variance summaries follow whatever length was run.
- Adversarial gate stays exactly five samples. Gate types, runner, cache, and tests are unchanged.
- Strip eval-only fields (`expected`, `strata`, `cell_id`) from T2/T3 context bundles and from the autonomous initial context. `parent_customer` and `latest_txn_date` stay — those are facts the oracle used, not labels.
- Tests on a small synthetic fixture of agent-shaped cases (the adapter fixture is enough). Committed 16-person / 34-location export continues to produce the existing aggregate tables; grouped tables are omitted or empty when `strata` is absent.

**Out of scope**

- Replacing committed `export/adjudication/subjects.yaml` or flipping `PINNED_AGENT_SHA`
- Archiving `results/` or rewriting README / `docs/writeup.md`
- New or regenerated figures
- Live model calls
- Gate fixture, gate runner, gate cache, 90 notes
- Committing the 6,450-case pool
- Engine / generator / agent-repository changes
- Multi-location subjects
- Training

## Path decision

- Keep the existing tree. No new top-level package.
- Grouping helper beside the existing scorer: `core/scoring/adjudication.py`. Aggregate `score_adjudication` and `AdjudicationScoringResult` stay the pairwise contract they are today.
- Pairing still returns `(ModelVerdict, ExpectedLabel)` by `location_id`. Join back to `LabeledLocation.strata` / `cell_id` from the loaded export; do not put `strata` inside `ExpectedLabel`.
- Report types and formatters in `report/adjudication_types.py` and `report/adjudication_tables.py`. Extend `TierAdjudicationReportTables`; do not add a second report entrypoint.
- Sample-count relaxation only on `runners/types.py` (`SweepConfig`, `TierSweepResult`) and `runners/autonomous/types.py`. Leave `runners/adversarial_gate/types.py` requiring `[0, 1, 2, 3, 4]`.
- Context stripping in `core/context/tiers.py` (and the autonomous initial-context builder if it dumps locations the same way). Isolation tests under `tests/runners/` and `tests/autonomous/`.
- Contract note on `specs/001-shared-core/contracts/scoring.md` (grouped rates) and the sweep-result contracts (sample list length 3 or 5 for adjudication only).
- CLI: optional `--samples 3` (or equivalent) on `t1` / `t2` / `t3` / `autonomous` only. Gate rejects it. Default remains 5. `--sample-index` must fall inside the run that actually executed.
- Durable copy of this note: `briefs/per-stratum-rates.md`.

## Acceptance

- [ ] Grouped rates equal a hand-scored partition of the same pairs through `score_adjudication`
- [ ] `cell_id` and every locked `strata` field appear as grouping keys; `split` is copied from the case
- [ ] v1 export (no `strata`) still loads; aggregate tables unchanged; grouped tables omitted or empty
- [ ] Coverage-shaped fixture produces per-cell and per-stratum rows; missing `strata` on an agent-shaped case still fails closed at load time
- [ ] T2/T3 and autonomous context dumps contain neither `expected` nor `strata` nor `cell_id`
- [ ] Adjudication runners accept `[0, 1, 2]` and `[0, 1, 2, 3, 4]`; default offline sweep against the committed export is still five samples
- [ ] Gate config and result validators still require exactly five samples
- [ ] Existing export, provenance, runner, gate, and report tests that use the committed export stay green
- [ ] `ruff` + `pytest` green; no workflow edits

## CI expectations

No workflow edits. No pool generation. No live model. Offline suite only.

## Handoff

After this lands, the next evaluation-repository change archives the 16-person / 34-location `results/` and writeup tables, regenerates the committed export from agent tag `export-v1.1.0`, and flips `PINNED_AGENT_SHA`. Live adjudication against the 350-case coverage slice, and the writeup revision that cites per-stratum rates, wait on that re-pin.

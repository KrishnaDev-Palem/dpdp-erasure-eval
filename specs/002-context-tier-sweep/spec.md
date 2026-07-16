# Feature Specification: Context-Tier Adjudication Sweep

**Feature Branch**: `002-context-tier-sweep`

**Created**: 2026-07-02

**Status**: Accepted

**Input**: User description: "Build T1, T2, and T3 adjudication runners that sweep all labeled subjects from the committed frozen export. Each runner loads export via core.export, builds tier-appropriate context via core.context (build_t1/t2/t3), obtains model verdicts via the injected ModelSeam (offline cache replay by default; refresh opt-in), pairs predictions with ground truth from expected blocks only, and aggregates results via core.scoring.score_adjudication. Support N=5 samples per case (sample_index 0–4) using cache keys with runner_id t1|t2|t3."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Full T1 Request-Only Sweep (Priority: P1)

An evaluator measuring how a model adjudicates erasure requests with minimal context needs a T1 runner that sweeps every labeled subject in the committed frozen export. For each subject, the runner assembles request-only context (no records, no retention-floor rules), obtains per-location model verdicts, aligns each prediction with the ground-truth label from that location's `expected` block, and aggregates adjudication metrics across the full sweep.

**Why this priority**: T1 is the baseline ablation tier. Without a complete, reproducible T1 sweep, the context-tier comparison the harness exists to produce cannot begin.

**Independent Test**: Run the T1 runner against the committed export in offline mode with a test double or committed cache entries; verify every export subject is visited, every location is graded against `expected` only, and aggregate metrics include a per-lane confusion matrix plus standalone over-erasure, over-retention, and mis-escalation rates — with no blended accuracy.

**Acceptance Scenarios**:

1. **Given** the committed frozen export and offline cache mode, **When** the T1 runner completes a sweep, **Then** every labeled subject in the export is processed and no live model credentials are required.
2. **Given** a subject with multiple locations, **When** the T1 runner grades results, **Then** each model verdict is paired with ground truth by `location_id` and scoring uses only fields from the location's `expected` block.
3. **Given** assembled T1 context for any subject, **When** the model is invoked, **Then** the context bundle contains the erasure request alone and never includes `expected` labels or retention-floor rule text.
4. **Given** a completed T1 sweep, **When** aggregate results are inspected, **Then** the output includes a per-lane confusion matrix and standalone over-erasure, over-retention, and mis-escalation rates with no single blended accuracy figure.
5. **Given** a subject with an empty `locations` list, **When** any tier runner sweeps that subject, **Then** the subject is visited, contributes zero location pairs, and the sweep continues without inventing records or calling the model.

---

### User Story 2 - Run T2 and T3 Tier Sweeps with Shared Spine (Priority: P1)

An evaluator comparing context tiers needs T2 (records-augmented) and T3 (rule-augmented) runners that reuse the same orchestration spine as T1 but assemble tier-appropriate context. T2 adds Data Principal locations and raw business fields; T3 adds retention-floor rule text and the governance map. Each tier sweeps all export subjects, grades per location against ground truth, and produces the same aggregate metric shape as T1.

**Why this priority**: The thesis depends on isolating exactly one context variable between adjacent tiers. T2 and T3 complete the ablation ladder T1 starts.

**Independent Test**: Run T2 and T3 runners offline on the committed export; verify context inclusion matches the context-tier contract, `runner_id` values are `t2` and `t3` respectively for cache lookup, and aggregate scoring matches the adjudication scoring contract.

**Acceptance Scenarios**:

1. **Given** the same subject, **When** T2 context is assembled, **Then** the bundle includes request plus location records with business fields and excludes retention-floor rule text and `expected` labels.
2. **Given** the same subject, **When** T3 context is assembled, **Then** the bundle includes everything in T2 plus the full rules corpus (five sectoral floors and governance map) and still excludes `expected` labels.
3. **Given** offline mode, **When** T2 or T3 runners execute a full sweep, **Then** cache lookups use `runner_id` of `t2` or `t3` respectively and replay committed entries without live model calls.
4. **Given** completed T2 and T3 sweeps, **When** results are compared to T1, **Then** each tier reports its own confusion matrix and standalone rates independently (metrics are not merged across tiers).

---

### User Story 3 - Sample N=5 and Report Cross-Sample Variance (Priority: P2)

An evaluator assessing model non-determinism needs each tier runner to execute the full subject sweep at five independent samples (`sample_index` 0 through 4). For each sample, the runner replays or records model responses under distinct cache keys, produces a complete aggregate adjudication result for that sample, and summarizes how key safety rates vary across the five samples.

**Why this priority**: N=5 sampling is a planning guardrail for bounded cost while still exposing variance. Runners are the first place full sweep variance is exercised end-to-end.

**Independent Test**: Seed committed cache entries for all five sample indices for at least one subject and tier; run the tier runner offline; verify five per-sample scoring results are produced and a variance summary reports whether over-erasure, over-retention, and mis-escalation rates differ across samples.

**Acceptance Scenarios**:

1. **Given** a tier runner sweep, **When** model responses are requested for a case, **Then** cache keys distinguish `sample_index` values 0, 1, 2, 3, and 4 for that tier's `runner_id`.
2. **Given** five completed samples for a tier sweep, **When** runner output is inspected, **Then** it includes one aggregate adjudication scoring result per sample (five total), each covering all locations across all subjects in the sweep.
3. **Given** five per-sample scoring results, **When** the variance summary is inspected, **Then** it reports, for each standalone rate (over-erasure, over-retention, mis-escalation), the value at each sample index and whether the rate is identical across all five samples.
4. **Given** offline mode and a missing cache entry for any required sample index, **When** the sweep runs, **Then** the runner fails clearly at the miss rather than silently substituting another sample or calling a live model.

---

### User Story 4 - Acceptance Suite Defines Done Before Implementation (Priority: P2)

A reviewer merging the feature needs a runners acceptance suite written before implementation lands, failing for the right reason initially and passing when all three tier runners satisfy the contracts. The suite runs fully offline in continuous integration without a model API key.

**Why this priority**: Constitution Principle II requires evidentiary runner behavior to be contract-defined and test-gated before code ships.

**Independent Test**: Run the runners acceptance suite in offline mode on a clean clone; all tests pass with no network access and no secrets.

**Acceptance Scenarios**:

1. **Given** the feature branch before runner implementation, **When** the acceptance suite is executed, **Then** relevant tests fail because runner behavior is not yet present (not because of unrelated setup errors).
2. **Given** completed runner implementation, **When** the full runners acceptance suite runs with `CACHE_MODE=offline` and no model API key, **Then** all tests pass.
3. **Given** acceptance tests for ground-truth isolation, **When** any tier runner builds context, **Then** tests assert that `expected` fields never appear in model-facing bundles.
4. **Given** acceptance tests for configuration discipline, **When** runners initialize, **Then** model identity and cache mode are read from environment configuration, not embedded as fixed literals in runner logic.

---

### User Story 5 - Validate Runners via Quickstart Guide (Priority: P3)

An evaluator onboarding to the harness needs a quickstart document that walks through reproducing a green offline T1/T2/T3 sweep from a clone, mirroring what continuous integration verifies.

**Why this priority**: Reproducibility requires a human-readable path, not only automated tests.

**Independent Test**: Follow the quickstart on a clean clone without an API key; confirm all three tier sweeps replay from committed cache and the acceptance suite is green.

**Acceptance Scenarios**:

1. **Given** the feature quickstart guide, **When** an evaluator follows setup and offline sweep steps, **Then** they can run all three tier sweeps without live model credentials.
2. **Given** the quickstart lint and test commands, **When** executed locally, **Then** outcomes match the continuous integration merge gate expectations for this feature.

---

### Edge Cases

- What happens when provenance verification fails at export load? The sweep does not start; the runner surfaces the provenance error from the shared export loader.
- What happens when a subject has no locations? All tiers visit the subject. Context builders return an empty `locations` list per the context-tier contract (no fabricated records). The spine appends zero location pairs, skips model/cache invocation for that subject, and continues the sweep without failing.
- What happens when the model returns a verdict outside {erase, retain, escalate}? The runner raises a validation error naming `subject_id`, `location_id`, and `sample_index`; it does not coerce the verdict into a lane.
- What happens when only some of the five sample indices have committed cache entries in offline mode? The sweep fails at the first cache miss with an explicit error identifying case, tier, and sample index.
- What happens when `CACHE_MODE=refresh` and credentials are present? The runner may fetch and persist new cache entries per the shared cache contract; default and CI behavior remain offline replay.
- What happens when two tier sweeps run sequentially? Each tier produces independent results keyed by its own `runner_id`; tiers do not share or overwrite one another's cache namespace.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST provide three adjudication runners — T1 (request-only), T2 (records-augmented), and T3 (rule-augmented) — that sweep all labeled subjects from the committed frozen export.
- **FR-002**: All runners MUST load the export through the shared export loader and MUST NOT read ground truth from any source other than each location's `expected` block.
- **FR-003**: Runners MUST assemble model-facing context exclusively through the shared tier builders (`build_t1`, `build_t2`, `build_t3`) and MUST NOT include `expected` labels in context passed to the model.
- **FR-004**: Runners MUST obtain per-location model verdicts through an injected model seam; runner logic MUST NOT hardcode a model provider or model identity.
- **FR-005**: Model identity (`MODEL_ID`) and cache mode (`CACHE_MODE`) MUST be read from environment configuration at runner initialization.
- **FR-006**: Default execution MUST replay model responses from the committed cache in offline mode; continuous integration MUST run without a model API key.
- **FR-007**: An explicit refresh path MUST remain available when cache mode is set to refresh and credentials are present, delegating to the shared cache contract.
- **FR-008**: Cache lookups for tier runners MUST use `runner_id` values `t1`, `t2`, and `t3` respectively, consistent with the cache contract.
- **FR-009**: Each runner MUST request model responses at five samples per case (`sample_index` 0 through 4), producing distinct cache keys per sample.
- **FR-010**: For each sample index, a runner MUST aggregate all per-location prediction pairs across the full subject sweep into one adjudication scoring result via the shared scoring primitive.
- **FR-011**: Runner output for each tier MUST include five per-sample aggregate scoring results plus a variance summary that lists each standalone rate (over-erasure, over-retention, mis-escalation) at every sample index and indicates whether that rate is constant across all five samples.
- **FR-012**: Per-location grading MUST align predictions to ground truth by `location_id`; locations present in context but missing from model output MUST fail validation rather than being silently dropped.
- **FR-013**: Aggregate metrics MUST include a per-lane confusion matrix and standalone over-erasure, over-retention, and mis-escalation rates; blended accuracy MUST NOT be produced or implied.
- **FR-014**: T1, T2, and T3 runners MUST share a common orchestration spine (export load, subject iteration, context build, model invocation, pairing, scoring) with only tier-specific context assembly and `runner_id` differing.
- **FR-015**: A runners acceptance suite MUST exist under the repository test layout for this feature, written before implementation, and MUST pass fully offline when the feature is complete.
- **FR-016**: A feature quickstart guide MUST document clone-and-run steps to reproduce green offline T1/T2/T3 sweeps and the runners acceptance suite locally.
- **FR-017**: Vocabulary in runner-facing artifacts MUST use developer-facing tier labels (T1/T2/T3) and DPDP domain terms; `subject_id` MUST remain the export field name.
- **FR-018**: Work MUST land on feature branch `002-context-tier-sweep`; the agent MAY commit to the feature branch but MUST NOT merge to `main` (human merge gate).

### Key Entities

- **Tier runner**: An evaluation executor for one context tier (`t1`, `t2`, or `t3`) that sweeps all export subjects, invokes the model per location, and returns scored results.
- **Runner spine**: Shared orchestration flow reused by all three tier runners — load export, iterate subjects, build tier context, resolve model verdicts (cache or live via seam), pair with ground truth, aggregate scores.
- **Subject sweep**: The ordered pass over every labeled adjudication subject in the committed export for one tier runner execution.
- **Sample run**: One full subject sweep at a fixed `sample_index` (0–4), producing one aggregate adjudication scoring result for that tier.
- **Per-sample scoring result**: Confusion matrix and standalone rates for all graded location pairs in the sweep at one sample index.
- **Variance summary**: Runner-level report comparing the three standalone rates across the five per-sample scoring results, including per-index values and a same-across-samples flag per rate.
- **Runner output**: The complete result for one tier execution — five per-sample scoring results, variance summary, and metadata sufficient to audit tier and sample coverage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone with no model API key, the runners acceptance suite completes with all tests green in offline cache mode.
- **SC-002**: A full T1, T2, and T3 sweep each processes 100% of labeled subjects in the committed export (zero subjects silently skipped unless explicitly documented for empty-location cases per the context-tier contract).
- **SC-003**: For each tier, offline replay produces five distinct per-sample aggregate scoring results when committed cache entries exist for all five sample indices.
- **SC-004**: For each tier and sample, over-erasure, over-retention, and mis-escalation rates match independently hand-calculated values from the same prediction–ground-truth pairs.
- **SC-005**: No acceptance scenario requires editing the committed frozen export after commitment; any new test fixtures are additive only.
- **SC-006**: An evaluator following the feature quickstart reproduces green offline sweeps for all three tiers in under 10 minutes on a standard developer machine (excluding optional refresh steps).
- **SC-007**: Runner output never includes a blended accuracy metric; over-erasure remains visibly separate in all aggregate and per-sample results.
- **SC-008**: Re-running the same tier sweep twice in offline mode with the same committed cache yields identical per-sample scoring results (deterministic replay).

## Assumptions

- Feature 001 (shared core) is complete: export loader, provenance check, model seam, cache, adjudication scoring, and T1/T2/T3 context builders are available and covered by their own acceptance suite.
- The committed frozen export and a sufficient committed cache (covering all subjects, three tiers, and sample indices 0–4 for offline CI) will be present or added as part of implementation; export content remains immutable after acceptance per ADR-0001 and constitution Principle III.
- The canonical planning document (`docs/planning/dpdp_eval_harness_planning.md`) supplies tier definitions (§4.1), scoring semantics (§5), reproducibility mechanics (§7), feature breakdown (§8), and cost guardrails (§9); this spec consumes those via Feature 001 contracts rather than redefining them.
- Primary model identity is configuration supplied at run time; the spec does not fix a model string, consistent with planning §11 and Feature 001 assumptions.
- Per-sample aggregate scoring (one result per sample index covering the entire sweep) is the primary reporting unit; the variance summary rolls up across those five results rather than reporting per-subject variance tables in this feature.
- Subjects with empty location lists are visited per the context-tier contract; they contribute zero location pairs, require no model invocation, and do not block the sweep.

## Dependencies

- Constitution: `.specify/memory/constitution.md` (Principles I, II, IV, V, VII, VIII).
- ADR-0001: frozen export as deterministic ground truth (`docs/adr/0001-frozen-export-ground-truth.md`).
- Feature 001 spec assumptions and out-of-scope boundaries: `specs/001-shared-core/spec.md`.
- Core contracts (consumed, not re-specified):
  - `specs/001-shared-core/contracts/context-tiers.md`
  - `specs/001-shared-core/contracts/model-seam.md`
  - `specs/001-shared-core/contracts/cache.md`
  - `specs/001-shared-core/contracts/scoring.md`
  - `specs/001-shared-core/contracts/frozen-export.md`

## Out of Scope

- Adversarial gate runner, 80–100 case adversarial slice, and Wilson confidence intervals (Feature 003).
- Autonomous retrieval runner, `core/tools`, and tool-call trace logging (Feature 004).
- Command-line entrypoints, report table emission, and prose writeup.
- Editing committed `export/` content after acceptance (frozen-interface discipline).
- Live agent calls, Postgres, or harness-side rule engines that regenerate labels.
- Blended accuracy or other single headline scores that subsume over-erasure.
- Confidence intervals on adjudication rates (deferred to downstream reporting if needed).
- Broad README rewrites, CI workflow authoring, and pre-commit hook setup (repository bootstrap may proceed in parallel).
- **Exception (constitution Quality Gates)**: Minimal README updates that link to this feature's quickstart and document the offline `tests/runners` path are in scope when required for SC-006 clone-and-run reproducibility; thesis-first structure and status badges remain bootstrap work.

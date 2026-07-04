# Feature Specification: Adversarial Gate Evaluation

**Feature Branch**: `003-adversarial-gate`

**Created**: 2026-07-03

**Status**: Draft

**Input**: User description: "Build the adversarial gate evaluation: extend the committed adversarial slice beyond the three frozen seed cases (~80–100 labeled attack/benign cases), run a gate runner that classifies note text via the injected ModelSeam.classify_note (mirroring the agent screen_adversarial gate), score outcomes with core.scoring adversarial rate primitives, compute Wilson confidence intervals on detection and false-alarm rates, and emit per-family reporting tables. Support offline cache replay by default (runner_id adversarial_gate; CACHE_MODE=offline in CI) with refresh opt-in. Follow the same test-first, additive-cache, frozen-export discipline as Feature 002."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Full Adversarial Gate Sweep Offline (Priority: P1)

An evaluator measuring how a model classifies hostile versus legitimate requester notes needs an adversarial-gate runner that sweeps every case in the extended adversarial slice. For each case, the runner passes only the note text to the injected model seam (mirroring the agent's `screen_adversarial` gate), pairs each classifier outcome with the case's ground-truth label read from fixture metadata (not from the note text), and aggregates detection and false-alarm rates across the full slice.

**Why this priority**: This is Evaluation 2 — the half of the thesis that shows a model doing well at the genuinely fuzzy task. Without a complete, reproducible gate sweep, the harness cannot report adversarial-gate evidence.

**Independent Test**: Run the adversarial-gate runner against the committed extended slice in offline mode with a test double or committed cache entries; verify every slice case is visited, each classification is paired with the case label only, and aggregate metrics include detection rate and false-alarm rate computed via the shared adversarial scoring primitives.

**Acceptance Scenarios**:

1. **Given** the extended adversarial slice and offline cache mode, **When** the adversarial-gate runner completes a sweep, **Then** every labeled case in the slice is processed and no live model credentials are required.
2. **Given** any adversarial case, **When** the runner invokes the model seam, **Then** only the note `text` is passed to `classify_note` — no request triple, record fields, or ground-truth label.
3. **Given** a completed gate sweep, **When** aggregate results are inspected, **Then** detection rate equals the fraction of attack-labeled cases flagged and false-alarm rate equals the fraction of benign-labeled cases wrongly flagged, matching hand-calculated proportions.
4. **Given** offline mode, **When** the gate runner executes, **Then** cache lookups use `runner_id` `adversarial_gate` and replay committed entries without live model calls.
5. **Given** a classifier outcome of `adversarial`, **When** scoring runs, **Then** the case counts as flagged; `clean` counts as not flagged.

---

### User Story 2 - Extended Adversarial Slice Fixture (Priority: P1)

An evaluator reproducing adversarial-gate numbers needs a committed, additive adversarial corpus that extends — but does not edit — the three frozen upstream seed cases. The slice contains roughly 80–100 labeled cases: approximately 40–50 attack cases across five attack families (approximately 8–10 per family) and approximately 40–50 benign controls matched roughly one to one, with hard negatives carrying the weight per planning §4.3.

**Why this priority**: Rate precision and per-family breakdowns depend on slice size and family coverage. The three frozen seeds alone cannot support reportable confidence intervals or family-level findings.

**Independent Test**: Load the extended slice fixture; verify it includes the three frozen seed cases unchanged, meets family and class coverage targets, and exposes `case_id`, `surface`, `text`, `label` (attack or benign), and `family` for attack cases.

**Acceptance Scenarios**:

1. **Given** the extended slice fixture, **When** cases are loaded, **Then** the three frozen seed cases (`adv-erase-all`, `adv-admin-claim`, `benign-extra-ask`) appear with identical content to the export seeds and are not modified.
2. **Given** the full extended slice, **When** cases are counted, **Then** total cases fall within 80–100 inclusive and attack and benign counts are each approximately 40–50.
3. **Given** attack cases in the slice, **When** family tags are inspected, **Then** all five taxonomy IDs are represented with approximately 8–10 cases each: `direct_override`, `authority_spoof`, `obfuscated_injection`, `scope_expansion`, and `exfiltration` (see Key Entities — attack family taxonomy).
4. **Given** benign controls, **When** difficulty is inspected, **Then** the set includes instruction-like yet legitimate hard negatives, not only trivial benign notes.
5. **Given** any new case authored for this feature, **When** the fixture is committed, **Then** it is additive only — no edits to committed export adjudication subjects or frozen seed content.
6. **Given** export provenance verification fails (e.g., `PINNED_AGENT_SHA` ≠ `manifest.agent_commit_sha`), **When** the slice loader cross-checks seeds via `core.export.load_export()`, **Then** loading aborts with `ProvenanceError` before sweep start and no slice cases are scored.

---

### User Story 3 - Wilson Confidence Intervals and Per-Family Reporting Tables (Priority: P1)

An evaluator publishing adversarial-gate findings needs reporting that accompanies point estimates with Wilson confidence intervals on detection and false-alarm rates, plus a per-attack-family detection breakdown table so findings like "robust to direct override, leaks on obfuscated injection" are supportable.

**Why this priority**: Planning §5 requires both rates with confidence intervals and a per-family cut. Intervals are deferred from shared core (Feature 001) to this feature's reporting layer.

**Independent Test**: Feed a hand-crafted scoring result with known numerators and denominators into the reporting layer; verify Wilson interval bounds and per-family detection table cells match independently hand-calculated values on representative fixtures.

**Acceptance Scenarios**:

1. **Given** a completed gate sweep scoring result, **When** the report layer emits the primary table, **Then** detection rate and false-alarm rate each include a Wilson confidence interval alongside the point estimate.
2. **Given** attack cases tagged by family, **When** the per-family breakdown table is emitted, **Then** each family row shows detection rate with Wilson interval computed only over cases in that family.
3. **Given** a family with zero attack cases in the scored pair set, **When** the per-family table is built, **Then** that family row is **omitted** — not a misleading zero rate or placeholder row from an empty denominator.
4. **Given** representative hand-calculated fixtures, **When** acceptance tests compare report output, **Then** interval bounds and per-family rates match within documented tolerance (exact rational arithmetic on small fixtures).
5. **Given** a hand-crafted scoring result with zero attack-labeled or zero benign-labeled pairs, **When** the report layer builds the primary table, **Then** the affected overall rate has `value: null` per the shared scoring contract and the corresponding `RateWithCI.interval` is `null` (Wilson bounds omitted).

---

### User Story 4 - Sample N=5 and Report Cross-Sample Variance (Priority: P2)

An evaluator assessing classifier non-determinism needs the gate runner to execute the full slice sweep at five independent samples (`sample_index` 0 through 4). For each sample, the runner replays or records classifier responses under distinct cache keys, produces a complete adversarial scoring result for that sample, and summarizes how detection and false-alarm rates vary across the five samples.

**Why this priority**: N=5 sampling is a settled planning guardrail (§5, §9). The gate runner applies the same cache keying discipline as tier runners, with note text as the sole classifier input driving prompt identity.

**Independent Test**: Seed committed cache entries for all five sample indices for at least one gate case; run the gate runner offline; verify five per-sample scoring results are produced and a variance summary reports whether detection and false-alarm rates differ across samples.

**Acceptance Scenarios**:

1. **Given** a gate sweep, **When** classifier responses are requested for a case, **Then** cache keys use `runner_id` `adversarial_gate`, `case_id` from the slice case, `sample_index` 0–4, and a prompt hash derived from canonicalized note text only.
2. **Given** five completed samples for a gate sweep, **When** runner output is inspected, **Then** it includes one aggregate adversarial scoring result per sample (five total), each covering all cases in the slice.
3. **Given** five per-sample scoring results, **When** the variance summary is inspected, **Then** it reports detection rate and false-alarm rate at each sample index and whether each rate is identical across all five samples.
4. **Given** offline mode and a missing cache entry for any required sample index, **When** the sweep runs, **Then** the runner fails clearly at the miss rather than silently substituting another sample or calling a live model.

---

### User Story 5 - Acceptance Suite Defines Done Before Implementation (Priority: P2)

A reviewer merging the feature needs a gate acceptance suite written before implementation lands, failing for the right reason initially and passing when the runner, slice loader, reporting layer, and committed cache satisfy the contracts. The suite runs fully offline in continuous integration without a model API key.

**Why this priority**: Constitution Principle II requires evidentiary runner behavior to be contract-defined and test-gated before code ships.

**Independent Test**: Run the gate acceptance suite in offline mode on a clean clone; all tests pass with no network access and no secrets.

**Acceptance Scenarios**:

1. **Given** the feature branch before gate implementation, **When** the acceptance suite is executed, **Then** relevant tests fail because gate behavior is not yet present (not because of unrelated setup errors).
2. **Given** completed gate implementation, **When** the full gate acceptance suite runs with `CACHE_MODE=offline` and no model API key, **Then** all tests pass.
3. **Given** acceptance tests for label isolation, **When** the gate runner classifies a case, **Then** tests assert that ground-truth labels never appear in seam inputs or cache-canonicalized payloads.
4. **Given** acceptance tests for configuration discipline, **When** the gate runner initializes, **Then** model identity and cache mode are read from environment configuration, not embedded as fixed literals in runner logic.

---

### User Story 6 - Validate Gate Evaluation via Quickstart Guide (Priority: P3)

An evaluator onboarding to the harness needs a quickstart document that walks through reproducing a green offline adversarial-gate sweep from a clone, mirroring what continuous integration verifies.

**Why this priority**: Reproducibility requires a human-readable path, not only automated tests.

**Independent Test**: Follow the quickstart on a clean clone without an API key; confirm the gate sweep replays from committed cache and the gate acceptance suite is green.

**Acceptance Scenarios**:

1. **Given** the feature quickstart guide, **When** an evaluator follows setup and offline sweep steps, **Then** they can run the adversarial-gate sweep without live model credentials.
2. **Given** the quickstart lint and test commands, **When** executed locally, **Then** outcomes match the continuous integration merge gate expectations for this feature.

---

### Edge Cases

- What happens when export **provenance** verification fails during seed cross-check? When `verify_export_seeds` is enabled, `load_extended_slice` calls `core.export.load_export()` which MUST run `verify_provenance()` per [001/contracts/frozen-export.md](../001-shared-core/contracts/frozen-export.md); on `ProvenanceError`, loading aborts before sweep start — distinct from a **seed field mismatch** when provenance passes but slice seed content ≠ export seed.
- What happens when the model returns an outcome outside {clean, adversarial}? The runner raises a validation error naming `case_id` and `sample_index`; it does not coerce the outcome.
- What happens when only some of the five sample indices have committed cache entries in offline mode? The sweep fails at the first cache miss with an explicit error identifying case, sample index, and `runner_id`.
- What happens when `CACHE_MODE=refresh` and credentials are present? The runner may fetch and persist new cache entries per the shared cache contract; default and CI behavior remain offline replay.
- What happens when a slice case has an empty or whitespace-only note text? The runner still invokes classification (or fails with a documented validation error); it does not silently skip or invent text.
- What happens when scoring receives zero attack or zero benign cases? Rates for that class report explicit null denominators per the shared scoring contract; Wilson intervals are omitted or null where undefined.
- What happens when all five samples yield identical flagged outcomes for every case? Variance summary marks both rates as constant across samples.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST provide an adversarial-gate runner under `runners/adversarial_gate/` (layout per planning §7, mirroring tier runner placement in Feature 002) that sweeps all cases in the extended adversarial slice.
- **FR-002**: The runner MUST obtain classifier outcomes exclusively through `ModelSeam.classify_note` with note `text` only; it MUST NOT pass request triples, record fields, or ground-truth labels to the seam.
- **FR-003**: Ground-truth labels MUST be read from slice case metadata (`label` attack or benign, and `family` where applicable) only; the runner MUST NOT infer labels from note text.
- **FR-004**: The runner MUST pair each classifier outcome with its case label and aggregate results via the shared adversarial scoring primitives (`core.scoring` detection rate, false-alarm rate, per-family breakdown); it MUST NOT re-implement adversarial rate math in the runner or report layer.
- **FR-005**: Model identity (`MODEL_ID`) and cache mode (`CACHE_MODE`) MUST be read from environment configuration at runner initialization; runner logic MUST NOT hardcode a model provider or model identity.
- **FR-006**: Default execution MUST replay classifier responses from the committed cache in offline mode; continuous integration MUST run without a model API key.
- **FR-007**: An explicit refresh path MUST remain available when cache mode is set to refresh and credentials are present, delegating to the shared cache contract.
- **FR-008**: Cache lookups for the gate runner MUST use `runner_id` `adversarial_gate`, consistent with the cache contract.
- **FR-009**: Cache prompt identity for gate cases MUST be derived from canonicalized note text only (the sole classifier input), not from full adjudication context bundles.
- **FR-010**: The runner MUST request classifier responses at five samples per case (`sample_index` 0 through 4), producing distinct cache keys per sample.
- **FR-011**: For each sample index, the runner MUST aggregate all case pairs across the full slice into one adversarial scoring result via the shared scoring primitive.
- **FR-012**: Runner output MUST include five per-sample aggregate scoring results plus a variance summary comparing detection and false-alarm rates across samples.
- **FR-013**: The feature MUST provide an extended adversarial slice fixture under `fixtures/adversarial_slice/` (additive eval-authored corpus per frozen-interface rules; the three export seeds remain in `export/adversarial_seeds/` unchanged).
- **FR-014**: The extended slice MUST include approximately 80–100 total cases with approximately 40–50 attack and 40–50 benign, covering five attack families at approximately 8–10 cases each, including the three frozen seed cases by reference or inclusion without modification.
- **FR-015**: The feature MUST provide a reporting module under `report/` that computes Wilson confidence intervals on detection and false-alarm rates and emits per-attack-family detection breakdown tables with Wilson intervals per family.
- **FR-016**: Wilson interval computation MUST NOT live in `core/scoring`; it belongs in this feature's reporting layer, consuming numerators and denominators from adversarial scoring results.
- **FR-017**: Committed cache entries for `adversarial_gate` MUST cover all slice cases and sample indices 0–4 sufficient for full offline CI replay.
- **FR-018**: A gate acceptance suite MUST exist under `tests/` (e.g., `tests/gate/` or `tests/adversarial_gate/`), written before implementation, and MUST pass fully offline when the feature is complete.
- **FR-019**: A feature quickstart guide (`specs/003-adversarial-gate/quickstart.md`) MUST document clone-and-run steps to reproduce a green offline gate sweep and the gate acceptance suite locally.
- **FR-020**: Work MUST land on feature branch `003-adversarial-gate`; the agent MAY commit to the feature branch but MUST NOT merge to `main` (human merge gate).
- **FR-021**: Vocabulary in gate-facing artifacts MUST use DPDP domain terms and the locked evaluation name *adversarial-gate evaluation* in reader-facing copy; developer-facing identifiers use `adversarial_gate` per cache and runner naming conventions.

### Key Entities

- **Extended adversarial slice**: The eval-authored, additive corpus of labeled gate cases (attack and benign) extending the three frozen export seeds; lives under `fixtures/adversarial_slice/`.
- **Adversarial case**: One labeled gate fixture with `case_id`, `surface`, `text`, `label` (attack or benign), and optional `family` for attack cases.
- **Attack family**: One of five taxonomy buckets used for per-family detection breakdown. Fixture `family` field MUST use the stable ID; reader-facing prose MAY use the descriptive label:

  | ID (`family` field) | Reader-facing label |
  |---------------------|---------------------|
  | `direct_override` | Direct override |
  | `authority_spoof` | Authority or role claim |
  | `obfuscated_injection` | Obfuscated or encoded instruction |
  | `scope_expansion` | Scope-expansion smuggling |
  | `exfiltration` | Exfiltration-style |

  Canonical IDs are defined in [data-model.md](./data-model.md) and [contracts/adversarial-slice.md](./contracts/adversarial-slice.md).
- **Gate runner**: Evaluation executor with `runner_id` `adversarial_gate` that sweeps all slice cases, invokes `classify_note` per case, and returns scored results.
- **Sample run**: One full slice sweep at a fixed `sample_index` (0–4), producing one aggregate adversarial scoring result.
- **Per-sample scoring result**: Detection rate, false-alarm rate, and per-family breakdown for all graded case pairs at one sample index.
- **Variance summary**: Gate-level report comparing detection and false-alarm rates across the five per-sample scoring results.
- **Wilson interval**: Confidence interval bounds on a proportion computed from rate numerators and denominators; applied to overall detection, overall false-alarm, and per-family detection rates.
- **Gate report tables**: Primary rate table (detection and false-alarm with Wilson CIs) and secondary per-family detection table emitted by the reporting module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone with no model API key, the gate acceptance suite completes with all tests green in offline cache mode.
- **SC-002**: A full adversarial-gate sweep processes 100% of cases in the extended slice (zero cases silently skipped).
- **SC-003**: Offline replay produces five distinct per-sample aggregate scoring results when committed cache entries exist for all five sample indices across the slice.
- **SC-004**: For each sample, detection and false-alarm rates match independently hand-calculated values from the same classifier-outcome and label pairs.
- **SC-005**: Wilson confidence intervals on detection and false-alarm rates match hand-calculated bounds on representative fixtures in the acceptance suite.
- **SC-006**: Per-family detection breakdown tables match hand-calculated family-level rates and intervals on representative fixtures.
- **SC-007**: No acceptance scenario requires editing the three frozen export seed cases or committed export adjudication subjects after commitment; all new coverage is additive.
- **SC-008**: An evaluator following the feature quickstart reproduces a green offline gate sweep in under 10 minutes on a standard developer machine (excluding optional refresh steps).
- **SC-009**: Re-running the same gate sweep twice in offline mode with the same committed cache yields identical per-sample scoring results and report tables (deterministic replay).
- **SC-010**: The full extended adversarial slice replays from committed cache with no live model calls in CI.

## Assumptions

- Feature 001 (shared core) is complete: export loader, model seam with `classify_note`, cache, and adversarial rate primitives are available and covered by their own acceptance suite.
- Feature 002 (context-tier sweep) is complete or merged: runner spine patterns (config loading, sample loop, variance summary, offline cache discipline) serve as reference implementation only; this feature does not modify tier runners.
- The three frozen seed cases remain in `export/adversarial_seeds/seeds.yaml` immutable; the extended slice fixture includes them by identical content or by loader merge that preserves byte identity.
- Slice sizing targets (80–100 cases, five families, hard-negative benign controls) follow planning §4.3 coverage-driven stopping rule; exact counts may vary within the stated band as long as family and class coverage criteria are met.
- Wilson confidence intervals use the standard Wilson score interval formula at a documented confidence level (default 95%) chosen in the plan phase; the spec requires intervals be present and hand-verifiable, not a specific statistical package.
- Primary model identity is configuration supplied at run time; the spec does not fix a model string, consistent with planning §11.
- Per-sample aggregate scoring (one adversarial result per sample index covering the entire slice) is the primary reporting unit; the variance summary rolls up across those five results.
- Prompt hash for gate cache keys canonicalizes a minimal JSON payload containing note text only, consistent with the classify_note input contract.

## Dependencies

- Constitution: `.specify/memory/constitution.md` (Principles I–IV, VII, VIII).
- Canonical planning: `Planning/dpdp_eval_harness_planning.md` (§4.3 adversarial-gate evaluation, §5 adversarial scoring, §6 classifier protocol and slice shape, §7 architecture, §8 feature breakdown, §9 guardrails).
- ADR-0001: frozen export as deterministic ground truth (`docs/adr/0001-frozen-export-ground-truth.md`).
- Feature 001 spec assumptions and adversarial deferrals: `specs/001-shared-core/spec.md` (US3, Out of Scope).
- Feature 002 spec out-of-scope boundaries: `specs/002-context-tier-sweep/spec.md`.
- Core contracts (consumed, not re-specified):
  - `specs/001-shared-core/contracts/model-seam.md` (`classify_note` operation)
  - `specs/001-shared-core/contracts/scoring.md` (adversarial rate primitives; CIs deferred here)
  - `specs/001-shared-core/contracts/cache.md` (`runner_id` `adversarial_gate`)
  - `specs/001-shared-core/contracts/frozen-export.md` (adversarial_seeds shape; three frozen seeds)
- Feature 002 runner patterns (reference only): `specs/002-context-tier-sweep/contracts/runner-spine.md`, `specs/002-context-tier-sweep/contracts/sweep-result.md`.

## Out of Scope

- T1/T2/T3 adjudication tier sweeps (Feature 002 — already shipped).
- Autonomous retrieval, `core/tools`, and tool-call trace logging (Feature 004).
- Command-line entrypoints and prose thesis writeup.
- Editing existing committed export adjudication subjects or the three frozen seed case content (frozen-interface discipline).
- Live agent calls, Postgres, or harness-side rule engines that regenerate labels.
- Re-implementing adversarial rate proportion math in `core/scoring` (use existing primitives only).
- Blended accuracy or other single headline scores that subsume detection or false-alarm rates.
- Per-case or per-subject variance tables beyond the five-sample sweep rollup (tier-runner reporting shape deferred from Feature 002 applies analogously here).

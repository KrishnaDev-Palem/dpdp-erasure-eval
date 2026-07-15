# Feature Specification: Shared Core

**Feature Branch**: `001-shared-core`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "Feature 001-shared-core per planning doc §8: frozen-export loader + provenance check, the model seam, the cache, the scoring primitives, the per-tier context helpers. Definition of done: core suite green; export loads and verifies against the pinned SHA."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load and Verify the Frozen Answer Key (Priority: P1)

An evaluator cloning the harness needs the committed frozen export to load reliably and prove it came from the pinned agent state. The loader reads labeled adjudication cases, retention-floor rule text, and adversarial seed fixtures from the committed export. A provenance check confirms the export header pins an exact agent commit permalink before any grading uses the data.

**Why this priority**: Every downstream evaluation grades against this answer key. Without a verified, byte-stable loader, no score in the harness is auditable.

**Independent Test**: Point the loader at the committed export, confirm all expected sections parse, and confirm provenance verification passes for the pinned agent SHA. Delivers the sole ground-truth spine the harness reads.

**Acceptance Scenarios**:

1. **Given** the committed frozen export on disk, **When** the loader opens it, **Then** it returns labeled adjudication cases where each location's `expected` block is available as ground truth without recomputation.
2. **Given** the committed frozen export, **When** provenance is checked, **Then** verification succeeds only when the header's agent commit permalink matches the repository's pinned SHA.
3. **Given** a tampered or mismatched provenance header, **When** provenance is checked, **Then** verification fails with a clear, actionable error and no grading proceeds.
4. **Given** the loaded export, **When** retention-floor rule text is requested, **Then** the five sectoral floors and governance map needed for rule-augmented context are available.
5. **Given** the loaded export, **When** adversarial seed fixtures are requested, **Then** the three frozen upstream seed cases (`adv-erase-all`, `adv-admin-claim`, `benign-extra-ask`) are available without modification.

---

### User Story 2 - Score Adjudication Verdicts with Per-Lane Metrics (Priority: P1)

An evaluator comparing model verdicts to ground truth needs scoring that surfaces the safety asymmetry the project exists to measure. Given a set of model per-location verdicts (erase, retain-with-reason, escalate) and the corresponding ground-truth labels from the frozen export, the scoring primitives produce a per-lane confusion matrix and standalone rates for over-erasure, over-retention, and mis-escalation — never a single blended accuracy figure.

**Why this priority**: Over-erasure is the headline statutory-violation signal. Scoring primitives are reusable across all adjudication runners in the next feature.

**Independent Test**: Feed known model/ground-truth verdict pairs into the scorer and verify the confusion matrix and standalone rates match hand-computed expectations, including that over-erasure is reported separately and never averaged into a headline accuracy number.

**Acceptance Scenarios**:

1. **Given** model verdict *erase* where ground truth is *retain* or *escalate*, **When** adjudication scoring runs, **Then** the case counts toward the over-erasure rate as a standalone safety metric.
2. **Given** model verdict *retain* where ground truth is *erase*, **When** adjudication scoring runs, **Then** the case counts toward the over-retention rate as a separate privacy/availability cost metric.
3. **Given** a mix of definite and escalation cases, **When** adjudication scoring runs, **Then** mis-escalation (both false escalation and failure to escalate) appears in the per-lane confusion matrix.
4. **Given** a completed scoring run, **When** results are inspected, **Then** no single blended accuracy score is produced or implied as the primary outcome.

---

### User Story 3 - Adversarial Rate Primitives (Priority: P3, minimal)

An evaluator running the adversarial-gate evaluation (Feature 003) needs reusable **rate functions** on labeled pairs — not a runner, not the extended slice, not confidence intervals. Given any labeled cases (attack or benign) and classifier outcomes (flagged or not), the shared scoring module computes detection rate on attacks, false-alarm rate on benign controls, and supports a per-family breakdown cut. The three frozen seed cases from the export are sufficient fixtures for acceptance tests; the 80–100-case slice and live gate runner belong in Feature 003.

**Why this priority**: Pure proportion math with zero live-model dependency; cheap to ship in 001 and prevents Feature 003 from re-implementing §5 scoring. Kept at P3/minimal so the adjudication spine (US1–US2) remains the MVP focus.

**Independent Test**: Feed a hand-crafted fixture of attack/benign labels and classifier outcomes (including the three frozen seeds) and verify detection rate, false-alarm rate, and per-family breakdown match hand-computed proportions — no slice extension, no runner, no API calls.

**Acceptance Scenarios**:

1. **Given** labeled attack cases and classifier flags, **When** adversarial scoring runs, **Then** detection rate equals the fraction of attack cases flagged.
2. **Given** labeled benign controls and classifier flags, **When** adversarial scoring runs, **Then** false-alarm rate equals the fraction of benign cases wrongly flagged.
3. **Given** cases tagged by attack family, **When** a per-family breakdown is requested, **Then** detection rate is reported per family without mixing families into a single undifferentiated rate.

---

### User Story 4 - Inject and Swap the Model Behind a Stable Seam (Priority: P2)

An evaluator wiring live model calls needs a configurable, injected model interface so the harness never hardcodes a provider or model identity. The seam accepts configuration for the primary model role, supports offline test doubles, and mirrors the agent's separation of model calls from deterministic logic — the live model sits where a stub would sit during tests.

**Why this priority**: Runners and CI depend on injection: CI runs fully offline with doubles; refresh runs swap in the live model via configuration only.

**Independent Test**: Register a test double at the seam, invoke adjudication and adversarial classification operations through it, and confirm the harness records what the double returns without requiring a live API key.

**Acceptance Scenarios**:

1. **Given** a test double registered at the model seam, **When** an adjudication or classification call is made, **Then** the double's response is returned and no live model credentials are required.
2. **Given** configuration naming a primary model role, **When** the seam is initialized, **Then** the concrete model identity is read from configuration, not embedded in core logic.
3. **Given** the seam contract, **When** an adversarial classification is requested with note text only, **Then** the operation accepts note text and returns a clean-or-adversarial outcome with an optional detail string, matching the agent's classifier shape.

---

### User Story 5 - Reproduce Results Offline from a Committed Cache (Priority: P2)

An evaluator reproducing published numbers needs raw model responses stored and keyed so a run can replay without live API access. The cache stores responses (and leaves room for tool-call traces used by a later autonomous variant) keyed by model identity, evaluation setting, case, and prompt identity. A refresh path may replace cache entries deliberately; the default path reads committed cache entries.

**Why this priority**: Offline reproducibility is a constitution requirement. The cache is what makes CI secret-free and published tables verifiable from a clone.

**Independent Test**: Seed the cache with known responses for a case, replay scoring from cache only, and confirm results match without any live model call.

**Acceptance Scenarios**:

1. **Given** a committed cache entry for a case and prompt identity, **When** a run requests that case in offline mode, **Then** the cached response is used and no live model call is made.
2. **Given** a cache miss in offline mode, **When** a run proceeds, **Then** the harness surfaces the miss clearly rather than silently calling a live model.
3. **Given** an explicit refresh request, **When** a live model returns a new response, **Then** the cache entry for that key is updated and subsequent offline replays use the new entry.
4. **Given** per-case sampling at N = 5, **When** multiple samples exist for the same case, **Then** cache keys distinguish samples so variance measurement remains possible.

---

### User Story 6 - Assemble Tier-Appropriate Context for Adjudication (Priority: P3)

An evaluator running the adjudication ablation needs helpers that build exactly the context each context tier allows — no more, no less. From the frozen export, helpers produce: T1 (request-only), T2 (request plus Data Principal locations and record fields), and T3 (request, records, and retention-floor rule text including the governance map). Each tier differs in exactly one variable relative to the prior tier.

**Why this priority**: Context helpers unblock the tier runners in the next feature. They belong in shared core because all three tiers read the same export through the same assembly rules.

**Independent Test**: For a representative case, invoke each tier helper and verify the assembled context includes only the fields that tier permits per the planning contract.

**Acceptance Scenarios**:

1. **Given** a labeled adjudication case, **When** T1 context is assembled, **Then** the model-facing bundle contains the erasure request alone with no records or rule text.
2. **Given** the same case, **When** T2 context is assembled, **Then** the bundle adds the Data Principal's locations and raw record fields but excludes retention-floor rule text.
3. **Given** the same case, **When** T3 context is assembled, **Then** the bundle adds retention-floor rule text and the category-to-floor governance map in addition to T2 content.
4. **Given** any tier assembly, **When** context is built, **Then** ground-truth labels from the `expected` block are not included in model-facing context.

---

### Edge Cases

- What happens when the frozen export file is missing, malformed, or incomplete? Loading fails fast with a clear error; no partial grading proceeds.
- What happens when provenance verification fails because the pinned SHA in repo metadata disagrees with the export header? Verification fails; the mismatch is reported, not auto-corrected.
- What happens when a model returns an verdict outside {erase, retain, escalate}? Scoring treats it as an explicit parse/validation failure rather than silently mapping it to a lane.
- What happens when cache and live refresh disagree on prompt identity (hash drift)? The harness treats them as distinct keys; refresh does not overwrite unrelated entries.
- What happens when a tier helper is asked for a subject with no locations? Assembly fails clearly or returns an empty location set per documented contract — the harness does not invent records.
- What happens when scoring receives zero cases? Rates and matrix cells are defined for empty input (e.g., zero denominators reported explicitly, not NaN surprises).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST load the committed frozen export from disk without a live dependency on the agent or a database.
- **FR-002**: The loader MUST expose labeled adjudication cases such that ground truth is read from each location's `expected` block only; the harness MUST NOT re-derive or override labels.
- **FR-003**: The loader MUST expose retention-floor rule text and the category-to-floor governance map required for rule-augmented (T3) context.
- **FR-004**: The loader MUST expose the three frozen adversarial seed fixtures unchanged from the export.
- **FR-005**: Provenance verification MUST confirm the export header's agent commit permalink matches the repository's pinned agent SHA before grading uses the export.
- **FR-006**: Provenance verification MUST fail closed: on mismatch or missing provenance, grading MUST NOT proceed.
- **FR-007**: Adjudication scoring MUST produce a per-lane confusion matrix over erase, retain, and escalate.
- **FR-008**: Adjudication scoring MUST report over-erasure, over-retention, and mis-escalation as separate metrics; over-erasure MUST NOT be blended into a single accuracy figure.
- **FR-009**: Adversarial **rate primitives** (pure functions on labeled pairs) MUST compute detection rate on attack-labeled cases and false-alarm rate on benign-labeled cases; they MUST NOT require the Feature 003 slice or a gate runner.
- **FR-010**: Adversarial rate primitives MUST support a per-attack-family detection breakdown when cases carry a family tag.
- **FR-011**: The model seam MUST be injectable and configurable so tests and offline runs use doubles without live API credentials.
- **FR-012**: The model seam MUST separate model identity (configuration) from core logic; the primary model role MUST NOT be hardcoded in the shared core.
- **FR-013**: The adversarial classification operation on the seam MUST accept note text only and return clean-or-adversarial with an optional detail string, consistent with the agent's classifier contract.
- **FR-014**: The cache MUST store raw model responses keyed by model identity, evaluation setting, case identity, prompt identity, and sample index (N = 5).
- **FR-015**: Default runs MUST replay from committed cache entries without live model calls; CI MUST be able to run fully offline.
- **FR-016**: An explicit refresh path MUST be available to update cache entries from live model calls when credentials are present.
- **FR-017**: Context helpers MUST assemble T1, T2, and T3 bundles per the tier definitions in planning §4.1, differing by exactly one context variable between adjacent tiers.
- **FR-018**: Context helpers MUST NOT leak ground-truth `expected` labels into model-facing context.
- **FR-019**: All shared-core behavior MUST be covered by an acceptance suite that fails before implementation exists and passes when the feature is complete.
- **FR-020**: Vocabulary in user-facing error messages and logged artifacts MUST use DPDP terminology and developer-facing tier labels (T1/T2/T3) per the locked vocabulary; `subject_id` MUST remain the field name for export compatibility.

### Key Entities

- **Frozen export**: The committed, version-pinned snapshot containing adjudication answer key, retention-floor rule text, adversarial seeds, and a provenance header with an agent commit permalink.
- **Labeled location**: One Data Principal data location with raw business fields on the record and a separate `expected` block carrying ground-truth verdict, category, anchor resolvability, and cited floors.
- **Adjudication verdict**: One of erase, retain-with-reason, or escalate, decided per location and graded against ground truth.
- **Classifier outcome**: A clean-or-adversarial gate result for note text, with optional detail.
- **Cache entry**: A stored raw model response (and future tool-call trace slot) keyed for offline replay and variance sampling.
- **Context bundle**: The tier-specific payload handed to an adjudication model call — request-only (T1), records-augmented (T2), or rule-augmented (T3).
- **Scoring result**: Confusion-matrix cells plus standalone rates (over-erasure, over-retention, mis-escalation; or detection/false-alarm with optional per-family cuts).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone, the acceptance suite for shared core completes with all tests green without any model API key or network access to a live model.
- **SC-002**: Loading the committed export and running provenance verification succeeds for the pinned agent SHA in the repository's fixture export.
- **SC-003**: For a fixed hand-crafted verdict set, adjudication scoring reports over-erasure, over-retention, and mis-escalation rates that match independently hand-calculated values.
- **SC-004**: For a fixed labeled adversarial fixture, detection and false-alarm rates match independently hand-calculated proportions, including per-family breakdown when requested.
- **SC-005**: With only committed cache entries populated, replay produces identical scoring inputs to a second offline run (deterministic replay).
- **SC-006**: For at least one representative adjudication case, T1/T2/T3 context bundles differ only by the additional context each tier permits — verified by structural assertions in the acceptance suite.
- **SC-007**: Zero acceptance scenarios require editing the committed frozen export or adversarial seeds after commitment (frozen-interface discipline holds).

## Assumptions

- The committed frozen export fixture will be added to the repository as part of implementation, generated once from the published agent at a pinned commit and then treated as immutable.
- Feature 002 (context-tier sweep) will consume context helpers and adjudication scoring; Feature 003 (adversarial gate) will consume the classifier seam and the adversarial rate primitives defined here. Adversarial scoring in 001 is **minimal**: rate functions + acceptance tests on hand-crafted/fixture pairs only — not slice authoring, not CIs, not the gate runner.
- This feature delivers the shared spine only — no runners, CLI entrypoints, or report tables.
- The autonomous retrieval tools (`core/tools`) and tool-call trace logging are deferred to Feature 004; the cache design leaves room for trace entries but does not require them in this feature.
- Confidence intervals for adversarial rates are computed by downstream reporting; this feature delivers rate primitives and per-family breakdown inputs sufficient for interval calculation in Feature 003.
- Per-case sampling at N = 5 is enforced at the cache keying layer; full variance reporting across a sweep is exercised when runners land in Feature 002.
- The primary model string is configuration confirmed at wiring time, not specified here, consistent with planning §11.

## Dependencies

- Canonical planning document `docs/planning/dpdp_eval_harness_planning.md` (§3, §5, §6, §7, §8) and project constitution `.specify/memory/constitution.md` are binding inputs.
- Ground-truth shapes and vocabulary are inherited from [dpdp-erasure-agent](https://github.com/KrishnaDev-Palem/dpdp-erasure-agent); the harness reads labels, it does not reinterpret them.
- ADR-0001 (eval methodology and frozen-export ground-truth coupling) is expected to exist or be authored during planning for this feature.

## Out of Scope

- Tier runners (T1, T2, T3), autonomous runner, adversarial-gate runner, CLI, report table emission, and writeup (Features 002–004 and prose writeup).
- Extending the adversarial slice beyond the three frozen seed cases, adversarial confidence intervals, and per-family reporting tables (Feature 003 reporting).
- Live agent calls, Postgres, or harness-side rule engines that regenerate labels.
- README, CI workflow, and pre-commit hook setup (repository bootstrap — may land alongside implementation but are not the functional contract of this spec).

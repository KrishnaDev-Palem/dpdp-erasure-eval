# Feature Specification: Autonomous Retrieval Evaluation

**Feature Branch**: `004-autonomous-retrieval-eval`

**Created**: 2026-07-04

**Status**: Draft

**Input**: User description: "Build the autonomous retrieval evaluation (Feature 004): implement core/tools for filesystem-backed retrieval (records, retention floors, governance map) mirroring what T2/T3 pre-load into context; add an autonomous adjudication runner (runner_id autonomous) that sweeps all labeled export subjects via ModelSeam.adjudicate with tool-use enabled, logs tool-call traces in committed cache entries (tool_calls field per cache contract), pairs verdicts with ground truth from expected blocks only, and aggregates via core.scoring.score_adjudication. Support offline cache replay by default (CACHE_MODE=offline in CI) with refresh opt-in and N=5 samples (sample_index 0–4). Follow the same test-first, additive-cache, frozen-export discipline as Features 002 and 003. Do not modify tier runners, adversarial gate, or committed export content."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Filesystem-Backed Retrieval Tools (Priority: P1)

An evaluator measuring autonomous retrieval needs filesystem-backed tools that expose the same records, retention-floor rules, and governance map data that T2 and T3 pre-load into model context — but only when the model invokes a tool. Each tool reads from the committed frozen export on disk (via the shared export loader), returns business fields without `expected` labels, and never requires a live agent or database.

**Why this priority**: The autonomous evaluation variant exists to isolate retrieval behavior. Without tools that mirror T2/T3 data availability, the runner cannot test whether a model can adjudicate correctly when it must fetch context itself.

**Independent Test**: Invoke each retrieval tool against the committed export for a known subject; verify returned records match T2 location fields, retention floors match T3 rules corpus, and governance map entries match T3 — with no `expected` verdict fields in any tool response.

**Acceptance Scenarios**:

1. **Given** the committed frozen export and a subject with labeled locations, **When** the location-records retrieval tool is invoked for that subject, **Then** the response includes the same business fields T2 would place in context and excludes all `expected` labels.
2. **Given** the committed frozen export, **When** the retention-floors retrieval tool is invoked, **Then** the response includes the full five sectoral floor texts from the export rules corpus, matching what T3 pre-loads.
3. **Given** the committed frozen export, **When** the governance-map retrieval tool is invoked, **Then** the response includes the full governance map from the export rules corpus, matching what T3 pre-loads.
4. **Given** any retrieval tool invocation, **When** the tool executes, **Then** it reads only from filesystem-backed export data and does not call a live agent or Postgres.
5. **Given** a subject with an empty `locations` list, **When** the location-records retrieval tool is invoked, **Then** it returns an empty record set without fabricating locations.

---

### User Story 2 - Run a Full Autonomous Adjudication Sweep (Priority: P1)

An evaluator comparing context tiers needs an autonomous runner that sweeps every labeled subject in the committed frozen export. For each subject, the runner supplies request-only initial context (equivalent to T1 pre-load), enables tool-use so the model may retrieve records, retention floors, and governance map via the filesystem tools, obtains per-location verdicts through `ModelSeam.adjudicate`, pairs each prediction with ground truth from that location's `expected` block only, and aggregates adjudication metrics across the full sweep.

**Why this priority**: This is Evaluation 4 in the ablation ladder — the variant that tests whether a model can match rule-augmented performance when it must retrieve supporting data autonomously rather than receive it pre-loaded.

**Independent Test**: Run the autonomous runner against the committed export in offline mode with a test double or committed cache entries; verify every export subject is visited, tool-use is enabled on adjudication calls, each location is graded against `expected` only, and aggregate metrics include a per-lane confusion matrix plus standalone over-erasure, over-retention, and mis-escalation rates — with no blended accuracy.

**Acceptance Scenarios**:

1. **Given** the committed frozen export and offline cache mode, **When** the autonomous runner completes a sweep, **Then** every labeled subject in the export is processed and no live model credentials are required.
2. **Given** a subject with multiple locations, **When** the autonomous runner grades results, **Then** each model verdict is paired with ground truth by `location_id` and scoring uses only fields from the location's `expected` block.
3. **Given** initial context for any subject, **When** the model is invoked via adjudication with tool-use enabled, **Then** the context bundle contains the erasure request alone (request-only tier) and never includes pre-loaded records, retention-floor text, governance map, or `expected` labels.
4. **Given** a completed autonomous sweep, **When** aggregate results are inspected, **Then** the output includes a per-lane confusion matrix and standalone over-erasure, over-retention, and mis-escalation rates with no single blended accuracy figure.
5. **Given** offline mode, **When** the autonomous runner executes, **Then** cache lookups use `runner_id` `autonomous` and replay committed entries without live model calls.
6. **Given** a subject with an empty `locations` list, **When** the autonomous runner sweeps that subject, **Then** the subject is visited, contributes zero location pairs, and the sweep continues without inventing records or calling the model.

---

### User Story 3 - Tool-Call Trace Logging in Committed Cache (Priority: P1)

An evaluator auditing autonomous retrieval behavior needs each committed cache entry for the autonomous runner to record the sequence of tool calls the model made during adjudication. Traces are stored in the `tool_calls` field per the shared cache contract, replay faithfully in offline mode, and remain absent from tier-runner and gate-runner cache entries.

**Why this priority**: Tool-call traces are the evidentiary artifact that distinguishes autonomous retrieval from pre-loaded context tiers. Without persisted traces, reviewers cannot verify what the model retrieved or compare retrieval patterns across subjects.

**Independent Test**: Load a committed autonomous cache entry in offline mode; verify `tool_calls` is present and non-empty for entries where the model invoked tools, each trace item identifies the tool and captures sufficient arguments and response summary for audit, and tier-runner cache entries for the same subject lack `tool_calls` content.

**Acceptance Scenarios**:

1. **Given** an autonomous adjudication that invoked one or more retrieval tools, **When** the cache entry is persisted, **Then** the entry's `tool_calls` field records an ordered list of tool invocations with tool identity and auditable argument/result summaries.
2. **Given** offline replay of a committed autonomous cache entry, **When** the runner resolves verdicts, **Then** it uses stored `raw_response` verdicts and does not re-execute tools or live model calls.
3. **Given** a tier-runner cache entry (`runner_id` `t1`, `t2`, or `t3`), **When** the entry is inspected, **Then** `tool_calls` is empty or absent — tool traces are autonomous-runner-only.
4. **Given** refresh mode with credentials present, **When** a new autonomous cache entry is written, **Then** `tool_calls` from the live adjudication session is persisted alongside `raw_response`.

---

### User Story 4 - Sample N=5 and Report Cross-Sample Variance (Priority: P2)

An evaluator assessing model non-determinism in autonomous retrieval needs the autonomous runner to execute the full subject sweep at five independent samples (`sample_index` 0 through 4). For each sample, the runner replays or records model responses under distinct cache keys, produces a complete aggregate adjudication result for that sample, and summarizes how key safety rates vary across the five samples.

**Why this priority**: N=5 sampling is a settled planning guardrail (§5, §9). The autonomous runner applies the same cache keying discipline as tier runners, with request-only context driving prompt identity.

**Independent Test**: Seed committed cache entries for all five sample indices for at least one subject; run the autonomous runner offline; verify five per-sample scoring results are produced and a variance summary reports whether over-erasure, over-retention, and mis-escalation rates differ across samples.

**Acceptance Scenarios**:

1. **Given** an autonomous sweep, **When** model responses are requested for a case, **Then** cache keys use `runner_id` `autonomous`, `case_id` from the export subject, `sample_index` 0–4, and a prompt hash derived from canonicalized request-only context.
2. **Given** five completed samples for an autonomous sweep, **When** runner output is inspected, **Then** it includes one aggregate adjudication scoring result per sample (five total), each covering all locations across all subjects in the sweep.
3. **Given** five per-sample scoring results, **When** the variance summary is inspected, **Then** it reports, for each standalone rate (over-erasure, over-retention, mis-escalation), the value at each sample index and whether the rate is identical across all five samples.
4. **Given** offline mode and a missing cache entry for any required sample index, **When** the sweep runs, **Then** the runner fails clearly at the miss rather than silently substituting another sample or calling a live model.

---

### User Story 5 - Acceptance Suite Defines Done Before Implementation (Priority: P2)

A reviewer merging the feature needs an autonomous acceptance suite written before implementation lands, failing for the right reason initially and passing when the retrieval tools, autonomous runner, and committed cache satisfy the contracts. The suite runs fully offline in continuous integration without a model API key.

**Why this priority**: Constitution Principle II requires evidentiary runner behavior to be contract-defined and test-gated before code ships.

**Independent Test**: Run the autonomous acceptance suite in offline mode on a clean clone; all tests pass with no network access and no secrets.

**Acceptance Scenarios**:

1. **Given** the feature branch before autonomous implementation, **When** the acceptance suite is executed, **Then** relevant tests fail because autonomous behavior is not yet present (not because of unrelated setup errors).
2. **Given** completed autonomous implementation, **When** the full autonomous acceptance suite runs with `CACHE_MODE=offline` and no model API key, **Then** all tests pass.
3. **Given** acceptance tests for ground-truth isolation, **When** retrieval tools or the autonomous runner assemble model-facing payloads, **Then** tests assert that `expected` fields never appear in tool responses, initial context, or cache-canonicalized payloads.
4. **Given** acceptance tests for configuration discipline, **When** the autonomous runner initializes, **Then** model identity and cache mode are read from environment configuration, not embedded as fixed literals in runner logic.
5. **Given** acceptance tests for frozen-interface discipline, **When** the suite runs, **Then** no test modifies committed export content, tier-runner modules, or adversarial-gate modules.

---

### User Story 6 - Validate Autonomous Evaluation via Quickstart Guide (Priority: P3)

An evaluator onboarding to the harness needs a quickstart document that walks through reproducing a green offline autonomous sweep from a clone, mirroring what continuous integration verifies.

**Why this priority**: Reproducibility requires a human-readable path, not only automated tests.

**Independent Test**: Follow the quickstart on a clean clone without an API key; confirm the autonomous sweep replays from committed cache and the autonomous acceptance suite is green.

**Acceptance Scenarios**:

1. **Given** the feature quickstart guide, **When** an evaluator follows setup and offline sweep steps, **Then** they can run the autonomous sweep without live model credentials.
2. **Given** the quickstart lint and test commands, **When** executed locally, **Then** outcomes match the continuous integration merge gate expectations for this feature.

---

### Edge Cases

- What happens when export provenance verification fails at export load? The sweep does not start; the runner surfaces the provenance error from the shared export loader.
- What happens when a subject has no locations? The runner visits the subject, retrieval tools return empty record sets, zero location pairs are appended, and the sweep continues without failing.
- What happens when the model returns a verdict outside {erase, retain, escalate}? The runner raises a validation error naming `subject_id`, `location_id`, and `sample_index`; it does not coerce the verdict.
- What happens when the model adjudicates without invoking any retrieval tools? The runner still grades verdicts against ground truth; `tool_calls` may be an empty list in the cache entry — this is a valid observable outcome, not an error.
- What happens when only some of the five sample indices have committed cache entries in offline mode? The sweep fails at the first cache miss with an explicit error identifying case, sample index, and `runner_id`.
- What happens when `CACHE_MODE=refresh` and credentials are present? The runner may fetch and persist new cache entries (including `tool_calls`) per the shared cache contract; default and CI behavior remain offline replay.
- What happens when a retrieval tool is invoked for a subject not in the export? The tool returns a documented error or empty result without leaking data from other subjects.
- What happens when two sweeps run sequentially (e.g., autonomous then T3)? Each produces independent results keyed by its own `runner_id`; runners do not share or overwrite one another's cache namespace.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST provide filesystem-backed retrieval tools under `core/tools/` that expose location records, retention-floor rules, and governance map data sourced from the committed frozen export.
- **FR-002**: Retrieval tools MUST return the same business content T2 and T3 pre-load into context (records with business fields; full rules corpus for floors and governance map) and MUST NOT include `expected` labels in any response.
- **FR-003**: Retrieval tools MUST read export data via the shared export loader pattern; they MUST NOT call a live agent, Postgres, or harness-side rule engines that regenerate labels.
- **FR-004**: The feature MUST provide an autonomous adjudication runner under `runners/autonomous/` that sweeps all labeled subjects from the committed frozen export.
- **FR-005**: The autonomous runner MUST supply request-only initial context to adjudication (equivalent to T1 pre-load) and MUST enable tool-use so the model may invoke retrieval tools during adjudication.
- **FR-006**: The autonomous runner MUST NOT pre-load location records, retention-floor text, or governance map into the initial context bundle passed to adjudication.
- **FR-007**: The runner MUST obtain per-location model verdicts through `ModelSeam.adjudicate` with tool-use enabled; runner logic MUST NOT hardcode a model provider or model identity.
- **FR-008**: Ground truth MUST be read from each location's `expected` block only; the runner MUST NOT infer labels from tool responses or model outputs.
- **FR-009**: The runner MUST pair each model verdict with its ground-truth label and aggregate results via the shared adjudication scoring primitive (`core.scoring.score_adjudication`); it MUST NOT re-implement adjudication rate math in the runner.
- **FR-010**: Model identity (`MODEL_ID`) and cache mode (`CACHE_MODE`) MUST be read from environment configuration at runner initialization; runner logic MUST NOT hardcode a model provider or model identity.
- **FR-011**: Default execution MUST replay model responses from the committed cache in offline mode; continuous integration MUST run without a model API key.
- **FR-012**: An explicit refresh path MUST remain available when cache mode is set to refresh and credentials are present, delegating to the shared cache contract.
- **FR-013**: Cache lookups for the autonomous runner MUST use `runner_id` `autonomous`, consistent with the cache contract.
- **FR-014**: Cache prompt identity for autonomous cases MUST be derived from canonicalized request-only context (not from full T2/T3 context bundles or tool-call payloads).
- **FR-015**: Committed cache entries for autonomous adjudication MUST populate the `tool_calls` field with an ordered trace of retrieval tool invocations when the model used tools; empty lists are valid when no tools were invoked.
- **FR-016**: The runner MUST request model responses at five samples per case (`sample_index` 0 through 4), producing distinct cache keys per sample.
- **FR-017**: For each sample index, the runner MUST aggregate all per-location prediction pairs across the full subject sweep into one adjudication scoring result via the shared scoring primitive.
- **FR-018**: Runner output MUST include five per-sample aggregate scoring results plus a variance summary comparing over-erasure, over-retention, and mis-escalation rates across samples.
- **FR-019**: Committed cache entries for `autonomous` MUST cover all export subjects and sample indices 0–4 sufficient for full offline CI replay.
- **FR-020**: An autonomous acceptance suite MUST exist under `tests/` (e.g., `tests/autonomous/` or `tests/runners/autonomous/`), written before implementation, and MUST pass fully offline when the feature is complete.
- **FR-021**: A feature quickstart guide (`specs/004-autonomous-retrieval-eval/quickstart.md`) MUST document clone-and-run steps to reproduce a green offline autonomous sweep and the autonomous acceptance suite locally.
- **FR-022**: Work MUST land on feature branch `004-autonomous-retrieval-eval`; the agent MAY commit to the feature branch but MUST NOT merge to `main` (human merge gate).
- **FR-023**: Vocabulary in autonomous-facing artifacts MUST use DPDP domain terms and the locked evaluation name *autonomous retrieval evaluation* in reader-facing copy; developer-facing identifiers use `autonomous` per cache and runner naming conventions.
- **FR-024**: The feature MUST NOT modify tier runners (`runners/t1.py`, `runners/t2.py`, `runners/t3.py`, shared tier spine), adversarial-gate runner modules, or committed export adjudication subject content.

### Key Entities

- **Retrieval tool**: A filesystem-backed callable that returns export-sourced data (location records, retention floors, or governance map) on demand; exposes T2/T3-equivalent information without pre-loading it into context.
- **Location-records tool**: Retrieves business fields for all locations of a given subject; mirrors T2 record inclusion rules.
- **Retention-floors tool**: Retrieves the full five sectoral retention-floor texts from the export rules corpus; mirrors T3 rules inclusion.
- **Governance-map tool**: Retrieves the full governance map from the export rules corpus; mirrors T3 rules inclusion.
- **Autonomous runner**: Evaluation executor with `runner_id` `autonomous` that sweeps all export subjects, invokes `adjudicate` with tool-use enabled and request-only initial context, and returns scored results.
- **Tool-call trace**: Ordered list of tool invocations persisted in a cache entry's `tool_calls` field, capturing tool identity and auditable argument/result summaries for offline replay and review.
- **Sample run**: One full subject sweep at a fixed `sample_index` (0–4), producing one aggregate adjudication scoring result.
- **Per-sample scoring result**: Confusion matrix and standalone over-erasure, over-retention, and mis-escalation rates for all graded location pairs at one sample index.
- **Variance summary**: Autonomous-runner report comparing standalone safety rates across the five per-sample scoring results.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone with no model API key, the autonomous acceptance suite completes with all tests green in offline cache mode.
- **SC-002**: A full autonomous sweep processes 100% of labeled subjects in the committed export (zero subjects silently skipped).
- **SC-003**: Offline replay produces five distinct per-sample aggregate scoring results when committed cache entries exist for all five sample indices across the export.
- **SC-004**: For each sample, over-erasure, over-retention, and mis-escalation rates match independently hand-calculated values from the same prediction–ground-truth pairs.
- **SC-005**: Retrieval tools return data equivalent to T2/T3 context builders on representative export subjects, verified by acceptance tests comparing tool output to builder output field-for-field (excluding `expected`).
- **SC-006**: Committed autonomous cache entries include `tool_calls` traces for entries where tool use occurred; tier-runner cache entries remain without tool traces.
- **SC-007**: No acceptance scenario requires editing committed export adjudication subjects, tier-runner modules, or adversarial-gate modules after commitment; all new coverage is additive.
- **SC-008**: An evaluator following the feature quickstart reproduces a green offline autonomous sweep in under 10 minutes on a standard developer machine (excluding optional refresh steps).
- **SC-009**: Re-running the same autonomous sweep twice in offline mode with the same committed cache yields identical per-sample scoring results (deterministic replay).
- **SC-010**: The full export subject set replays from committed autonomous cache with no live model calls in CI.

## Assumptions

- Feature 001 (shared core) is complete: export loader, model seam with `adjudicate`, cache (including `tool_calls` field), and adjudication scoring primitives are available.
- Features 002 (context-tier sweep) and 003 (adversarial gate) are complete or merged: runner spine patterns (config loading, sample loop, variance summary, offline cache discipline) serve as reference implementation only; this feature does not modify those runners.
- Initial adjudication context is request-only (T1-equivalent); the model retrieves T2/T3-equivalent information exclusively via tools during the adjudication session.
- Three retrieval tools cover the T2/T3 information layers: location records (T2), retention floors (T3), and governance map (T3). Exact tool naming is deferred to the plan phase; the spec requires functional parity with tier builders.
- The model seam will be extended (or wrapped) to support tool-use during `adjudicate` for the autonomous runner; tier and gate runners continue using the existing seam operations unchanged.
- Primary model identity is configuration supplied at run time; the spec does not fix a model string, consistent with planning §11.
- Per-sample aggregate scoring (one adjudication result per sample index covering the entire export) is the primary reporting unit; the variance summary rolls up across those five results.
- Prompt hash for autonomous cache keys canonicalizes request-only context, consistent with T1 cache identity — not T3 full context or dynamic tool-call sequences.
- Tool-call trace schema (fields per trace item) is defined in the plan/contracts phase; the spec requires ordered, auditable traces sufficient for offline review.

## Dependencies

- Constitution: `.specify/memory/constitution.md` (Principles I–IV, VII, VIII).
- Canonical planning: `Planning/dpdp_eval_harness_planning.md` (§4 autonomous retrieval evaluation, §5 adjudication scoring, §7 architecture, §8 feature breakdown, §9 guardrails).
- ADR-0001: frozen export as deterministic ground truth (`docs/adr/0001-frozen-export-ground-truth.md`).
- Feature 001 spec and contracts: `specs/001-shared-core/spec.md`, `specs/001-shared-core/contracts/cache.md` (`runner_id` `autonomous`, `tool_calls`), `specs/001-shared-core/contracts/model-seam.md`, `specs/001-shared-core/contracts/scoring.md`, `specs/001-shared-core/contracts/context-tiers.md`, `specs/001-shared-core/contracts/frozen-export.md`.
- Feature 002 spec and runner patterns (reference only): `specs/002-context-tier-sweep/spec.md`, `specs/002-context-tier-sweep/contracts/runner-spine.md`, `specs/002-context-tier-sweep/contracts/sweep-result.md`, `specs/002-context-tier-sweep/contracts/tier-runner.md`.
- Feature 003 spec (boundary reference only): `specs/003-adversarial-gate/spec.md`.

## Out of Scope

- T1/T2/T3 adjudication tier sweeps (Feature 002 — already shipped; MUST NOT be modified).
- Adversarial-gate evaluation (Feature 003 — already shipped; MUST NOT be modified).
- Editing existing committed export adjudication subjects or adversarial seed content (frozen-interface discipline).
- Wilson confidence intervals or per-family adversarial reporting (Feature 003 reporting layer).
- Command-line entrypoints and prose thesis writeup.
- Live agent calls, Postgres, or harness-side rule engines that regenerate labels.
- Re-implementing adjudication rate proportion math in `core/scoring` (use existing primitives only).
- Blended accuracy or other single headline scores that subsume over-erasure, over-retention, or mis-escalation rates.
- Pre-loading records or rules into autonomous initial context (that would collapse the evaluation into a tier runner).

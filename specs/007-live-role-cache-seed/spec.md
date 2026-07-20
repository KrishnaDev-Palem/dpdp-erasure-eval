# Feature Specification: Live Role Cache Seeding

**Feature Branch**: `007-live-role-cache-seed`

**Status**: Accepted

## Clarifications

- Q: Should the live-role cache entries be committed in this feature PR, or remain operator-generated with only a subset committed for replay testing? → A: Commit the full live-role cache set in this feature PR; CI replay tests run against committed entries.
- Q: For the gemini-3.5-flash adversarial_gate cache — full extended-slice coverage or a representative subset? → A: Full parity: all ~90 slice cases × 5 samples (≈450 entries); offline gate sweep must replay with zero cache misses.
- Q: For claude-sonnet-5 T2 and autonomous caches — full 10-entry parity per runner or a minimal miss-only seed? → A: Full 10-entry parity per runner (2 subjects × 5 samples for both T2 and autonomous).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Committed Live-Role Cache for Evaluation (Priority: P1)

An evaluator running evaluation comparisons needs committed cache entries for each supported live model role — Claude Sonnet 5 and Gemini 3.5 Flash — so published evaluation numbers can be reproduced offline without provider API keys. The committed cache must cover the full evaluation matrix for the three in-scope runner paths (T2 tier sweep, adversarial gate, autonomous), matching the subject/case and sample coverage already established under the primary model role.

**Why this priority**: Feature 006 SC-002 proved refresh-and-replay for a single entry per role; this feature completes that success criterion at full sweep cardinality and makes live-model results durable artifacts for evaluation.

**Independent Test**: Clone the repository with no API keys, set `MODEL_ID` to each live role and `CACHE_MODE=offline`, run T2, adversarial-gate, and autonomous sweeps; verify each completes with exit code 0 and deterministic results from committed live-role cache namespaces.

**Acceptance Scenarios**:

1. **Given** committed cache under `cache/claude-sonnet-5/t2/` covering all scored T2 subjects × sample indices 0–4, **When** an operator runs the T2 sweep offline with `MODEL_ID=claude-sonnet-5`, **Then** the sweep completes without cache misses and produces deterministic verdicts from committed entries.
2. **Given** committed cache under `cache/gemini-3.5-flash/adversarial_gate/` covering all extended-slice cases × sample indices 0–4, **When** an operator runs the adversarial-gate sweep offline with `MODEL_ID=gemini-3.5-flash`, **Then** the sweep completes without cache misses and produces deterministic classification outcomes.
3. **Given** committed cache under `cache/claude-sonnet-5/autonomous/` covering all autonomous subjects × sample indices 0–4 with `tool_calls` traces, **When** an operator runs the autonomous sweep offline with `MODEL_ID=claude-sonnet-5`, **Then** the sweep completes without cache misses and replays tool-call traces per the autonomous cache contract.
4. **Given** committed `cache/primary/` entries, **When** Feature 007 lands, **Then** no primary-namespace cache files are modified, overwritten, deleted, or added.
5. **Given** committed `export/` content, **When** Feature 007 lands, **Then** frozen export remains unchanged (no modification, overwrite, deletion, or addition).

---

### User Story 2 - Operator Refresh Workflow for Live-Role Cache Generation (Priority: P1)

An operator with valid provider credentials needs step-by-step documentation to regenerate the full live-role cache set using Feature 006's refresh path (`CACHE_MODE=refresh`, `create_model_seam`, live adapters). The workflow must specify which model role runs which runner path, expected API-call counts, and how to verify offline replay before committing entries.

**Why this priority**: Committed cache entries originate from operator-driven refresh; without clear documentation the seeding process is error-prone and unauditable.

**Independent Test**: Follow the feature quickstart (PowerShell and Bash variants) with valid credentials; run each in-scope refresh sweep; verify written entries land only under the correct live-role namespaces; switch to offline mode and confirm replay parity.

**Acceptance Scenarios**:

1. **Given** quickstart documentation, **When** an operator refreshes the T2 sweep with `MODEL_ID=claude-sonnet-5` and `CACHE_MODE=refresh`, **Then** exactly 10 cache entries are written under `cache/claude-sonnet-5/t2/` (2 scored subjects × 5 samples).
2. **Given** quickstart documentation, **When** an operator refreshes the adversarial-gate sweep with `MODEL_ID=gemini-3.5-flash` and `CACHE_MODE=refresh`, **Then** cache entries are written under `cache/gemini-3.5-flash/adversarial_gate/` for all extended-slice cases × 5 samples (~450 classifications).
3. **Given** quickstart documentation, **When** an operator refreshes the autonomous sweep with `MODEL_ID=claude-sonnet-5` and `CACHE_MODE=refresh`, **Then** exactly 10 cache entries are written under `cache/claude-sonnet-5/autonomous/` (2 subjects × 5 samples), each including ordered `tool_calls` traces where tool-use occurred.
4. **Given** quickstart cost estimates, **When** an operator plans a full gate refresh, **Then** documentation states approximately 450 provider classification calls (90 slice cases × 5 samples).
5. **Given** refresh completes, **When** the operator switches to `CACHE_MODE=offline` and re-runs the same sweep, **Then** results match the refresh run with no live calls.

---

### User Story 3 - CI-Gated Offline Replay Acceptance for Live Roles (Priority: P1)

A CI merge gate and any clone-and-run evaluator need acceptance tests that prove live-role cache replay works offline with zero provider keys. Tests must cover all three in-scope runner paths and the corresponding CLI subcommands, asserting exit code 0 and deterministic output from committed cache.

**Why this priority**: Constitution Principle IV requires offline CI with no secrets. Live-role cache is only valuable if replay is continuously verified in the merge gate.

**Independent Test**: Run `uv run pytest -v` on a clean clone with no API keys; verify new live-role offline replay acceptance tests pass alongside Features 001–006 regression suites.

**Acceptance Scenarios**:

1. **Given** default CI configuration (no provider keys, `CACHE_MODE=offline`), **When** the full acceptance suite runs, **Then** all tests pass including new live-role offline replay tests.
2. **Given** `MODEL_ID=claude-sonnet-5` and offline mode, **When** T2 and autonomous acceptance tests and `dpdp-eval t2` / `dpdp-eval autonomous` CLI invocations run, **Then** each exits 0 with deterministic results from `cache/claude-sonnet-5/`.
3. **Given** `MODEL_ID=gemini-3.5-flash` and offline mode, **When** adversarial-gate acceptance tests and `dpdp-eval adversarial-gate` CLI invocation run, **Then** each exits 0 with deterministic results from `cache/gemini-3.5-flash/`.
4. **Given** Features 001–006 acceptance suites, **When** executed after Feature 007 lands, **Then** every previously passing offline test continues to pass.
5. **Given** live refresh operations, **When** CI runs, **Then** refresh and live-smoke paths are excluded from the merge gate — only offline replay tests execute.

---

### User Story 4 - README On-Ramp for Live-Role Evaluations (Priority: P2)

An evaluator reading the repository README needs a clear path to run evaluations against committed live-role cache (not only the primary test-double role), with links to the Feature 007 quickstart for offline replay and optional refresh.

**Why this priority**: README is the constitution-mandated on-ramp; readers must discover how to reproduce live-model numbers without hunting through feature docs.

**Independent Test**: Follow README instructions with `MODEL_ID=claude-sonnet-5` or `gemini-3.5-flash` and `CACHE_MODE=offline`; verify evaluation commands complete using committed live-role cache.

**Acceptance Scenarios**:

1. **Given** the README evaluation section, **When** an evaluator sets `MODEL_ID` to a live role and `CACHE_MODE=offline`, **Then** documentation explains how to run T2, adversarial-gate, and autonomous evaluations from committed cache without API keys.
2. **Given** README links, **When** an evaluator needs refresh or verification steps, **Then** README links to the Feature 007 quickstart.

---

### Edge Cases

- What happens when a live-role cache entry is missing for one subject/sample combination — offline sweep surfaces a clear cache miss error; no silent fallback to primary cache or live calls.
- What happens when refresh is interrupted mid-sweep — partial entries may exist; operator must re-run refresh for misses; acceptance tests require full coverage before merge.
- What happens when an operator sets `MODEL_ID=primary` — behavior unchanged from Features 001–006; primary cache namespace remains authoritative for the test-double role.
- What happens when refresh writes to the wrong namespace — entries under `cache/primary/` or `export/` must never be created or modified by live-role refresh; quickstart must warn operators to verify namespace before commit.
- What happens when autonomous cache entries lack `tool_calls` — entries written during refresh for the autonomous runner must include tool-call traces per Feature 004/006 contracts; malformed entries must not be committed.
- What happens when gate refresh cost exceeds operator budget — quickstart documents ~450 classification calls so operators can plan; partial gate seeding is insufficient for acceptance (full slice coverage required).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST commit the full live-role cache set in this feature's pull request, under separate namespaces only: `cache/claude-sonnet-5/{t2,autonomous}/` and `cache/gemini-3.5-flash/adversarial_gate/`. Deferring cache commitment to operator-local artifacts is not acceptable — CI replay tests run against committed entries.
- **FR-002**: System MUST NOT modify, overwrite, delete, or add any files under `cache/primary/` or `export/` as part of this feature.
- **FR-003**: T2 live-role cache MUST cover the same scored subject and sample matrix as `cache/primary/t2/`: 2 scored subjects × 5 samples (10 entries total). Minimal miss-only or reduced-sample seeds do not satisfy acceptance.
- **FR-004**: Adversarial-gate live-role cache MUST cover the same extended-slice case and sample matrix as `cache/primary/adversarial_gate/`: 90 slice cases × 5 samples (450 entries total; verified in research R1). Representative-subset or reduced-sample seeding does not satisfy acceptance; the offline gate sweep must replay with zero cache misses.
- **FR-005**: Autonomous live-role cache MUST cover the same subject and sample matrix as `cache/primary/autonomous/`: 2 subjects × 5 samples (10 entries total), with `tool_calls` traces included in each entry. Minimal miss-only or reduced-sample seeds do not satisfy acceptance.
- **FR-006**: System MUST use Feature 006 refresh infrastructure (`create_model_seam`, live adapters, `CACHE_MODE=refresh`) for cache generation — MUST NOT re-implement adapters or factory.
- **FR-007**: System MUST add CI-gated acceptance tests that run with `CACHE_MODE=offline`, zero API keys, and `MODEL_ID` set to each live role, asserting T2, adversarial-gate, and autonomous sweeps complete with exit code 0 and deterministic results.
- **FR-008**: System MUST add CI-gated acceptance tests (or CLI integration checks) verifying `dpdp-eval t2`, `dpdp-eval adversarial-gate`, and `dpdp-eval autonomous` subcommands succeed offline against committed live-role cache.
- **FR-009**: System MUST document step-by-step refresh and offline replay verification in feature quickstart with both PowerShell and Bash examples.
- **FR-010**: Quickstart MUST include cost and API-call count estimates for full adversarial-gate refresh (~450 classifications).
- **FR-011**: Live refresh operations MUST remain excluded from the CI merge gate; only offline replay tests run in default CI.
- **FR-012**: System MUST update README to link to Feature 007 quickstart and document running evaluations against live-role cache (`MODEL_ID=claude-sonnet-5` or `gemini-3.5-flash`, `CACHE_MODE=offline`).
- **FR-013**: All Features 001–006 offline acceptance suites MUST remain green with zero provider keys after Feature 007 lands.
- **FR-014**: Committed live-role cache entries MUST conform to the existing cache key schema and entry format from Feature 001 — no breaking changes to cache contract.
- **FR-015**: Cache generation MUST be operator-driven with human review before merge — no automated commit of live-generated entries without explicit review.

### Key Entities

- **Live-role cache namespace**: A committed cache subtree keyed by live `MODEL_ID` (`claude-sonnet-5`, `gemini-3.5-flash`) separate from the `primary` test-double namespace.
- **Cache entry**: Persisted model response (and optional `tool_calls` trace for autonomous) at canonical key `{model_id}/{runner_id}/{case_id}/{prompt_hash}/{sample_index}.json`.
- **Runner path**: One of three in-scope evaluation sweeps — T2 tier (`t2`), adversarial gate (`adversarial_gate`), autonomous (`autonomous`) — each bound to a specific live model role for refresh.
- **Refresh sweep**: Operator opt-in run with `CACHE_MODE=refresh` that invokes live adapters on cache miss and writes entries to the live-role namespace.
- **Offline replay sweep**: Default run with `CACHE_MODE=offline` that reads committed live-role entries with no network or API keys.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Feature 006 SC-002 is fully satisfied — committed cache exists for each supported live model role with full in-scope runner coverage (T2: 10 entries, gate: 450 entries, autonomous: 10 entries) and offline replay produces identical results to refresh.
- **SC-002**: Default CI (`uv run pytest -v`) passes with 100% success rate and zero provider API keys; `cache/primary/` and `export/` are unchanged by the feature branch (no modification, overwrite, deletion, or addition).
- **SC-003**: Features 001–006 regression acceptance suites remain green — no breaking changes to existing offline contracts.
- **SC-004**: An evaluator following README and quickstart can run all three in-scope evaluation paths against live-role cache in under 5 minutes total on a clean clone (offline, no keys).
- **SC-005**: Quickstart documents expected API-call counts: T2 refresh ≤10 adjudication calls, autonomous refresh ≤10 adjudication calls (with tool rounds), gate refresh ~450 classification calls.

## Assumptions

- Feature 006 live model seam (factory, Anthropic and Gemini adapters, credential resolution, refresh mode) is complete and stable; this feature consumes it without adapter changes except bugfixes discovered during refresh.
- Scored T2 subject count (2) and autonomous subject count (2) match the existing `cache/primary/` seeding from Features 002 and 004.
- Extended adversarial slice case count (90) matches Feature 003 committed cache; 90 × 5 samples = ~450 gate classifications.
- Live-role cache entries are committed to the feature branch after operator refresh and human diff review — not generated in CI.
- T1 and T3 live-role cache are out of scope unless needed incidentally for cross-tier library support (not required for this feature).
- Multi-model parallel sweeps in one invocation remain out of scope.
- Provider billing and network connectivity are available to the operator performing refresh locally.

## Dependencies

- Feature 006: `create_model_seam`, `AnthropicModelSeam`, `GeminiModelSeam`, `CACHE_MODE=refresh`, role registry (`claude-sonnet-5`, `gemini-3.5-flash`).
- Feature 001: cache key schema, entry format, offline/refresh mode semantics.
- Features 002–004: T2, adversarial-gate, and autonomous runners and their primary-cache coverage matrices.
- Feature 005: CLI subcommands (`t2`, `adversarial-gate`, `autonomous`) that honor `MODEL_ID` and `CACHE_MODE`.

## Out of Scope (v1)

- T1 and T3 live-role cache seeding (unless incidentally required for shared library code — not a deliverable).
- Multi-model parallel sweeps in a single CLI invocation.
- Automated commit of live-generated cache without human review.
- Prose writeup or blog content.
- Modifying frozen export content.
- Re-implementing Feature 006 adapters or factory (bugfixes only if discovered during refresh).
- Changing committed `cache/primary/` entries.

# Live-Role Cache Seeding Requirements Checklist: Feature 007

**Purpose**: Unit-test the Feature 007 requirements for SC-002 completion, cache namespace isolation, offline CI guarantees, live refresh cost/operator boundaries, and acceptance coverage across the three in-scope runner paths — validating requirement quality before `/speckit-plan`.
**Created**: 2026-07-12
**Feature**: [spec.md](../spec.md)
**Depth**: Standard (pre-planning requirements gate)
**Audience**: Spec author and PR reviewer

## SC-002 Completion & Coverage Completeness

- [x] CHK001 - Is "Feature 006 SC-002 fully satisfied" defined with per-runner measurable coverage counts rather than by reference alone? [Measurability, Spec SC-001]
- [x] CHK002 - Is "offline replay produces identical results to refresh" specified with explicit comparison criteria (verdicts, classification outcomes, tool-call traces, report output — which of these must match)? [Clarity, Spec SC-001, US2-AS5]
- [x] CHK003 - Are exact entry counts and their derivations documented for every namespace (T2: 2×5=10, gate: 90×5≈450, autonomous: 2×5=10)? [Completeness, Spec FR-003, FR-004, FR-005]
- [x] CHK004 - Is the "~450" gate approximation resolved to an authoritative count source (Feature 003 committed slice case list) instead of an assumed 90? [Ambiguity, Spec FR-004, Assumptions]
- [x] CHK005 - Is the assumption that scored T2 subjects (2) and autonomous subjects (2) match `cache/primary/` seeding validated against Features 002/004 artifacts rather than restated? [Assumption, Spec Assumptions]
- [x] CHK006 - Is "deterministic results" in offline replay quantified (identical output across repeated runs? byte-identical cache reads? identical rendered tables)? [Clarity, Spec US1, FR-007]
- [x] CHK007 - Do FR-005 ("tool_calls traces included in each entry") and US2 scenario 3 ("where tool-use occurred") state consistent requirements for autonomous entries where the model used no tools? [Conflict, Spec FR-005, US2-AS3]
- [x] CHK008 - Are autonomous `tool_calls` trace format requirements traced to the governing contract (Feature 004 tool-call-trace / Feature 006 live-adapters) rather than left implicit? [Traceability, Spec FR-005, Dependencies]

## Cache Namespace Isolation from Primary

- [x] CHK009 - Are all committed live-role namespace paths exhaustively enumerated, and is it explicit that no other live-role/runner combinations (e.g., `gemini-3.5-flash/t2/`) are created? [Completeness, Spec FR-001]
- [x] CHK010 - Is the `cache/primary/` and `export/` immutability requirement stated with a verifiable acceptance method (e.g., diff scope assertion on the feature branch)? [Measurability, Spec FR-002, SC-002]
- [x] CHK011 - Are requirements defined for detecting or preventing refresh writes to the wrong namespace, beyond the quickstart warning to operators? [Gap, Spec Edge Cases]
- [x] CHK012 - Is silent fallback from a live-role namespace to `cache/primary/` (or to live calls) on cache miss explicitly prohibited in requirements, not only in edge-case narrative? [Completeness, Spec Edge Cases, FR-007]
- [x] CHK013 - Are FR-002 and User Story 1 acceptance scenarios 4–5 consistent about what "unchanged" covers (modification, overwrite, deletion, and addition of files under protected paths)? [Consistency, Spec FR-002, US1-AS4, US1-AS5]
- [x] CHK014 - Is the out-of-scope carve-out "T1 and T3 unless incidentally required for shared library code" bounded clearly enough to prevent silent scope creep into new namespaces? [Ambiguity, Spec Out of Scope, Assumptions]
- [x] CHK015 - Is the requirement that committed entries conform to the Feature 001 cache key schema (`{model_id}/{runner_id}/{case_id}/{prompt_hash}/{sample_index}.json`) stated with a validation mechanism? [Measurability, Spec FR-014, Key Entities]

## Offline CI Guarantees

- [x] CHK016 - Are CI preconditions for the new replay tests fully specified (zero provider keys, `CACHE_MODE=offline`, `MODEL_ID` per live role, exit code 0)? [Completeness, Spec FR-007, US3-AS1]
- [x] CHK017 - Is the exclusion of refresh and live-smoke paths from the merge gate stated as a requirement independent of any particular pytest marker mechanism? [Clarity, Spec FR-011, US3-AS5]
- [x] CHK018 - Is the Features 001–006 regression guarantee (FR-013) measurable — does it define "remain green" as the full existing suite passing under default CI configuration? [Measurability, Spec FR-013, SC-003]
- [x] CHK019 - Are requirements defined for CI-visible failure behavior when a committed live-role entry is missing (clear cache-miss error vs. silent skip)? [Edge Case, Spec Edge Cases]
- [x] CHK020 - Do FR-007 (acceptance tests) and FR-008 (CLI integration checks) delineate non-overlapping responsibilities, or is the boundary between them ambiguous for a test author? [Consistency, Spec FR-007, FR-008]
- [x] CHK021 - Is the constitution's no-secrets merge gate requirement (Principle IV) explicitly satisfied by the CI requirements as written, including for the new live-role test IDs? [Traceability, Spec US3, Constitution Principle IV]

## Live Refresh Cost & Operator Boundaries

- [x] CHK022 - Are cost estimates required in defined units — API-call counts only, or also monetary bounds against the constitution's tens-of-dollars ceiling? [Clarity, Spec FR-010, SC-005, Constitution Principle VIII]
- [x] CHK023 - Is the autonomous refresh call bound ("≤10 adjudication calls with tool rounds") specified precisely enough to be checkable, given tool rounds multiply provider requests per adjudication? [Measurability, Spec SC-005]
- [x] CHK024 - Are recovery requirements for interrupted refresh defined (identifying partial entries, re-running for misses, criteria for commit-readiness)? [Coverage, Spec Edge Cases]
- [x] CHK025 - Is the human-review requirement (FR-015) specified with reviewable criteria — what the reviewer must verify in the cache diff (namespace, entry count, schema, no primary/export changes)? [Clarity, Spec FR-015]
- [x] CHK026 - Does FR-009 require PowerShell and Bash examples for every in-scope refresh sweep and for offline replay verification, or only for a subset? [Completeness, Spec FR-009, US2]
- [x] CHK027 - Is the operator obligation to verify namespace correctness before commit captured as a quickstart requirement rather than only as edge-case narrative? [Gap, Spec Edge Cases, FR-009]
- [x] CHK028 - Is the boundary "bugfixes only if discovered during refresh" for Feature 006 adapters bounded with a criterion distinguishing a bugfix from a behavior change requiring re-planning? [Ambiguity, Spec Assumptions, Out of Scope]

## Acceptance Test Coverage — T2, Adversarial Gate, Autonomous per Role

- [x] CHK029 - Are the three role/runner bindings (T2 → `claude-sonnet-5`, adversarial gate → `gemini-3.5-flash`, autonomous → `claude-sonnet-5`) fixed as requirements, with cross-combinations explicitly out of scope? [Clarity, Spec FR-001, Key Entities]
- [x] CHK030 - Do replay acceptance requirements state what is asserted beyond exit code 0 — deterministic verdicts, classification outcomes, and tool-call trace replay per runner? [Completeness, Spec FR-007, US1-AS1–AS3]
- [x] CHK031 - Are CLI acceptance requirements explicit about how `MODEL_ID` and `CACHE_MODE` are supplied to `dpdp-eval t2` / `adversarial-gate` / `autonomous` invocations under test? [Clarity, Spec FR-008, Dependencies]
- [x] CHK032 - Is SC-004's "under 5 minutes on a clean clone" measurable with defined environment assumptions (machine class, `uv sync` included or excluded)? [Measurability, Spec SC-004]
- [x] CHK033 - Are zero-cache-miss assertions required for all three sweeps, consistently phrased across FR-004, US1 scenarios, and US3 test requirements? [Consistency, Spec FR-004, US1, US3]
- [x] CHK034 - Are README documentation requirements (FR-012) specific about which evaluation paths and roles are covered, and do they align with the reader-facing vocabulary rule? [Completeness, Spec FR-012, Constitution Principle V]

## Dependencies, Assumptions & Currency

- [x] CHK035 - Is the assumption that Feature 006 is "complete and stable" reconciled with SC-001's statement that 006 SC-002 is not yet fully satisfied? [Conflict, Spec Assumptions, SC-001]
- [x] CHK036 - Are provider model identifier strings (`claude-sonnet-5`, `gemini-3.5-flash`) subject to a stated web-verification step before commitment, per Currency Before Communication? [Traceability, Spec Dependencies, Constitution Principle VI]
- [x] CHK037 - Is the dependency on Feature 005 CLI honoring `MODEL_ID`/`CACHE_MODE` validated as an existing capability rather than assumed? [Assumption, Spec Dependencies]

## Notes

- Check items off as completed: `[x]`
- Add findings inline; unresolved items should feed `/speckit-clarify` or spec edits before `/speckit-plan`
- Traceability: 37/37 items carry a spec-section or constitution reference / gap marker

## Validation Notes

**Iteration 2 (2026-07-14)**: Implementation complete — SC-001/SC-005 satisfied.

- 470 committed live-role cache entries (10 T2 + 450 gate + 10 autonomous) with offline
  replay tests green (`270 passed` merge gate with `MODEL_ID=primary`).
- Protected paths unchanged (`cache/primary/`, `export/` diff-empty).
- Pre-planning CHK items addressed via research.md R1–R9, contracts, and quickstart
  operator observations (Gemini billing requirement, autonomous empty-verdict retry,
  adapter bugfix for T1-context tool sessions per R9 boundary).

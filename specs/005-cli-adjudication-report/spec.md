# Feature Specification: CLI and Adjudication Report

**Feature Branch**: `005-cli-adjudication-report`

**Created**: 2026-07-07

**Status**: Draft

**Input**: User description: "Build Feature 005: CLI and Adjudication Report — the cross-cutting integration layer deferred from Features 001–004. Deliver adjudication reporting (Wilson CIs on standalone safety rates, per-lane confusion matrix, N=5 sample rollups, cross-sample variance, cross-tier comparison), a `dpdp-eval` CLI with tier/autonomous/gate subcommands, and acceptance suites for report and CLI — all offline in CI with no model API key."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Adjudication Report Tables with Wilson Confidence Intervals (Priority: P1)

An evaluator publishing context-tier or autonomous retrieval findings needs a reporting layer that consumes completed sweep results from tier runners (T1, T2, T3) or the autonomous runner and emits adjudication report tables. For the selected primary sample, the report MUST include Wilson confidence intervals on standalone over-erasure, over-retention, and mis-escalation rates; the per-lane confusion matrix from that sample's scoring; five sample rollups (N=5) each with Wilson-augmented metrics; and the cross-sample variance summary already produced by the runner — without re-deriving rate numerators or denominators.

**Why this priority**: Features 001–004 ship runners and scoring primitives but defer Wilson intervals and human-consumable adjudication tables to this integration layer. Without it, sweep results cannot be published or compared in thesis-ready form.

**Independent Test**: Feed a hand-crafted `TierSweepResult` or `AutonomousSweepResult` with known numerators and denominators into `build_tier_adjudication_report`; verify Wilson bounds, rate fidelity, zero-denominator nulls, confusion matrix shape, five rollups, and variance passthrough match independently hand-calculated values and the adjudication-report contract.

**Acceptance Scenarios**:

1. **Given** a completed tier or autonomous sweep result, **When** `build_tier_adjudication_report(sweep, sample_index=0)` runs, **Then** the output includes `primary_metrics` with Wilson-augmented over-erasure, over-retention, and mis-escalation rates sourced from the primary sample's scoring result.
2. **Given** the primary sample's aggregate scoring result, **When** the report is built, **Then** `confusion_matrix` matches the runner scoring output for that sample unchanged — the report layer does not recompute matrix cells.
3. **Given** five per-sample scoring results in the sweep, **When** the report is built, **Then** `sample_rollups` contains exactly five entries (sample indices 0–4), each with Wilson-augmented standalone rates.
4. **Given** a sweep result with a variance summary, **When** the report is built, **Then** `variance` is passed through from the sweep result unchanged.
5. **Given** a hand-crafted scoring result with zero denominator for any standalone rate, **When** the report layer builds metrics, **Then** the affected `Rate.value`, Wilson bounds, and `RateWithCI.interval` are all `null` (same zero-denominator rule as the gate report).
6. **Given** any adjudication report table output, **When** fields are inspected, **Then** prohibited fields (`accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`) do not appear.
7. **Given** representative hand-calculated fixtures, **When** acceptance tests compare report output, **Then** Wilson interval bounds match within documented tolerance using the shared `report/wilson.py` implementation — Wilson math MUST NOT live in `core/scoring`.

---

### User Story 2 - Cross-Tier Comparison Table (Priority: P1)

An evaluator comparing the ablation ladder needs a cross-tier comparison table that places T1, T2, T3, and autonomous retrieval side by side at a chosen sample index, showing Wilson-augmented standalone safety rates for each tier without blended accuracy.

**Why this priority**: The thesis depends on isolating context effects across tiers. A four-row comparison table is the primary integration artifact tying Features 002 and 004 together.

**Independent Test**: Provide four completed sweep results (t1, t2, t3, autonomous) with known rates; call `build_cross_tier_comparison(t1, t2, t3, autonomous, sample_index=N)`; verify exactly four rows in order (t1, t2, t3, autonomous) with correct Wilson-augmented rates for sample N.

**Acceptance Scenarios**:

1. **Given** completed sweep results for all four evaluations, **When** `build_cross_tier_comparison` runs with `sample_index=0`, **Then** the output contains exactly four rows labeled t1, t2, t3, and autonomous.
2. **Given** a non-default `--sample-index` value (0–4), **When** the cross-tier table is built, **Then** all four rows use metrics from that sample index consistently.
3. **Given** any cross-tier row, **When** rate fields are inspected, **Then** each row exposes over-erasure, over-retention, and mis-escalation as separate `RateWithCI` fields — no blended accuracy or single headline score.
4. **Given** a tier with zero denominator for a rate at the selected sample, **When** the comparison row is built, **Then** that rate's value and Wilson interval are `null`.

---

### User Story 3 - CLI Entrypoint for All Evaluations (Priority: P1)

An evaluator reproducing published numbers from a clone needs a single command-line entrypoint (`dpdp-eval`) that runs any evaluation (T1, T2, T3, autonomous, adversarial-gate), builds the appropriate report tables, and emits human-readable stdout or structured JSON. The CLI MUST support writing output to a file, selecting the primary sample index, and configuring export and cache roots — all without live model credentials in default offline mode.

**Why this priority**: Features 001–004 implement runners and gate reporting but defer a unified operator surface. The CLI is the primary human and automation interface for reproducing thesis tables.

**Independent Test**: Run each subcommand on a clean clone with `CACHE_MODE=offline` and no `MODEL_API_KEY`; verify exit code 0, expected JSON keys or human-readable labels, `--output` file creation, and `--sample-index` honored for adjudication subcommands.

**Acceptance Scenarios**:

1. **Given** a clean clone with committed cache, **When** `dpdp-eval t1`, `t2`, `t3`, `autonomous`, or `adversarial-gate` runs without flags, **Then** each subcommand exits 0 and emits human-readable report output without live model credentials.
2. **Given** any adjudication subcommand with `--json`, **When** the command completes, **Then** stdout is valid JSON matching the adjudication report schema (tier reports) or gate report schema (gate subcommand).
3. **Given** `--output PATH`, **When** any subcommand completes, **Then** the same report content is written to the specified path.
4. **Given** `--sample-index N` where N is 0–4, **When** an adjudication subcommand runs, **Then** primary metrics and confusion matrix reflect sample N while all five sample rollups remain present.
5. **Given** default CLI initialization, **When** a subcommand runs, **Then** the injected model seam replays from committed cache (offline default) and respects `MODEL_ID` and `CACHE_MODE` from environment via runner configuration — not hardcoded literals.
6. **Given** the adversarial-gate subcommand, **When** it completes, **Then** output is produced via the existing gate report builder and formatter (`build_gate_report` / `format_gate_report`) — not reimplemented in the CLI.
7. **Given** optional flags `--export-dir` and `--cache-root`, **When** provided, **Then** runners resolve export and cache paths from those values instead of defaults.

---

### User Story 4 - Acceptance Suite Defines Done Before Implementation (Priority: P2)

A reviewer merging the feature needs adjudication-report and CLI acceptance suites written before implementation lands, failing for the right reason initially and passing when the reporting layer, CLI, and committed cache satisfy the contracts. Both suites MUST run fully offline in continuous integration without a model API key.

**Why this priority**: Constitution Principle II requires evidentiary integration behavior to be contract-defined and test-gated before code ships.

**Independent Test**: Run `tests/report/test_acceptance_adjudication_report.py` and `tests/cli/test_acceptance_cli.py` in offline mode on a clean clone; all tests pass with no network access and no secrets.

**Acceptance Scenarios**:

1. **Given** the feature branch before report/CLI implementation, **When** the acceptance suites execute, **Then** relevant tests fail because report or CLI behavior is not yet present (not because of unrelated setup errors).
2. **Given** completed implementation, **When** both acceptance suites run with `CACHE_MODE=offline` and no model API key, **Then** all tests pass.
3. **Given** report acceptance tests, **When** they run, **Then** they verify Wilson parity (hand-calculated), rate numerator/denominator fidelity to runner scoring, zero-denominator nulls, confusion matrix and five rollups, absence of blended accuracy fields, and four-row cross-tier comparison.
4. **Given** CLI acceptance tests, **When** they run, **Then** they verify each subcommand exits 0 offline, JSON schema keys, human output labels, `--output` file write, and `--sample-index` honored.
5. **Given** acceptance tests for configuration discipline, **When** CLI subcommands initialize runners, **Then** tests assert model identity and cache mode are read from environment configuration.

---

### User Story 5 - Validate CLI and Reports via Quickstart Guide (Priority: P3)

An evaluator onboarding to the harness needs a quickstart document that walks through reproducing green offline runs for all CLI subcommands and the feature acceptance suites from a clone, mirroring what continuous integration verifies.

**Why this priority**: Reproducibility requires a human-readable path, not only automated tests.

**Independent Test**: Follow `specs/005-cli-adjudication-report/quickstart.md` on a clean clone without an API key; confirm all subcommands replay from committed cache and both acceptance suites are green.

**Acceptance Scenarios**:

1. **Given** the feature quickstart guide, **When** an evaluator follows setup and offline CLI steps, **Then** they can run all five subcommands without live model credentials.
2. **Given** the quickstart test commands, **When** executed locally, **Then** outcomes match the continuous integration merge gate expectations for this feature.

---

### Edge Cases

- What happens when export provenance verification fails during a CLI-initiated sweep? The runner surfaces the provenance error and the CLI exits non-zero; no partial report is emitted.
- What happens when a standalone rate has zero denominator at the selected sample? That rate's value and Wilson interval are `null`; other rates with valid denominators still report normally.
- What happens when `--sample-index` is outside 0–4? The CLI rejects the argument with a clear validation error before invoking a runner.
- What happens when only some of the five sample indices have committed cache entries in offline mode? The runner fails at the first cache miss; the CLI propagates the error and exits non-zero.
- What happens when `CACHE_MODE=refresh` and credentials are present? Runners may fetch and persist new cache entries per the shared cache contract; default and CI behavior remain offline replay.
- What happens when `--output PATH` points to a non-writable or missing parent directory? The CLI fails with a clear error naming the path; it does not silently drop file output.
- What happens when cross-tier comparison is requested but one tier sweep has not been run? Callers must supply four completed sweep results; building the comparison table with incomplete inputs is out of CLI scope — the CLI runs one evaluation per invocation.
- What happens when JSON serialization encounters null rate values? Output remains valid JSON with explicit `null` for undefined rates and intervals, consistent with gate report JSON shape.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST provide an adjudication reporting module under `report/` with `adjudication_types.py` and `adjudication_tables.py` consuming `TierSweepResult` (T1/T2/T3) and `AutonomousSweepResult` from upstream runners.
- **FR-002**: `build_tier_adjudication_report(sweep, *, sample_index=0)` MUST produce `TierAdjudicationReportTables` per [contracts/adjudication-report.md](./contracts/adjudication-report.md), including tier/runner metadata, primary metrics, confusion matrix, five sample rollups, and variance summary.
- **FR-003**: The report layer MUST compute Wilson confidence intervals on over-erasure, over-retention, and mis-escalation rates using the shared `report/wilson.py` implementation; Wilson computation MUST NOT be added to `core/scoring`.
- **FR-004**: The report layer MUST consume rate numerators and denominators from runner scoring results only; it MUST NOT re-derive rate proportions or re-score prediction pairs.
- **FR-005**: When `denominator == 0`, `Rate.value`, Wilson bounds, and `RateWithCI.interval` MUST be `null` — matching the gate report zero-denominator rule.
- **FR-006**: Adjudication report types and serialized output MUST NOT include prohibited fields: `accuracy`, `micro_f1`, `blended_score`, `blended_accuracy`.
- **FR-007**: `build_cross_tier_comparison(t1, t2, t3, autonomous, *, sample_index=0)` MUST produce exactly four rows (t1, t2, t3, autonomous) with Wilson-augmented standalone rates for the selected sample.
- **FR-008**: The feature MUST provide a CLI package under `cli/` registered as console script `dpdp-eval` in `pyproject.toml`.
- **FR-009**: The CLI MUST expose subcommands: `t1`, `t2`, `t3`, `autonomous`, and `adversarial-gate`.
- **FR-010**: Adjudication subcommands MUST run the corresponding runner, build adjudication report tables, and emit human-readable stdout or `--json` structured output.
- **FR-011**: The adversarial-gate subcommand MUST run the gate runner and emit `GateReportTables` via existing `build_gate_report` and `format_gate_report` — not a duplicate gate formatter.
- **FR-012**: The CLI MUST support flags: `--json`, `--output PATH`, `--sample-index` (0–4, default 0), `--export-dir`, and `--cache-root`.
- **FR-013**: Default CLI execution MUST use offline cache replay suitable for CI; continuous integration MUST run all CLI acceptance paths without a model API key.
- **FR-014**: CLI runner initialization MUST respect `MODEL_ID` and `CACHE_MODE` from environment configuration via existing runner config loading — not hardcoded provider or model identity.
- **FR-015**: An adjudication report acceptance suite MUST exist at `tests/report/test_acceptance_adjudication_report.py`, written before implementation, covering Wilson parity, rate fidelity, zero-denominator nulls, confusion matrix, five rollups, prohibited-field absence, and cross-tier comparison.
- **FR-016**: A CLI acceptance suite MUST exist at `tests/cli/test_acceptance_cli.py`, written before implementation, covering offline subcommand success, JSON schema keys, human labels, `--output`, and `--sample-index`.
- **FR-017**: A feature quickstart guide (`specs/005-cli-adjudication-report/quickstart.md`) MUST document clone-and-run steps for all subcommands and acceptance suites.
- **FR-018**: Work MUST land on feature branch `005-cli-adjudication-report`; the agent MAY commit to the feature branch but MUST NOT merge to `main` (human merge gate).
- **FR-019**: Vocabulary in CLI-facing human output MUST use DPDP domain terms and reader-facing evaluation names (request-only, records-augmented, rule-augmented, autonomous retrieval, adversarial-gate evaluation); developer-facing identifiers use `t1`, `t2`, `t3`, `autonomous`, and `adversarial_gate` per runner and cache naming conventions.
- **FR-020**: The feature MUST NOT modify runner orchestration, frozen export content, or scoring math in `core/scoring`; it integrates existing runners and scoring only.

### Key Entities

- **TierAdjudicationReportTables**: Top-level adjudication report for one tier or autonomous evaluation, bundling metadata, primary Wilson-augmented metrics, confusion matrix, five sample rollups, and variance summary.
- **AdjudicationMetricsTable**: Wilson-augmented standalone over-erasure, over-retention, and mis-escalation rates for one sample.
- **SampleMetricsSummary**: One entry in the five-sample rollup list with sample index and Wilson-augmented standalone rates.
- **CrossTierComparisonTable**: Four-row side-by-side comparison of t1, t2, t3, and autonomous standalone rates at a selected sample index.
- **CrossTierMetricRow**: One tier's Wilson-augmented standalone rates within the cross-tier table.
- **RateWithCI**: Point estimate plus Wilson interval wrapper shared with gate reporting; interval is `null` when denominator is zero.
- **CLI subcommand**: One evaluation dispatch path (`t1`, `t2`, `t3`, `autonomous`, `adversarial-gate`) that runs the upstream runner and formats report output.
- **Primary sample index**: The sample (0–4) driving primary metrics and confusion matrix; default 0, overridable via `--sample-index`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone with no model API key, both adjudication-report and CLI acceptance suites complete with all tests green in offline cache mode.
- **SC-002**: Each of the five CLI subcommands exits 0 and produces complete report output when run against committed cache in offline mode.
- **SC-003**: For representative fixtures, Wilson confidence intervals on all three standalone adjudication rates match independently hand-calculated bounds in the report acceptance suite.
- **SC-004**: Rate numerators and denominators in report output match the upstream runner scoring results exactly — zero re-derivation drift in acceptance tests.
- **SC-005**: Cross-tier comparison tables contain exactly four rows with correct tier labels and sample-consistent metrics.
- **SC-006**: No adjudication report or CLI JSON output contains prohibited blended-accuracy fields.
- **SC-007**: Zero-denominator rates and intervals serialize as explicit nulls in both human and JSON output, verified by acceptance tests.
- **SC-008**: An evaluator following the feature quickstart reproduces green offline CLI runs for all subcommands in under 10 minutes on a standard developer machine (excluding optional refresh steps).
- **SC-009**: Re-running the same CLI subcommand twice in offline mode with the same committed cache yields identical report output (deterministic replay).
- **SC-010**: Continuous integration executes report and CLI acceptance tests without network access or secrets.

## Assumptions

- Features 001–004 are complete and merged: shared core (export, cache, scoring, model seam), tier runners with `TierSweepResult`, adversarial gate runner with gate report layer, and autonomous runner with `AutonomousSweepResult`.
- Wilson confidence intervals use the standard Wilson score interval at 95% confidence with the same parameters as the gate report (`report/wilson.py`); the spec requires intervals be present and hand-verifiable, not a specific third-party statistics package.
- The default model seam for CLI offline runs replays committed cache entries without live API calls; exact seam selection (`FakeModelSeam` or equivalent) is a plan-phase detail as long as offline CI behavior holds.
- Per-sample aggregate scoring (one adjudication result per sample index covering the entire export or tier sweep) remains the runner's responsibility; this feature wraps and formats those results only.
- Cross-tier comparison is a library/report function invoked by tests and future automation; the v1 CLI runs one evaluation per invocation and does not require a single subcommand that runs all four tiers sequentially.
- Human-readable CLI output labels follow the vocabulary discipline in constitution Principle V; exact formatting is defined in the plan/contracts phase.
- Gate report building and formatting from Feature 003 remain unchanged; this feature wires the gate subcommand to them.

## Dependencies

- Constitution: `.specify/memory/constitution.md` (Principles I–IV, VII, VIII).
- Canonical planning: `Planning/dpdp_eval_harness_planning.md` (§7 integration layer, §5 adjudication scoring, §8 feature breakdown, §9 guardrails).
- ADR-0001: frozen export as deterministic ground truth (`docs/adr/0001-frozen-export-ground-truth.md`).
- Feature 001 contracts (consumed, not re-specified): `specs/001-shared-core/contracts/scoring.md`, `specs/001-shared-core/contracts/cache.md`, `specs/001-shared-core/contracts/model-seam.md`.
- Feature 002 spec and contracts: `specs/002-context-tier-sweep/spec.md`, `specs/002-context-tier-sweep/contracts/sweep-result.md`.
- Feature 003 spec and gate report pattern: `specs/003-adversarial-gate/spec.md`, `specs/003-adversarial-gate/contracts/gate-report.md`.
- Feature 004 spec and contracts: `specs/004-autonomous-retrieval-eval/spec.md`, `specs/004-autonomous-retrieval-eval/contracts/autonomous-runner.md`.
- Feature 005 contract: [contracts/adjudication-report.md](./contracts/adjudication-report.md).

## Out of Scope

- Runner orchestration changes (tier, autonomous, or gate runners MUST NOT be modified).
- Edits to committed frozen export adjudication subjects or adversarial seed content.
- Scoring math changes or Wilson interval logic in `core/scoring`.
- Live model provider integration or requiring `MODEL_API_KEY` in CI.
- Per-subject variance tables beyond the five-sample sweep rollup already in runner output.
- Prose thesis writeup or README overhaul (may reference CLI commands but is not owned by this feature).
- Blended accuracy or other single headline scores that subsume standalone safety rates.
- A combined CLI subcommand that runs all tiers and autonomous in one invocation (callers run subcommands individually).

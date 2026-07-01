<!--
Sync Impact Report
==================
Version change: 1.0.0 → 1.0.1
Modified principles:
  - I. Deterministic Ground Truth — authority anchored to planning §1 and §6
  - V. Vocabulary and Wording Discipline — DPDP/GDPR clause cites planning §2
  - VIII. Dependency and Cost Discipline — model-count bounds removed (v1 scope)
Added sections: N/A
Removed sections: N/A
Templates:
  - .specify/templates/plan-template.md — ✅ aligned (no change this pass)
  - .specify/templates/tasks-template.md — ✅ aligned (no change this pass)
  - .specify/templates/spec-template.md — ✅ aligned
  - .specify/templates/commands/*.md — ⚠ not present in repo
  - README.md — ⚠ not present in repo
Deferred: N/A
-->

# DPDP Erasure Evaluation Harness Constitution

## Core Principles

### I. Deterministic Ground Truth (NON-NEGOTIABLE)

**Rule.** The harness MUST grade a model's per-location verdicts (erase,
retain-with-reason, escalate) against the deterministic ground truth exported from
[dpdp-erasure-agent](https://github.com/KrishnaDev-Palem/dpdp-erasure-agent) —
the agent's verdicts are the known-correct answer key. Per the frozen-export contract,
the harness MUST read the `expected` block as ground truth and MUST NOT edit,
second-guess, or re-derive it. The harness MUST NOT change the agent, re-litigate
the agent's regulatory interpretation, or take a live dependency on the running
agent or Postgres. The deterministic system is the reference frame; the model is the
subject under evaluation.

**Why (this project).** The harness is not a bake-off between adjudicators; it
measures a model-based adjudicator against rule-checked labels the agent already
produced. Recomputing or overriding those labels would make the harness a second
adjudication system and invalidate the thesis.

**Constrains.** Feature specs and plans for scoring, runners, loaders, and reporting
MUST treat the committed frozen export as the sole answer key. Plans MUST NOT
propose live agent calls, Postgres lookups, or harness-side rule engines that
regenerate labels. Specs MUST state how grading reads `expected` without
re-derivation.

### II. Acceptance-Spec Before Implementation (NON-NEGOTIABLE)

**Rule.** Each feature's contract MUST be written before it is built. No
implementation code lands before its acceptance suite exists and fails for the
right reason. A green acceptance suite is the feature's definition of done.

**Why (this project).** The harness produces evidentiary numbers about model
behavior against a frozen key. Shipping behavior without a failing-then-passing
acceptance suite would make scores unauditable and regressions invisible.

**Constrains.** Every feature spec MUST define acceptance scenarios before
implementation tasks appear in `tasks.md`. Plans MUST sequence test tasks ahead of
implementation tasks. Tasks that add behavior without a preceding failing test
MUST be rejected at review.

### III. Frozen-Interface / Frozen-Export Discipline

**Rule.** The committed frozen export and any accepted runner interface MUST NOT
be edited after commitment. New coverage MUST be additive only: new fixtures, new
cases, new runners — never edits to accepted ones.

**Why (this project).** Published tables and cross-run comparisons depend on a
stable answer key and stable runner contracts. In-place edits silently rewrite
history and break reproducibility claims.

**Constrains.** Specs and plans for new evaluations, fixtures, or runners MUST
extend via addition. Migration or correction of committed exports or accepted
interfaces MUST be treated as a constitution amendment, not a feature tweak.

### IV. Reproducibility and Offline Verification

**Rule.** Dependency management MUST use `uv` with a committed `uv.lock`. A clone
plus `uv sync` MUST reproduce the exact environment. Published numbers MUST
reproduce offline from the committed cache. Continuous integration MUST run the
full `pytest` suite (and `ruff` lint/format checks) on every pull request, fully
offline, with no model API key.

**Why (this project).** The deliverable is measured, reproducible evidence. Numbers
that require live API calls or undisclosed environment drift cannot be verified
by reviewers or CI.

**Constrains.** Plans MUST specify lockfile updates when dependencies change.
Specs for scoring or reporting MUST include an offline replay path from committed
cache. CI configuration MUST NOT require secrets for the merge gate.

### V. Vocabulary and Wording Discipline

**Rule.** Tracked artifacts MUST follow the locked vocabulary in planning §2:
DPDP terminology throughout, never GDPR terminology. Per planning §3,
developer-facing surfaces (commit scopes, runner names, suite names, internal
docs) MUST use T1 / T2 / T3 and runner labels; reader-facing surfaces (README,
writeup) MUST use the descriptive evaluation names (request-only,
records-augmented, rule-augmented) and the retired-scaffolding rule from §2
("pillar" and "condition" MUST NOT appear).

**Why (this project).** The harness inherits domain vocabulary from the agent and
must stay byte-compatible with the frozen export while remaining legible to
readers who are not looking at runner internals.

**Constrains.** Specs MUST label tier and runner naming explicitly and cite §2
for domain terms. Plans and user-facing copy MUST pass a terminology check before
merge. Internal identifiers (e.g., `subject_id`) MUST NOT be renamed when export
compatibility requires the existing field name.

### VI. Currency Before Communication

**Rule.** Any regulatory or model-availability fact MUST be web-verified before
it lands in a tracked artifact. Sectoral floors and model strings both move;
unverified claims MUST NOT be committed.

**Why (this project).** The writeup and specs cite live regulatory and model
context. Stale or assumed facts would undermine the honesty requirement of the
deliverable.

**Constrains.** Specs and plans that cite statutes, sectoral floors, model IDs, or
availability MUST record verification steps or sources. Implementation MUST NOT
embed unverified regulatory text as canonical.

### VII. Git Flow and Human Merge Gate

**Rule.** Work MUST happen on feature branches opened as pull requests. The agent
(Cursor) MAY commit to the feature branch but MUST NOT merge to `main`. A human
MUST review the diff and merge to `main` by hand. CI MUST be green before merge.

**Why (this project).** Landing on `main` is the protected operation that publishes
reproducible numbers and frozen contracts. Keeping merge human-gated preserves
accountability while allowing agent-assisted branch work.

**Constrains.** Plans MUST name the feature branch. Tasks MUST NOT include merge-to-
`main` steps for the agent. Specs MUST list CI gates as merge prerequisites.

### VIII. Dependency and Cost Discipline

**Rule.** Dependency additions MUST have explicit justification. The harness MUST
NOT use a database or pgvector. Total spend MUST stay in the tens of dollars;
plans MUST NOT introduce combinatorial blowup (unbounded tiers × models × samples
× cases).

**Why (this project).** The harness is a bounded evaluation instrument, not a
production platform. Uncontrolled dependencies or run matrices would violate scope
and budget guardrails without improving the core thesis.

**Constrains.** Plans MUST justify each new dependency in Complexity Tracking when
not covered by an existing principle exception. Specs MUST bound run cardinality
(samples, cases, and sweep dimensions) to avoid combinatorial blowup. Database or
vector-store requirements MUST be rejected unless amended via governance.

### IX. Tracked Artifacts, Not Ephemeral Chat

**Rule.** Specs, ADRs, briefs, and decision records MUST be committed documents.
Load-bearing choices MUST NOT live only in chat or uncommitted notes.

**Why (this project).** The build order and Spec Kit workflow assume durable,
reviewable artifacts that outlive any single session.

**Constrains.** Feature work MUST produce or update files under `specs/`, `docs/adr/`,
or other tracked paths defined in the plan. Plans MUST list which artifacts this
feature adds or changes.

### X. Stop and Surface Over Silent Choices

**Rule.** Where the constitution, planning document, or a feature spec is silent
or ambiguous on a value or behavior, the gap MUST be surfaced to a human. Agents
and implementers MUST NOT guess or fill gaps with undocumented defaults.

**Why (this project).** Silent choices become hidden assumptions in scores and
contracts. Surfacing gaps preserves the honest, auditable posture of the harness.

**Constrains.** Specs MUST mark `NEEDS CLARIFICATION` rather than inventing values.
Plans MUST halt at Constitution Check or design gates when prerequisites are
missing. Implementation tasks MUST NOT proceed past unresolved gaps.

## Repository Quality Gates

The following repository conventions from planning §3 are binding quality gates.
They are not separate principles because they operationalize Principles IV and VII.

- **Pre-commit hooks.** `ruff` lint and format plus basic file hygiene (trailing
  whitespace, end-of-file, YAML well-formedness) MUST run locally so the same
  checks that gate the PR catch issues before commit.
- **Secret hygiene.** The model API key MUST be read from an environment variable.
  `.env.example` MUST be committed with variable names and no values; `.env` MUST
  be git-ignored and secrets MUST NOT be committed.
- **Licensing and provenance.** The repository MUST carry an MIT `LICENSE`. The
  frozen export MUST carry a provenance header pinning the agent commit SHA.
- **README as on-ramp.** The README MUST be thesis-first, use reader-facing
  vocabulary, and document a clone-and-run path that reproduces published tables
  from the committed cache; status badges MUST reflect real CI state.

## Governance

This constitution supersedes ad hoc practices for the DPDP Erasure Evaluation
Harness. It is derived from `dpdp_eval_harness_planning.md` (canonical planning
document), with §3 (Principles and non-negotiables) and §9 (Cost and scope
guardrails) as the primary pointers and §1, §2, and §6 supplying authority where
those sections cross-reference or imply them.

**Amendment procedure.** Changes MUST update `.specify/memory/constitution.md`,
increment the version per semantic versioning below, set `Last Amended` to the
change date, and propagate impacts to dependent templates (`plan-template.md`,
`spec-template.md`, `tasks-template.md`) and any runtime guidance docs.

**Versioning policy.**

- **MAJOR:** Backward-incompatible removal or redefinition of a principle.
- **MINOR:** New principle or materially expanded guidance.
- **PATCH:** Clarifications, wording, or non-semantic refinements.

**Compliance review.** Every pull request MUST pass Constitution Check in the
feature plan. Reviewers MUST verify test-first ordering, frozen-export discipline,
offline CI, terminology, and cost bounds before merge. Load-bearing architectural
choices MUST be recorded as ADRs under `docs/adr/` with context, decision,
consequences, and rejected alternatives.

**Authority.** Where this constitution conflicts with conversational defaults or
agent habits, this document wins. Feature-specific behavior belongs in per-feature
specs, not here.

**Version**: 1.0.1 | **Ratified**: 2026-06-30 | **Last Amended**: 2026-06-30

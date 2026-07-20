# Research: 001-shared-core

**Date**: 2026-07-01  
**Feature**: Shared core spine (export, model seam, cache, scoring, context)

## R1 — Tech stack alignment with agent

**Decision**: Python 3.11, `uv` for dependency management, `pytest` for acceptance tests, `ruff` for lint/format.

**Rationale**: Planning section 7 and constitution Principle IV require parity with the agent for reproducibility. The harness is a library-style Python project reading YAML/JSON from disk — no web framework or database.

**Alternatives considered**:
- Node/TypeScript — rejected; agent ground truth is Python-native and team conventions mirror the agent.
- Poetry/pip-tools — rejected; constitution mandates `uv` + committed `uv.lock`.

## R2 — Frozen export format and provenance

**Decision**: Single committed directory `export/` at repo root containing YAML files: `manifest.yaml` (provenance header + pinned SHA permalink), `adjudication/` (subjects/locations), `rules/` (retention floors + governance map), `adversarial_seeds/` (three frozen cases). Loader validates manifest before exposing data.

**Rationale**: Planning section 6 defines byte-compatible shapes inherited from the agent. A manifest-first layout keeps provenance check isolated and auditable. File-based export avoids a database (constitution VIII).

**Alternatives considered**:
- Single monolithic YAML — rejected; harder to diff and extend adversarial slice in Feature 003.
- Live agent API at load time — rejected; violates constitution Principle I.

## R3 — Model seam shape

**Decision**: Protocol-based injection with two operation families on one seam:
1. **Adjudication** — accept a context bundle + case identity; return structured per-location verdicts (`erase` | `retain` | `escalate`) plus optional rationale text.
2. **Classification** — accept note text only; return `clean` | `adversarial` plus optional detail string (mirrors agent `Classifier`).

Configuration via dataclass/env: model role name, provider settings, temperature defaults. Default implementation raises `NotConfiguredError`; tests use `FakeModel` double.

**Rationale**: Planning section 6–section 7 require the adversarial gate to mirror the agent classifier while adjudication runners need per-location verdicts. One injectable seam avoids duplicate wiring; Feature 002/003 runners share it.

**Alternatives considered**:
- Separate seams per evaluation — rejected; duplicates cache keying and configuration.
- Hardcoded OpenAI client — rejected; breaks offline CI and constitution IV.

## R4 — Cache layout and keying

**Decision**: Committed tree under `core/cache/data/` (or top-level `cache/` per plan section 7 — use `cache/` at repo root for visibility in quickstart). Key components: `model_id`, `runner_id` (e.g. `t1`, `t2`, `t3`, `adversarial_gate`), `case_id`, `prompt_hash` (SHA-256 of canonical JSON context), `sample_index` (0–4 for N=5). Each entry is a JSON file with raw response payload + metadata (timestamp, prompt_hash echo).

Offline mode: `CACHE_MODE=offline` (default in CI). Refresh mode: `CACHE_MODE=refresh` requires `MODEL_API_KEY` env var.

**Rationale**: Planning section 7 reproducibility mechanics and spec FR-014–FR-016. File-based cache keeps CI secret-free and git-diffable for published numbers.

**Alternatives considered**:
- SQLite cache — rejected; unnecessary dependency, harder to review in PRs.
- No committed cache in 001 — rejected; cache module and keying must exist in core even if minimal seed entries ship with Feature 002 runs.

## R5 — Scoring primitives

**Decision**:
- **Adjudication**: build 3×3 confusion matrix (predicted × actual lanes). Derive `over_erasure_rate`, `over_retention_rate`, `mis_escalation_rate` as standalone fractions with explicit denominators. Never compute blended accuracy.
- **Adversarial**: `detection_rate = flagged_attacks / total_attacks`, `false_alarm_rate = flagged_benign / total_benign`. Per-family breakdown groups by `family` field on slice cases.

Empty-input behavior: rates return `None` or structured `{rate: null, denominator: 0}` — never silent NaN.

**Rationale**: Planning section 5 scoring contract and constitution ground-truth discipline.

**Alternatives considered**:
- Single F1 or accuracy headline — rejected; planning explicitly forbids blended adjudication score.
- Wilson CI in core — deferred to Feature 003 reporting; core supplies counts and rates sufficient for CI calculation.

## R6 — Context tier assembly

**Decision**: Three pure functions in `core/context/`: `build_t1`, `build_t2`, `build_t3`. Input: erasure request dict (`subject_id`, `type`, `basis`, `as_of`) + subject's locations from export. T3 adds `rules.retention_floors` and `rules.governance_map` from export. Output: canonical JSON-serializable dict hashed for cache keys. `expected` blocks stripped at assembly boundary.

**Rationale**: Planning section 4.1 tier definitions and spec User Story 6. Pure functions ease acceptance testing without model calls.

**Alternatives considered**:
- Template strings in runners — rejected; duplicates tier logic across three runners in Feature 002.

## R7 — Regulatory text in export

**Decision**: Retention floor table from planning section 6 is embedded in the committed export `rules/` files. Verification note: Income-tax Rules 2026 r.46(9) cited in planning is the current pin as of mid-2026; re-verify before commit via official sources when the export is generated from the agent.

**Rationale**: Constitution Principle VI (currency before communication). The harness does not re-litigate floors; it reads what the export carries.

**Alternatives considered**:
- Harness-side statute fetch — rejected; violates frozen-export discipline.

## R8 — Test layout and test-first sequencing

**Decision**: Package layout `core/` + `tests/core/` mirroring modules. Acceptance tests named `test_acceptance_*.py` per submodule. Export fixture under `export/` with minimal representative subset if full agent export is large — must still pass provenance check against pinned SHA when full export lands.

**Rationale**: Constitution II — tests written first, fail for right reason, then implementation.

**Alternatives considered**:
- `src/` layout — rejected; planning section 7 uses `core/` at repo root explicitly.

## R9 — ADR-0001

**Decision**: Author `docs/adr/0001-frozen-export-ground-truth.md` during this feature documenting eval methodology and frozen-export coupling (planning section 10 item 1).

**Rationale**: Constitution governance requires load-bearing choices in ADRs.

**Alternatives considered**:
- Spec-only documentation — rejected; ADR index expected in planning section 3.

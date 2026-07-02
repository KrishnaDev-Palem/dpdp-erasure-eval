# Implementation Plan: Shared Core

**Branch**: `001-shared-core` | **Date**: 2026-07-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-shared-core/spec.md`

## Summary

Build the harness spine: load and verify the committed frozen export (provenance-pinned agent answer key), injectable model seam, offline-capable response cache, adjudication and adversarial scoring primitives, and T1/T2/T3 context assembly helpers. Delivered as a `core/` Python package with a test-first acceptance suite that runs fully offline. No runners, CLI, or report tables in this feature.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: `pyyaml` (export parsing), `pydantic` v2 (validated dataclasses) — minimal set; justify any addition in PR  
**Storage**: Filesystem only — `export/` (frozen answer key), `cache/` (committed responses)  
**Testing**: `pytest`, acceptance tests under `tests/core/`  
**Target Platform**: Linux/macOS/Windows dev; GitHub Actions CI  
**Project Type**: Library-style Python package + committed data artifacts  
**Performance Goals**: Full core acceptance suite completes in &lt;30s offline  
**Constraints**: No database, no live agent, no API key in CI, frozen export immutable after commit (planning §6 frozen-export contract, §9 guardrails)  
**Scale/Scope**: ~30–50 labeled locations in export; cache keyed for N=5 samples per case

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | Evidence |
|-----------|--------|----------|
| **I. Deterministic Ground Truth** | **PASS** | Loader reads `expected` only ([contracts/frozen-export.md](./contracts/frozen-export.md)); no live agent or Postgres; no harness-side re-derivation |
| **II. Acceptance-Spec Before Implementation** | **PASS** | [tasks.md](./tasks.md) sequences failing `test_acceptance_*.py` tasks before each implementation phase; FR-019 |
| **III. Frozen-Interface / Frozen-Export Discipline** | **PASS** | Committed `export/` immutable after acceptance; provenance gate; additive-only extension policy in spec |
| **IV. Reproducibility and Offline Verification** | **PASS** | `uv` + `uv.lock`; committed `cache/` offline replay ([contracts/cache.md](./contracts/cache.md)); CI without API key |
| **V. Vocabulary and Wording Discipline** | **PASS** | DPDP terms; T1/T2/T3 internal labels ([contracts/context-tiers.md](./contracts/context-tiers.md)); `subject_id` retained |
| **VI. Currency Before Communication** | **PASS** | Statute text embedded in committed export at generation time; research R7 records re-verify step before export commit |
| **VII. Git Flow and Human Merge Gate** | **PASS** | Branch `001-shared-core`; PR + human merge; agent does not merge to `main` |
| **VIII. Dependency and Cost Discipline** | **PASS** | No database/pgvector; bounded deps (`pyyaml`, `pydantic` only); no combinatorial blowup; see §9 guardrails below |
| **IX. Tracked Artifacts, Not Ephemeral Chat** | **PASS** | spec/plan/research/data-model/contracts/quickstart/tasks committed; ADR-0001 scheduled in tasks T008 |
| **X. Stop and Surface Over Silent Choices** | **PASS** | Runners, CLI, Wilson CIs, autonomous tools explicitly deferred; no unresolved NEEDS CLARIFICATION |

*Post-design re-check (2026-07-01): **PASS** — no violations requiring Complexity Tracking.*

## Scope Guardrails (planning §9)

- **No Postgres** — filesystem export + cache only; SQLite rejected in research R4.
- **No live agent dependency** — export loaded from disk; provenance checks pinned SHA; CI runs fully offline.
- **Bounded dependencies** — Python 3.11, `uv`, `pytest`, `ruff`, `pyyaml`, `pydantic` v2; any addition requires PR justification.
- **Bounded cardinality** — N=5 samples per case; ~30–50 labeled locations; three adversarial seeds in 001 (slice extension deferred to Feature 003).
- **No combinatorial blowup** — no unbounded tiers × models × samples × cases matrix in this feature.

## Test-First Sequencing

Constitution Principle II requires acceptance tests before implementation. [tasks.md](./tasks.md) enforces this per user story (foundational fixture scaffold T014–T015 precedes US1 tests):

| Phase | Tests first (MUST FAIL) | Then implement |
|-------|-------------------------|----------------|
| US1 Export | T016, T017 | T018–T021 |
| US4 Model seam | T023 | T024–T026 |
| US5 Cache | T028 | T029–T033 |
| US2 Adjudication scoring | T035 | T036–T037 |
| US3 Adversarial rates (minimal) | T039 | T040–T041 |
| US6 Context tiers | T043 | T044–T046 |

**Execution order** (binding, per tasks.md): Bootstrap → Foundational → US1 → US4 → US5 → US2 → US3 → US6 → Polish.

**Definition of done**: each phase's acceptance tests fail for the right reason before implementation lands, then pass when the phase completes. Full suite green offline per SC-001.

## Project Structure

### Documentation (this feature)

```text
specs/001-shared-core/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── frozen-export.md
│   ├── model-seam.md
│   ├── cache.md
│   ├── scoring.md
│   └── context-tiers.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
core/
├── __init__.py
├── export/
│   ├── __init__.py
│   ├── loader.py          # load manifest, subjects, rules, seeds
│   └── provenance.py      # SHA pin verification
├── model/
│   ├── __init__.py
│   ├── seam.py            # Protocol + errors
│   └── fake.py            # FakeModelSeam for tests
├── cache/
│   ├── __init__.py
│   ├── store.py           # read/write/list
│   └── canonicalize.py    # prompt hash
├── scoring/
│   ├── __init__.py
│   ├── adjudication.py    # confusion matrix + rates
│   └── adversarial.py     # detection / false-alarm
└── context/
    ├── __init__.py
    └── tiers.py           # build_t1/t2/t3

export/                    # committed frozen export (fixture)
├── PINNED_AGENT_SHA
├── manifest.yaml
├── adjudication/
├── rules/
└── adversarial_seeds/

cache/                     # committed cache entries (minimal seed for 001 tests)

tests/
└── core/
    ├── test_acceptance_export.py
    ├── test_acceptance_provenance.py
    ├── test_acceptance_scoring_adjudication.py
    ├── test_acceptance_scoring_adversarial.py
    ├── test_acceptance_model_seam.py
    ├── test_acceptance_cache.py
    └── test_acceptance_context.py

docs/adr/
├── README.md
└── 0001-frozen-export-ground-truth.md

pyproject.toml
uv.lock
.env.example
```

**Structure Decision**: Single-package layout per planning §7 with `core/` at repo root (not `src/`). Tests mirror modules under `tests/core/`. Data artifacts `export/` and `cache/` sit at root for clone-and-inspect reproducibility.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0: Research

Complete — see [research.md](./research.md). All technical context items resolved; no open NEEDS CLARIFICATION.

## Phase 1: Design

Complete — see:

- [data-model.md](./data-model.md)
- [contracts/](./contracts/)
- [quickstart.md](./quickstart.md)

## Phase 2: Tasks

Complete — see [tasks.md](./tasks.md).

## Implementation Notes (for tasks phase)

1. **Bootstrap first**: `pyproject.toml`, `uv sync`, `ruff`, minimal `pytest` harness — enables red tests.
2. **Export fixture**: Generate or copy from agent at pinned SHA; commit with manifest + `PINNED_AGENT_SHA`.
3. **Test-first per user story**: follow tasks.md execution order (US1 export → US4 seam → US5 cache → US2/US3 scoring → US6 context); seam uses `ContextBundle` from `core/types.py` until tier builders land in US6.
4. **ADR-0001** (load-bearing): Author `docs/adr/0001-frozen-export-ground-truth.md` early in implementation — documents eval methodology and frozen-export ground-truth coupling per planning §10; indexed in `docs/adr/README.md`. This is the sole ADR required for 001; no other load-bearing forks need ADR coverage in this feature.
5. **Out of scope reminder**: No `runners/`, `cli`, `report/`, or `core/tools/` in this feature.

# Implementation Plan: Adversarial Gate Evaluation

**Branch**: `003-adversarial-gate` | **Date**: 2026-07-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-adversarial-gate/spec.md`

## Summary

Deliver an adversarial-gate runner that sweeps an extended, eval-authored slice (~80–100 labeled attack/benign cases) using `ModelSeam.classify_note` with note text only, scores outcomes via `core.scoring.score_adversarial`, and emits Wilson confidence intervals plus per-attack-family detection tables from a new `report/` module. Default execution replays committed cache entries (`runner_id` `adversarial_gate`, N=5 samples) with no live model in CI. Acceptance tests under `tests/gate/` are written before implementation and must pass fully offline.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Inherited from Feature 001 — `pyyaml`, `pydantic` v2; Wilson intervals via stdlib `math` only (no new runtime deps)  
**Storage**: Filesystem — `export/` (frozen seeds, read-only cross-check), `fixtures/adversarial_slice/` (extended corpus), `cache/` (committed classifier responses keyed by `adversarial_gate` + sample)  
**Testing**: `pytest`; acceptance tests under `tests/gate/` mirroring `runners/adversarial_gate/`  
**Target Platform**: Linux/macOS/Windows dev; GitHub Actions CI (offline, no API key)  
**Project Type**: Library-style Python package + gate runner module + reporting module + committed cache expansion  
**Performance Goals**: Full gate acceptance suite completes in &lt;60s offline on a standard dev machine  
**Constraints**: No Postgres, no live agent in CI, frozen export seeds immutable, `CACHE_MODE=offline` default, N=5 samples only (planning §9), label isolation on seam inputs  
**Scale/Scope**: ~80–100 slice cases × 5 sample indices; five attack families at ~8–10 cases each; one gate runner namespace

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | Evidence |
|-----------|--------|----------|
| **I. Deterministic Ground Truth** | **PASS** | Gate grades classifier outcomes against slice fixture labels (`label`, `family`) read from metadata — not inferred from note text. Export seeds cross-checked but not edited ([001/contracts/frozen-export.md](../001-shared-core/contracts/frozen-export.md)). No live agent or Postgres |
| **II. Acceptance-Spec Before Implementation** | **PASS** | Gate contracts in [contracts/](./contracts/); acceptance suite planned under `tests/gate/` before implementation tasks in Phase 2 (`tasks.md`) |
| **III. Frozen-Interface / Frozen-Export Discipline** | **PASS** | No edits to committed `export/` or Feature 001/002 contracts; additive slice fixtures, cache entries, `runners/adversarial_gate/`, and `report/` only |
| **IV. Reproducibility and Offline Verification** | **PASS** | `uv` + `uv.lock`; default `CACHE_MODE=offline`; committed cache replay per [001/contracts/cache.md](../001-shared-core/contracts/cache.md); CI without `MODEL_API_KEY` |
| **V. Vocabulary and Wording Discipline** | **PASS** | Reader-facing *adversarial-gate evaluation*; developer-facing `adversarial_gate` runner_id; DPDP domain terms; no retired scaffolding terms |
| **VI. Currency Before Communication** | **PASS** | No new statute claims; slice cases are eval-authored adversarial prose, not regulatory citations |
| **VII. Git Flow and Human Merge Gate** | **PASS** | Branch `003-adversarial-gate`; PR + human merge; agent does not merge to `main` |
| **VIII. Dependency and Cost Discipline** | **PASS** | No database/pgvector; Wilson CIs implemented in stdlib (research R3); bounded matrix: ~100 cases × N=5 samples × one runner |
| **IX. Tracked Artifacts, Not Ephemeral Chat** | **PASS** | spec/plan/research/data-model/contracts/quickstart committed under `specs/003-adversarial-gate/` |
| **X. Stop and Surface Over Silent Choices** | **PASS** | Research resolves layout, Wilson approach, and slice strategy; no unresolved NEEDS CLARIFICATION |

*Post-design re-check (2026-07-03): **PASS** — no violations requiring Complexity Tracking.*

## Scope Guardrails (planning §9)

- **No Postgres** — filesystem export, fixtures, and cache only.
- **No live agent in CI** — default `CACHE_MODE=offline`; refresh path documented in [quickstart.md](./quickstart.md) but excluded from merge gate.
- **Bounded dependencies** — reuse Feature 001 stack (`uv`, `pytest`, `ruff`, `pyyaml`, `pydantic` v2); Wilson intervals via stdlib `math`; any addition beyond that requires PR justification in Complexity Tracking.
- **Bounded cardinality** — N=5 samples per case (`sample_index` 0–4); one gate runner; ~80–100 slice cases; no combinatorial model × family × case blowup.
- **No combinatorial blowup** — cache namespace partitioned by `runner_id` `adversarial_gate`; per-family tables are reporting cuts over one sweep, not separate runs.

## Test-First Sequencing

Constitution Principle II requires acceptance tests before implementation. Phase 2 `tasks.md` (via `/speckit-tasks`) MUST sequence failing gate acceptance tests ahead of implementation:

| Phase | Tests first (MUST FAIL) | Then implement |
|-------|-------------------------|----------------|
| Slice loader | `test_acceptance_adversarial_slice.py` | `runners/adversarial_gate/slice_loader.py` |
| Gate runner spine | `test_acceptance_gate_runner.py` | `runners/adversarial_gate/runner.py` |
| Label isolation | `test_acceptance_label_isolation.py` | assert no `label`/`family` in seam or cache payload |
| N=5 + variance | `test_acceptance_gate_sample_variance.py` | sample loop + adversarial variance summary |
| Config discipline | `test_acceptance_gate_config.py` | env-driven `MODEL_ID`, `CACHE_MODE` |
| Wilson + tables | `test_acceptance_gate_report.py` | `report/wilson.py`, `report/adversarial_tables.py` |
| Cache offline | `test_acceptance_gate_cache_offline.py` | committed cache replay; miss errors |

**Definition of done**: acceptance tests fail for the right reason before gate code lands, then pass when the feature completes. Full `tests/gate/` suite green offline per SC-001.

## Project Structure

### Documentation (this feature)

```text
specs/003-adversarial-gate/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── gate-runner.md
│   ├── adversarial-slice.md
│   └── gate-report.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
runners/
├── spine.py             # Feature 002 tier spine (unchanged)
├── t1.py, t2.py, t3.py  # Feature 002 tier runners (unchanged)
└── adversarial_gate/
    ├── __init__.py
    ├── runner.py        # gate sweep orchestration
    ├── slice_loader.py  # load extended slice + seed cross-check
    ├── cache.py         # gate cache key + classify_note refresh path
    ├── variance.py      # detection/false-alarm cross-sample summary
    └── types.py         # GateSweepConfig, GateSweepResult, etc.

fixtures/
└── adversarial_slice/
    └── cases.yaml       # ~80–100 labeled cases (additive; includes frozen seeds)

report/
├── __init__.py
├── wilson.py            # Wilson score interval (stdlib math)
├── adversarial_tables.py # primary + per-family table emission
└── types.py             # WilsonInterval, RateWithCI, GateReportTables

export/                  # unchanged committed frozen export (Feature 001)
cache/                   # expanded: all slice cases × adversarial_gate × sample 0..4

tests/
├── core/                # Feature 001 acceptance (unchanged)
├── runners/             # Feature 002 acceptance (unchanged)
└── gate/
    ├── conftest.py
    ├── test_acceptance_adversarial_slice.py
    ├── test_acceptance_gate_runner.py
    ├── test_acceptance_label_isolation.py
    ├── test_acceptance_gate_sample_variance.py
    ├── test_acceptance_gate_config.py
    ├── test_acceptance_gate_report.py
    └── test_acceptance_gate_cache_offline.py

core/                    # Feature 001 shared core (consumed, not modified except blocking bugfixes)
```

**Structure Decision**: Per planning §7 and spec FR-001, the gate runner lives in `runners/adversarial_gate/` (subdirectory, distinct from flat tier entry modules). Tier runners remain at `runners/t1.py` etc. Reporting deferred from Features 001/002 lands in top-level `report/`. Extended slice fixtures are eval-authored under `fixtures/adversarial_slice/` — separate from immutable `export/adversarial_seeds/`. Tests mirror under `tests/gate/`.

## Gate Runner Spine (design summary)

The gate runner follows Feature 002 orchestration patterns (detailed in [contracts/gate-runner.md](./contracts/gate-runner.md)):

1. **Load slice** — `slice_loader.load_extended_slice()`; optionally cross-check three frozen seed cases against `core.export.load_export().seeds` (byte identity); abort on mismatch.
2. **Initialize config** — `MODEL_ID`, `CACHE_MODE` from environment via `core.model.load_model_config()`; inject `ModelSeam` + `CacheStore`.
3. **For each `sample_index` in 0..4** (outer loop):
   - Collect `(ClassifierResult, AdversarialSeedCase)` pairs across all slice cases.
   - **For each case** in stable fixture order:
     - Form `CacheKey` with `runner_id=adversarial_gate`, `case_id`, `sample_index`, `prompt_hash({"text": case.text})`.
     - Resolve classification: gate cache helper → offline replay or refresh via `seam.classify_note(text=case.text, case_id=case.case_id)`.
     - Validate outcome ∈ {`clean`, `adversarial`}; reject otherwise.
     - Append pair `(ClassifierResult, case)` — label from fixture metadata only.
   - **Score sample** — `core.scoring.score_adversarial(all_pairs)` → one `AdversarialScoringResult`.
4. **Variance summary** — compare detection and false-alarm rates across five per-sample results.
5. **Report (optional at runner boundary)** — `report.adversarial_tables.build_gate_report(sample_result)` for Wilson CIs and per-family tables.
6. **Return** — `GateSweepResult` per [contracts/gate-report.md](./contracts/gate-report.md).

Gate-specific code MUST NOT reimplement adversarial rate math or Wilson formulas outside their designated modules.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0: Research

Complete — see [research.md](./research.md). All technical context items resolved; gate runner layout, Wilson CI approach, and slice fixture strategy justified.

## Phase 1: Design

Complete — see:

- [data-model.md](./data-model.md)
- [contracts/](./contracts/)
- [quickstart.md](./quickstart.md)

## Phase 2: Tasks

Not created by `/speckit-plan`. Run `/speckit-tasks` to generate [tasks.md](./tasks.md).

## Implementation Notes (for tasks phase)

1. **Acceptance tests first**: scaffold `tests/gate/` with `FakeModelSeam` and minimal committed cache seeds; expand cache to full slice × five samples during implementation.
2. **Slice before runner**: validate fixture shape, frozen seed inclusion, and family coverage before wiring the sweep loop.
3. **Cache expansion**: committed cache MUST cover every slice case × `adversarial_gate` × `sample_index` 0–4 for offline CI; additive entries only.
4. **Prompt identity**: cache canonical payload is `{"text": "<note>"}` only — reuse `core.cache.prompt_hash` on a plain dict, not a `ContextBundle`.
5. **Do not modify** `specs/001-shared-core/`, `specs/002-context-tier-sweep/`, or `core/` except blocking bugfixes (e.g., if `CacheStore.get_or_refresh` cannot serve classify_note without a small additive helper in gate module).
6. **Out of scope reminder**: no CLI entrypoints, tier runner changes, autonomous runner (Feature 004), Postgres, or blended accuracy scores.

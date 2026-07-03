# Implementation Plan: Context-Tier Adjudication Sweep

**Branch**: `002-context-tier-sweep` | **Date**: 2026-07-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-context-tier-sweep/spec.md`

## Summary

Deliver three tier adjudication runners (T1 request-only, T2 records-augmented, T3 rule-augmented) that sweep every labeled subject in the committed frozen export, replay model verdicts from the committed cache by default (N=5 samples per case), pair predictions with ground truth from `expected` blocks only, and aggregate per-sample adjudication metrics via `core.scoring.score_adjudication`. All runners share one orchestration spine under `runners/`; tier differences are limited to `runner_id` and which `core.context` builder is invoked. Acceptance tests under `tests/runners/` are written before implementation and must pass fully offline in CI.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Inherited from Feature 001 — `pyyaml`, `pydantic` v2; no new runtime deps expected  
**Storage**: Filesystem — `export/` (frozen answer key), `cache/` (committed model responses keyed by tier + sample)  
**Testing**: `pytest`; acceptance tests under `tests/runners/` mirroring `runners/`  
**Target Platform**: Linux/macOS/Windows dev; GitHub Actions CI (offline, no API key)  
**Project Type**: Library-style Python package + tier runner modules + committed cache expansion  
**Performance Goals**: Full runners acceptance suite completes in &lt;60s offline on a standard dev machine  
**Constraints**: No Postgres, no live agent in CI, frozen export immutable, `CACHE_MODE=offline` default, N=5 samples only (planning §9)  
**Scale/Scope**: All labeled export subjects × 3 tiers × 5 sample indices; ~30–50 labeled locations total across export

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | Evidence |
|-----------|--------|----------|
| **I. Deterministic Ground Truth** | **PASS** | Runners load export via `core.export.load_export`; scoring pairs use `expected` only ([001/contracts/frozen-export.md](../001-shared-core/contracts/frozen-export.md), [001/contracts/scoring.md](../001-shared-core/contracts/scoring.md)); no live agent or Postgres |
| **II. Acceptance-Spec Before Implementation** | **PASS** | Runners contracts in [contracts/](./contracts/); acceptance suite planned under `tests/runners/` before implementation tasks in Phase 2 (`tasks.md`) |
| **III. Frozen-Interface / Frozen-Export Discipline** | **PASS** | No edits to committed `export/` or Feature 001 core contracts; additive cache entries and new `runners/` modules only |
| **IV. Reproducibility and Offline Verification** | **PASS** | `uv` + `uv.lock`; default `CACHE_MODE=offline`; committed cache replay per [001/contracts/cache.md](../001-shared-core/contracts/cache.md); CI without `MODEL_API_KEY` |
| **V. Vocabulary and Wording Discipline** | **PASS** | Developer-facing T1/T2/T3 and `runner_id` values `t1`/`t2`/`t3`; DPDP domain terms; `subject_id` retained ([001/contracts/context-tiers.md](../001-shared-core/contracts/context-tiers.md)) |
| **VI. Currency Before Communication** | **PASS** | Regulatory text consumed from committed export rules corpus; no new statute claims in runner artifacts |
| **VII. Git Flow and Human Merge Gate** | **PASS** | Branch `002-context-tier-sweep`; PR + human merge; agent does not merge to `main` |
| **VIII. Dependency and Cost Discipline** | **PASS** | No database/pgvector; no new deps without justification; bounded matrix: 3 tiers × N=5 samples × export subjects only |
| **IX. Tracked Artifacts, Not Ephemeral Chat** | **PASS** | spec/plan/research/data-model/contracts/quickstart committed under `specs/002-context-tier-sweep/` |
| **X. Stop and Surface Over Silent Choices** | **PASS** | Research resolves layout and orchestration; no unresolved NEEDS CLARIFICATION |

*Post-design re-check (2026-07-02): **PASS** — no violations requiring Complexity Tracking.*

## Scope Guardrails (planning §9)

- **No Postgres** — filesystem export + cache only; runners read/write cache JSON under `cache/`.
- **No live agent in CI** — default `CACHE_MODE=offline`; refresh path documented in [quickstart.md](./quickstart.md) but excluded from merge gate.
- **Bounded dependencies** — reuse Feature 001 stack (`uv`, `pytest`, `ruff`, `pyyaml`, `pydantic` v2); any addition requires PR justification in Complexity Tracking.
- **Bounded cardinality** — N=5 samples per case (`sample_index` 0–4); three tier runners only; no combinatorial model × tier × case blowup in this feature.
- **No combinatorial blowup** — each tier sweep is independent; cache namespace partitioned by `runner_id`.

## Test-First Sequencing

Constitution Principle II requires acceptance tests before implementation. Phase 2 `tasks.md` (via `/speckit-tasks`) MUST sequence failing runner acceptance tests ahead of runner implementation:

| Phase | Tests first (MUST FAIL) | Then implement |
|-------|-------------------------|----------------|
| Spine | `test_acceptance_runner_spine.py` | `runners/spine.py`, pairing/validation helpers |
| T1 runner | `test_acceptance_t1_runner.py` | `runners/t1.py` (thin wrapper) |
| T2/T3 runners | `test_acceptance_t2_runner.py`, `test_acceptance_t3_runner.py` | `runners/t2.py`, `runners/t3.py` |
| N=5 + variance | `test_acceptance_sample_variance.py` | sample loop + variance summary in spine |
| Ground-truth isolation | `test_acceptance_context_isolation.py` | assert no `expected` in model-facing paths |
| Config discipline | `test_acceptance_runner_config.py` | env-driven `MODEL_ID`, `CACHE_MODE` |

**Definition of done**: acceptance tests fail for the right reason before runner code lands, then pass when the feature completes. Full `tests/runners/` suite green offline per SC-001.

## Project Structure

### Documentation (this feature)

```text
specs/002-context-tier-sweep/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── runner-spine.md
│   ├── tier-runner.md
│   └── sweep-result.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
runners/
├── __init__.py
├── spine.py             # shared orchestration: export load → subject sweep → cache → score
├── pairing.py           # location_id alignment, verdict validation (optional split from spine)
├── variance.py          # cross-sample rate comparison
├── t1.py                # T1 runner entry (runner_id=t1, build_t1)
├── t2.py                # T2 runner entry (runner_id=t2, build_t2)
└── t3.py                # T3 runner entry (runner_id=t3, build_t3)

export/                  # unchanged committed frozen export (Feature 001)
cache/                   # expanded committed entries: all subjects × t1|t2|t3 × sample 0..4

tests/
├── core/                # Feature 001 acceptance (unchanged)
└── runners/
    ├── conftest.py
    ├── test_acceptance_runner_spine.py
    ├── test_acceptance_t1_runner.py
    ├── test_acceptance_t2_runner.py
    ├── test_acceptance_t3_runner.py
    ├── test_acceptance_sample_variance.py
    ├── test_acceptance_context_isolation.py
    └── test_acceptance_runner_config.py

core/                    # Feature 001 shared core (consumed, not modified in this feature)
```

**Structure Decision**: Per planning §7, `runners/` lives at repository root (not under `core/` or `src/`). Tests mirror under `tests/runners/`. Tier runners are thin modules delegating to `runners/spine.py`; tier assembly stays in `core/context/tiers.py` (Feature 001). Cache and export artifacts remain at repo root for clone-and-inspect reproducibility.

## Shared Runner Spine (design summary)

All tier runners follow the same orchestration flow (detailed in [contracts/runner-spine.md](./contracts/runner-spine.md)):

1. **Load export** — `core.export.load_export()`; call `verify_provenance()`; abort sweep on failure.
2. **Initialize config** — `MODEL_ID`, `CACHE_MODE` from environment via `core.model.load_model_config()`; inject `ModelSeam` + `CacheStore`.
3. **For each `sample_index` in 0..4** (outer loop):
   - Collect prediction–ground-truth pairs across all subjects.
   - **For each subject** in export order:
     - Build tier context via `build_t1` / `build_t2` / `build_t3` (T3 receives `export.rules`).
     - Form `CacheKey` via `core.cache.make_cache_key` with tier `runner_id` and `case_id=subject_id`.
     - Resolve verdicts: `CacheStore.get_or_refresh` (offline replay or refresh-on-miss).
     - Parse `ModelVerdict` list from cache entry; validate coverage and verdict enum.
     - Pair each verdict with `location.expected` by `location_id`.
   - **Score sample** — `core.scoring.score_adjudication(all_pairs)` → one `AdjudicationScoringResult`.
4. **Variance summary** — compare standalone rates across the five per-sample results.
5. **Return** — `TierSweepResult` per [contracts/sweep-result.md](./contracts/sweep-result.md).

Tier-specific code MUST NOT reimplement context assembly, cache keying, or scoring formulas.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0: Research

Complete — see [research.md](./research.md). All technical context items resolved; runner layout vs tier-logic duplication justified.

## Phase 1: Design

Complete — see:

- [data-model.md](./data-model.md)
- [contracts/](./contracts/)
- [quickstart.md](./quickstart.md)

## Phase 2: Tasks

Not created by `/speckit-plan`. Run `/speckit-tasks` to generate [tasks.md](./tasks.md).

## Implementation Notes (for tasks phase)

1. **Acceptance tests first**: scaffold `tests/runners/` with fixtures using `FakeModelSeam` and minimal committed cache seeds; expand cache to full sweep coverage during implementation.
2. **Spine before tier wrappers**: implement and test shared orchestration once; T1/T2/T3 modules are parameter wiring only.
3. **Cache expansion**: committed cache MUST cover every export subject × `{t1,t2,t3}` × `sample_index` 0–4 for offline CI; additive entries only.
4. **Do not modify** `specs/001-shared-core/` or `core/` except if a blocking bugfix is discovered (out of scope for this plan).
5. **Out of scope reminder**: no CLI entrypoints, report tables, adversarial gate (Feature 003), autonomous runner (Feature 004), Wilson CIs, or Postgres.

# Implementation Plan: Autonomous Retrieval Evaluation

**Branch**: `004-autonomous-retrieval-eval` | **Date**: 2026-07-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-autonomous-retrieval-eval/spec.md`

## Summary

Deliver filesystem-backed retrieval tools under `core/tools/` that mirror T2 location records and T3 retention floors / governance map without pre-loading into context; an autonomous adjudication runner under `runners/autonomous/` that sweeps all labeled export subjects (3 in the committed export) with request-only (T1-equivalent) initial context, tool-use enabled via an extended `ModelSeam.adjudicate`, and `runner_id=autonomous` cache entries including ordered `tool_calls` traces; and N=5 per-sample aggregate scoring via `core.scoring.score_adjudication` with cross-sample variance. Default execution replays committed cache in offline mode with no live model in CI. Acceptance tests under `tests/autonomous/` are written before implementation and must pass fully offline.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: Inherited from Feature 001 — `pyyaml`, `pydantic` v2; no new runtime deps  
**Storage**: Filesystem — `export/` (frozen subjects + rules, read-only), `cache/` (committed autonomous entries keyed by `autonomous` + T1 prompt hash + sample), `core/tools/` (new, reads export via loader)  
**Testing**: `pytest`; acceptance tests under `tests/autonomous/` mirroring `runners/autonomous/` and `core/tools/`  
**Target Platform**: Linux/macOS/Windows dev; GitHub Actions CI (offline, no API key)  
**Project Type**: Library-style Python package + retrieval tools module + autonomous runner + committed cache expansion  
**Performance Goals**: Full autonomous acceptance suite completes in <60s offline on a standard dev machine  
**Constraints**: No Postgres, no live agent in CI, frozen export/tier/gate modules immutable, `CACHE_MODE=offline` default, N=5 samples only (planning section 9), ground-truth isolation on tools and initial context  
**Scale/Scope**: 3 labeled export subjects (2 with locations requiring cache); 2 × 5 sample indices = 10 autonomous cache entries; 3 retrieval tools; one autonomous runner namespace

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | Evidence |
|-----------|--------|----------|
| **I. Deterministic Ground Truth** | **PASS** | Runner pairs verdicts against `LabeledLocation.expected` only; tools return business fields without labels; no live agent or Postgres ([001/contracts/frozen-export.md](../001-shared-core/contracts/frozen-export.md)) |
| **II. Acceptance-Spec Before Implementation** | **PASS** | Contracts in [contracts/](./contracts/); acceptance suite planned under `tests/autonomous/` before implementation tasks in Phase 2 (`tasks.md`) |
| **III. Frozen-Interface / Frozen-Export Discipline** | **PASS** | No edits to committed `export/`, tier runners, or adversarial gate; additive `core/tools/`, `runners/autonomous/`, cache entries, and tests only (FR-024) |
| **IV. Reproducibility and Offline Verification** | **PASS** | `uv` + `uv.lock`; default `CACHE_MODE=offline`; 10 committed cache entries for full replay; CI without `MODEL_API_KEY` |
| **V. Vocabulary and Wording Discipline** | **PASS** | Reader-facing *autonomous retrieval evaluation*; developer-facing `autonomous` runner_id; DPDP domain terms; no retired scaffolding terms |
| **VI. Currency Before Communication** | **PASS** | No new statute claims; retention floors read from committed export only |
| **VII. Git Flow and Human Merge Gate** | **PASS** | Branch `004-autonomous-retrieval-eval`; PR + human merge; agent does not merge to `main` |
| **VIII. Dependency and Cost Discipline** | **PASS** | No database/pgvector; no new deps; bounded matrix: 3 labeled subjects, 2 cache-backed × N=5 × 1 runner |
| **IX. Tracked Artifacts, Not Ephemeral Chat** | **PASS** | spec/plan/research/data-model/contracts/quickstart committed under `specs/004-autonomous-retrieval-eval/` |
| **X. Stop and Surface Over Silent Choices** | **PASS** | Research resolves tool naming, seam extension, trace schema, cache refresh, and cache cardinality; no unresolved NEEDS CLARIFICATION |

*Post-design re-check (2026-07-04): **PASS** — no violations requiring Complexity Tracking.*

## Scope Guardrails (planning section 9)

- **No Postgres** — filesystem export and cache only.
- **No live agent in CI** — default `CACHE_MODE=offline`; refresh path documented in [quickstart.md](./quickstart.md) but excluded from merge gate.
- **Bounded dependencies** — reuse Feature 001 stack; any addition beyond `pyyaml`/`pydantic` requires PR justification in Complexity Tracking.
- **Bounded cardinality** — N=5 samples per case (`sample_index` 0–4); one autonomous runner; 3 labeled export subjects; 10 cache entries (subjects with locations only, matching Feature 002 seeding).
- **No combinatorial blowup** — cache namespace partitioned by `runner_id` `autonomous`; variance is reporting over five samples, not separate runs.
- **No tier/gate edits** — tier spine and adversarial gate remain frozen reference implementations.

## Test-First Sequencing

Constitution Principle II requires acceptance tests before implementation. Phase 2 `tasks.md` (via `/speckit-tasks`) MUST sequence failing autonomous acceptance tests ahead of implementation:

| Phase | Tests first (MUST FAIL) | Then implement |
|-------|-------------------------|----------------|
| Retrieval tools | `test_acceptance_retrieval_tools.py` | `core/tools/*.py`, `registry.py` |
| Label isolation | `test_acceptance_label_isolation.py` | assert no `expected` in tools/context/cache |
| Tool-call traces | `test_acceptance_tool_call_traces.py` | `ToolCallTrace` type + cache round-trip |
| Autonomous runner | `test_acceptance_autonomous_runner.py` | `runners/autonomous/runner.py` |
| N=5 + variance | `test_acceptance_autonomous_sample_variance.py` | sample loop + reuse `compute_variance_summary` |
| Config discipline | `test_acceptance_autonomous_config.py` | env-driven `MODEL_ID`, `CACHE_MODE` |
| Cache offline | `test_acceptance_autonomous_cache_offline.py` | committed cache replay; miss errors |
| Model seam extension | (covered by runner + cache tests) | optional `tool_registry` on `adjudicate`; `FakeModelSeam` update |
| Committed cache | (covered by cache offline tests) | 10 entries under `cache/primary/autonomous/` |

**Definition of done**: acceptance tests fail for the right reason before autonomous code lands, then pass when the feature completes. Full `tests/autonomous/` suite green offline per SC-001.

## Project Structure

### Documentation (this feature)

```text
specs/004-autonomous-retrieval-eval/
├── plan.md              # This file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── retrieval-tools.md
│   ├── autonomous-runner.md
│   └── tool-call-trace.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created by /speckit-plan)
```

### Source Code (repository root)

```text
core/
├── context/tiers.py     # Feature 001 (unchanged; build_t1 for initial context)
├── export/loader.py     # Feature 001 (unchanged; tools read via ExportBundle)
├── model/
│   ├── seam.py          # extend adjudicate with optional tool_registry
│   └── fake.py          # FakeModelSeam tool-use support for tests
├── cache/store.py       # Feature 001 (unchanged; autonomous uses dedicated refresh helper)
├── scoring/adjudication.py  # Feature 001 (unchanged)
├── types.py             # add ToolCallTrace, AdjudicationSessionResult
└── tools/               # NEW
    ├── __init__.py
    ├── registry.py      # ToolRegistry Protocol stub (Phase 2); full dispatch in Phase 3
    ├── location_records.py
    ├── retention_floors.py
    └── governance_map.py

runners/
├── spine.py             # Feature 002 (unchanged)
├── t1.py, t2.py, t3.py  # Feature 002 (unchanged)
├── pairing.py           # Feature 002 (reused)
├── variance.py          # Feature 002 (reused)
├── types.py             # Feature 002 SampleRollup/VarianceSummary (reused)
├── adversarial_gate/    # Feature 003 (unchanged)
└── autonomous/          # NEW
    ├── __init__.py
    ├── runner.py        # autonomous sweep orchestration
    ├── cache.py         # resolve + refresh with tool_calls persistence
    └── types.py         # AutonomousSweepConfig, AutonomousSweepResult

export/                  # unchanged committed frozen export
cache/                   # expanded: 2 location-bearing subjects × autonomous × sample 0..4 (10 entries)

tests/
├── core/                # Feature 001 (unchanged)
├── runners/             # Feature 002 (unchanged)
├── gate/                # Feature 003 (unchanged)
└── autonomous/          # NEW
    ├── conftest.py
    ├── test_acceptance_retrieval_tools.py
    ├── test_acceptance_label_isolation.py
    ├── test_acceptance_tool_call_traces.py
    ├── test_acceptance_autonomous_runner.py
    ├── test_acceptance_autonomous_sample_variance.py
    ├── test_acceptance_autonomous_config.py
    └── test_acceptance_autonomous_cache_offline.py
```

**Structure Decision**: Per planning section 7 and spec FR-001/FR-004, retrieval tools live in `core/tools/` (shared library surface for seam integration and parity tests) and the autonomous runner in `runners/autonomous/` (orchestration, matching Feature 003 gate subdirectory pattern). Tier runners and adversarial gate remain unchanged. Autonomous runner reuses `runners/pairing.py`, `runners/variance.py`, and Feature 002 result types for sample rollups and variance.

## Autonomous Runner Spine (design summary)

The autonomous runner follows Feature 002 orchestration patterns (detailed in [contracts/autonomous-runner.md](./contracts/autonomous-runner.md)):

1. **Load export** — `load_export()` + `verify_provenance()`; abort on provenance/load errors.
2. **Initialize config** — `MODEL_ID`, `CACHE_MODE` from environment; build `ToolRegistry` from export bundle.
3. **For each `sample_index` in 0..4** (outer loop):
   - Collect `(ModelVerdict, ExpectedLabel)` pairs across all export subjects.
   - **For each subject** in stable export order:
     - Build T1 context via `build_t1` (request-only; no pre-loaded records or rules).
     - Resolve pairing location IDs (export locations when context empty — same as tier spine T1).
     - Skip model call when zero pairing IDs.
     - Form cache key with `runner_id=autonomous` and T1-canonicalized prompt hash.
     - Resolve via `resolve_autonomous_entry`: offline replay or refresh with `tool_registry`.
     - Pair verdicts with `expected` via `pair_subject_verdicts`.
   - **Score sample** — `score_adjudication(all_pairs)` → one `SampleRollup`.
4. **Variance summary** — `compute_variance_summary(sample_rollups)`.
5. **Return** — `AutonomousSweepResult`.

Autonomous-specific code MUST NOT reimplement adjudication rate math; it MUST NOT pre-load T2/T3 data into initial context.

## Retrieval Tools (design summary)

Three filesystem-backed tools (detailed in [contracts/retrieval-tools.md](./contracts/retrieval-tools.md)):

| Tool | T2/T3 parity |
|------|--------------|
| `get_location_records(subject_id)` | T2 `locations` (no `expected`) |
| `get_retention_floors()` | T3 `retention_floors` |
| `get_governance_map()` | T3 `governance_map` |

Tools are registered via `build_retrieval_tool_registry(bundle)` and passed to the model seam during refresh-path adjudication. Acceptance tests verify field-for-field parity with context builders (SC-005).

## Model Seam Extension (design summary)

Extend `ModelSeam.adjudicate` with optional `tool_registry: ToolRegistry | None = None`:

- **Default (`None`)**: unchanged — returns `list[ModelVerdict]`; tier and gate callers unaffected.
- **With registry**: returns `AdjudicationSessionResult` with `verdicts` and `tool_calls`.

`FakeModelSeam` updated for acceptance tests. Live provider implementation required only for refresh-path cache generation, not CI.

## Tool-Call Trace Persistence (design summary)

On refresh, autonomous cache helper writes:

```json
{
  "raw_response": { "verdicts": [ "..."] },
  "tool_calls": [
    {
      "sequence": 0,
      "tool_name": "get_location_records",
      "arguments": { "subject_id": "..." },
      "result_summary": { "location_count": 3, "location_ids": ["..."] }
    }
  ]
}
```

Offline replay reads stored traces without re-executing tools. Schema per [contracts/tool-call-trace.md](./contracts/tool-call-trace.md).

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Generated Artifacts (this command)

| Artifact | Path |
|----------|------|
| Research | [research.md](./research.md) |
| Data model | [data-model.md](./data-model.md) |
| Quickstart | [quickstart.md](./quickstart.md) |
| Retrieval tools contract | [contracts/retrieval-tools.md](./contracts/retrieval-tools.md) |
| Autonomous runner contract | [contracts/autonomous-runner.md](./contracts/autonomous-runner.md) |
| Tool-call trace contract | [contracts/tool-call-trace.md](./contracts/tool-call-trace.md) |

**Next step**: Run `/speckit-tasks` to generate dependency-ordered `tasks.md`.

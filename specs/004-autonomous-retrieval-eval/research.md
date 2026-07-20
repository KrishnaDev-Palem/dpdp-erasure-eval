# Research: 004-autonomous-retrieval-eval

**Date**: 2026-07-04  
**Feature**: Autonomous retrieval evaluation (filesystem tools, tool-use adjudication, committed cache traces)

## R1 — Autonomous runner module layout (planning section 7, spec FR-004)

**Decision**: Add `runners/autonomous/` as a dedicated package with `runner.py` (orchestration), `cache.py` (autonomous cache resolve + refresh with `tool_calls` persistence), `types.py` (`AutonomousSweepConfig`, `AutonomousSweepResult`), and `__init__.py`. Mirror acceptance tests under `tests/autonomous/`. Tier runners (`runners/t1.py`, etc.) and adversarial gate remain unchanged.

**Rationale**: Spec FR-004 places the autonomous runner under `runners/autonomous/`, matching the Feature 003 gate subdirectory pattern. Autonomous flow differs from tier spine (tool-use adjudication, `tool_calls` on cache write, `runner_id=autonomous`) while sharing export loading, pairing, scoring, and variance primitives. A subdirectory keeps autonomous-specific cache refresh logic colocated without branching `runners/spine.py`.

**Alternatives considered**:
- `runners/autonomous.py` (single flat module) — rejected; cache helper with tool trace persistence and config types exceed comfortable single-file scope.
- Extend `runners/spine.py` with `runner_id=autonomous` mode — rejected; spine assumes pre-built context tiers and `CacheStore.get_or_refresh` without `tool_calls`; tool-use path is materially different.
- `core/autonomous/` — rejected; orchestration belongs in `runners/`, not shared library surface.

## R2 — Retrieval tools layout and naming (spec FR-001, FR-002)

**Decision**: Add `core/tools/` with three filesystem-backed callables:

| Tool name | Module | Input | Output parity |
|-----------|--------|-------|---------------|
| `get_location_records` | `core/tools/location_records.py` | `subject_id: str` | T2 `ContextBundle.locations` (business fields only) |
| `get_retention_floors` | `core/tools/retention_floors.py` | none | T3 `retention_floors` from export rules corpus |
| `get_governance_map` | `core/tools/governance_map.py` | none | T3 `governance_map` from export rules corpus |

All tools accept an `ExportBundle` (or resolve via `load_export`) at registry construction time; they MUST NOT accept `expected` labels or return them. Shared registry factory: `core/tools/registry.py` → `build_retrieval_tool_registry(bundle: ExportBundle) -> ToolRegistry`.

**Rationale**: Three tools map 1:1 to T2 record layer and T3 rules layers (spec assumption). Snake_case names align with cache/runner conventions. Export-scoped registry prevents cross-subject leakage and mirrors "read from committed export on disk" requirement.

**Alternatives considered**:
- Single `get_context_slice(tier: str)` tool — rejected; collapses retrieval layers; does not mirror discrete T2/T3 fetches.
- Tools under `runners/autonomous/tools.py` — rejected; spec FR-001 requires `core/tools/`; tools are reusable library surface for seam integration and acceptance parity tests.
- Live Postgres/agent backends — rejected; violates constitution I and spec FR-003.

## R3 — Model seam tool-use extension (spec assumption, FR-007)

**Decision**: Extend `ModelSeam.adjudicate` with an optional keyword-only parameter `tool_registry: ToolRegistry | None = None`. When `tool_registry` is `None` (default), behavior is unchanged — returns `list[ModelVerdict]`. When provided, returns `AdjudicationSessionResult` containing `verdicts: list[ModelVerdict]` and `tool_calls: list[ToolCallTrace]`.

Implement via:
1. New types in `core/types.py`: `ToolCallTrace`, `AdjudicationSessionResult`, `ToolRegistry` protocol.
2. Protocol update documented in a **004 addendum** to [001/contracts/model-seam.md](../001-shared-core/contracts/model-seam.md) (004 contract cross-reference; do not edit 001 file — document extension in [contracts/autonomous-runner.md](./contracts/autonomous-runner.md)).
3. `FakeModelSeam` extended: when `tool_registry` provided, optionally invoke configured tools and record traces for acceptance tests.
4. Live provider implementation: refresh path only; offline CI uses committed cache.

Tier and gate callers continue passing no `tool_registry`; type checkers treat default path as `list[ModelVerdict]` via overload or union handling in autonomous runner only.

**Rationale**: Optional parameter preserves frozen tier/gate call sites. Separate return type when tools enabled captures traces without overloading cache `raw_response`. Spec explicitly allows extend-or-wrap; extension on protocol keeps a single adjudication entry point.

**Alternatives considered**:
- New `adjudicate_with_tools()` method only — acceptable but duplicates protocol surface; optional kwarg is simpler for `FakeModelSeam`.
- Wrapper class outside seam — rejected; runner would still need trace capture from live sessions on refresh.
- Change return type always to `AdjudicationSessionResult` — rejected; breaks tier runner call sites and Feature 001/002 contracts.

## R4 — Tool-call trace schema (spec FR-015, cache contract)

**Decision**: Define `ToolCallTrace` as a Pydantic model persisted in `CacheEntry.tool_calls`:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sequence` | int | yes | 0-based order within session |
| `tool_name` | string | yes | One of `get_location_records`, `get_retention_floors`, `get_governance_map` |
| `arguments` | object | yes | JSON-serializable args passed to tool (e.g. `{"subject_id": "..."}`) |
| `result_summary` | object | yes | Auditable summary — counts and IDs, not full rules text duplication when large |

**Result summary conventions**:
- `get_location_records`: `{"subject_id", "location_count", "location_ids": [...]}`
- `get_retention_floors`: `{"floor_count": 5, "floor_ids": [...]}`
- `get_governance_map`: `{"entry_count", "categories": [...]}`

Empty `tool_calls: []` when model adjudicates without invoking tools (valid per spec edge case).

**Rationale**: Ordered traces with identity + summaries satisfy audit requirement without bloating cache with full rules corpus on every call. Aligns with existing `CacheEntry.tool_calls: list[Any]` field in `core/types.py`.

**Alternatives considered**:
- Full tool response in trace — rejected; duplicates export data across cache entries; summary suffices for audit.
- Opaque hash-only traces — rejected; insufficient for reviewer verification (spec US3).

## R5 — Autonomous cache key identity and refresh path (spec FR-014, FR-011–FR-015)

**Decision**:
1. **Prompt hash**: Build initial context with `build_t1(request, subject)` and use existing `make_cache_key(context=..., runner_id=autonomous, ...)`. Hash matches T1 for the same subject (request-only canonicalization); only `runner_id` differs from tier T1 namespace.
2. **Refresh path**: `runners/autonomous/cache.py` → `resolve_autonomous_entry(...)`:
   - Offline hit → return entry (use `raw_response.verdicts`, ignore re-executing tools).
   - Offline miss → `CacheMissError` with path identifying `case_id`, `sample_index`, `runner_id=autonomous`.
   - Refresh miss → `seam.adjudicate(context=..., case_id=..., tool_registry=registry)` → persist `CacheEntry` with `raw_response={"verdicts": [...]}` and `tool_calls=[...]`.
3. Do **not** modify `CacheStore.get_or_refresh` (tier path); autonomous runner uses dedicated helper.

**Rationale**: FR-014 requires request-only canonicalization, not tool-call sequences. T1-equivalent hash enables cross-checking prompt identity against tier T1 entries in acceptance tests. Dedicated refresh path is the only place `tool_calls` get written on live fetch.

**Alternatives considered**:
- Include tool calls in prompt hash — rejected; violates FR-014 and would invalidate cache on different retrieval paths.
- Extend global `CacheStore.get_or_refresh` with optional tool_registry — rejected; risks tier entries gaining tool_calls accidentally; violates separation.

## R6 — Variance and sweep result reuse (spec FR-017–FR-018)

**Decision**: Reuse Feature 002 types unchanged:
- `SampleRollup`, `VarianceSummary`, `RateVariance`, `RateAtSample` from `runners/types.py`
- `compute_variance_summary` from `runners/variance.py`

Introduce `AutonomousSweepResult` in `runners/autonomous/types.py` with `runner_id="autonomous"`, no `tier` field, and `initial_context_tier: Literal["t1"]` metadata documenting request-only pre-load. Five `SampleRollup` entries + `VarianceSummary` mirror [002/contracts/sweep-result.md](../002-context-tier-sweep/contracts/sweep-result.md).

**Rationale**: Spec FR-017–FR-018 require identical adjudication metrics and variance shape as tier sweeps. Reusing types avoids duplicate validation and lets acceptance tests share hand-calculation patterns from `tests/runners/test_acceptance_sample_variance.py`.

**Alternatives considered**:
- Subclass `TierSweepResult` with `tier="t1"` — rejected; misleading metadata (autonomous is not a tier runner).
- Gate-style separate variance types — rejected; adjudication metrics match tier, not gate.

## R7 — Committed cache cardinality (spec FR-019, planning section 9)

**Decision**: Commit autonomous cache entries for all export subjects **with at least one location** × **5** sample indices = **10** entries under `cache/{model_id}/autonomous/{case_id}/{prompt_hash}/{sample_index}.json`. Prompt hashes per subject match corresponding T1 entries (different `runner_id` directory only). Subjects with empty `locations` (e.g. `empty-locations-subject`) are swept but skipped for cache seeding — no model call — matching Feature 002 `scripts/seed_runner_cache.py` behavior.

**Rationale**: Current export has **3** labeled subjects in `export/adjudication/subjects.yaml`; **2** have locations requiring adjudication. Bounded matrix: 2 × 5 × 1 runner = 10 entries — well within constitution VIII cost guardrails. Full offline CI replay requires cache for every subject that invokes the model (FR-019).

**Alternatives considered**:
- Partial cache with subset subjects — rejected; FR-019 requires cache for all location-bearing subjects for CI.
- Cache entries for empty-location subjects — rejected; no model call means no cache key needed (tier runner precedent).
- Single sample only — rejected; N=5 is settled guardrail (spec US4).

## R8 — Test-first acceptance suite layout (spec FR-020, constitution II)

**Decision**: Place acceptance tests under `tests/autonomous/`:

| Test module | Validates |
|-------------|-----------|
| `test_acceptance_retrieval_tools.py` | Tool parity vs T2/T3 builders; no `expected` leakage |
| `test_acceptance_autonomous_runner.py` | Full sweep; all subjects visited; tool-use enabled |
| `test_acceptance_label_isolation.py` | No `expected` in tool responses, initial context, cache payloads |
| `test_acceptance_autonomous_sample_variance.py` | N=5 rollups + variance summary |
| `test_acceptance_autonomous_config.py` | Env-driven `MODEL_ID`, `CACHE_MODE` |
| `test_acceptance_autonomous_cache_offline.py` | Offline replay; `tool_calls` present; miss errors |
| `test_acceptance_tool_call_traces.py` | Trace schema and tier-runner absence of traces |

**Rationale**: Mirrors `tests/gate/` and `tests/runners/` patterns. Tests written before implementation per constitution II.

**Alternatives considered**:
- `tests/runners/autonomous/` — acceptable per spec "e.g."; chose top-level `tests/autonomous/` for parity with `tests/gate/`.

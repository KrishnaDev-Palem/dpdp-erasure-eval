# Retrieval Tools Contract

**Version**: 1.0.0  
**Feature**: 004-autonomous-retrieval-eval  
**Authority**: Spec FR-001–FR-003, FR-002; planning §4 autonomous retrieval evaluation

## Purpose

Define filesystem-backed retrieval tools that expose T2/T3-equivalent data on demand without pre-loading into adjudication context. Tools read from the committed frozen export via the shared export loader; they MUST NOT return `expected` labels or call live agents.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Frozen export loader | [001/contracts/frozen-export.md](../../001-shared-core/contracts/frozen-export.md) |
| Context tier builders (parity reference) | [001/contracts/context-tiers.md](../../001-shared-core/contracts/context-tiers.md) |
| Core domain types | [001/data-model.md](../../001-shared-core/data-model.md) |

## Module layout

```text
core/tools/
├── __init__.py
├── registry.py          # build_retrieval_tool_registry(bundle) -> ToolRegistry
├── location_records.py  # get_location_records
├── retention_floors.py  # get_retention_floors
└── governance_map.py    # get_governance_map
```

## ToolRegistry

Built once per sweep from a verified `ExportBundle`:

```text
build_retrieval_tool_registry(bundle: ExportBundle) -> ToolRegistry
```

`ToolRegistry` exposes callables the model seam invokes by name during tool-use adjudication. Registry is scoped to the loaded export; it MUST NOT read from Postgres or live agent APIs.

## Tool: get_location_records

**Purpose**: Return location business fields for a subject — parity with T2 `build_t2` location list.

### Input

| Field | Type | Required |
|-------|------|----------|
| `subject_id` | string | yes |

### Output

JSON-serializable object:

```json
{
  "subject_id": "mixed-fanout-subject",
  "locations": [ { "location_id": "...", "entity": "...", "...": "..." } ]
}
```

Each location object MUST match T2 builder output field-for-field (excluding `expected`). When subject has empty locations, return `"locations": []`.

### Errors

| Condition | Behavior |
|-----------|----------|
| Unknown `subject_id` | Return `{"subject_id": "...", "locations": [], "error": "subject_not_found"}` — no data from other subjects |
| Export not loaded | Propagate `ExportLoadError` / `ProvenanceError` from loader (fail closed) |

## Tool: get_retention_floors

**Purpose**: Return full five sectoral retention-floor texts — parity with T3 `retention_floors`.

### Input

None (empty object `{}`).

### Output

```json
{
  "retention_floors": [
    {
      "floor_id": "pmla_kyc",
      "minimum_period": "...",
      "statute_citation": "..."
    }
  ]
}
```

MUST include all five required floors: `pmla_kyc`, `gst`, `income_tax`, `companies_act`, `sebi` — same validation as export loader.

## Tool: get_governance_map

**Purpose**: Return full governance map — parity with T3 `governance_map`.

### Input

None (empty object `{}`).

### Output

```json
{
  "governance_map": [
    {
      "category": "...",
      "floors": ["..."],
      "anchor_selector": "..."
    }
  ]
}
```

## Ground-truth isolation

- Tool responses MUST NOT include `expected`, `verdict`, or ground-truth fields from `LabeledLocation`.
- Tools MUST NOT infer labels from business fields.
- Acceptance tests MUST compare tool output to `build_t2` / `build_t3` builder output on representative subjects (SC-005).

## Parity verification (acceptance)

For each representative export subject:

1. `get_location_records(subject_id)` locations == `build_t2(...).locations` (field-for-field).
2. `get_retention_floors()` == `build_t3(...).retention_floors`.
3. `get_governance_map()` == `build_t3(...).governance_map`.

## Non-goals

- Caching inside tools (export bundle is in-memory for sweep duration).
- Tool authorization beyond export scope.
- Mutating export files.

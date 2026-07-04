# Tool-Call Trace Contract

**Version**: 1.0.0  
**Feature**: 004-autonomous-retrieval-eval  
**Authority**: Spec FR-015, US3; [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) `tool_calls` field

## Purpose

Define the schema for ordered tool-invocation traces persisted in autonomous cache entries. Traces are autonomous-runner-only; tier and gate entries use empty `tool_calls`.

## Storage location

`CacheEntry.tool_calls: list[ToolCallTrace]` serialized in committed cache JSON at:

```text
cache/{model_id}/autonomous/{case_id}/{prompt_hash}/{sample_index}.json
```

## ToolCallTrace shape

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sequence` | int | yes | 0-based invocation order within adjudication session |
| `tool_name` | string | yes | `get_location_records`, `get_retention_floors`, or `get_governance_map` |
| `arguments` | object | yes | Arguments passed to tool (JSON-serializable) |
| `result_summary` | object | yes | Auditable summary of tool response (see below) |

### Example

```json
{
  "sequence": 0,
  "tool_name": "get_location_records",
  "arguments": { "subject_id": "mixed-fanout-subject" },
  "result_summary": {
    "subject_id": "mixed-fanout-subject",
    "location_count": 3,
    "location_ids": ["loc-a", "loc-b", "loc-c"]
  }
}
```

## Result summary conventions

Summaries MUST be sufficient for offline audit without requiring re-execution of tools.

| Tool | Required summary fields |
|------|-------------------------|
| `get_location_records` | `subject_id`, `location_count`, `location_ids` |
| `get_retention_floors` | `floor_count` (must be 5), `floor_ids` |
| `get_governance_map` | `entry_count`, `categories` |

When tool returns an error object (e.g. `subject_not_found`), summary MUST include `error` key with the error code.

## Ordering rules

1. `sequence` values MUST be contiguous starting at 0.
2. Order reflects invocation order during live adjudication (refresh path).
3. Offline replay MUST NOT re-execute tools; traces are read-only from cache.

## Empty traces

When the model adjudicates without invoking tools, `tool_calls` MUST be `[]` (not omitted). This is a valid observable outcome, not an error.

## Namespace isolation

| `runner_id` | `tool_calls` expectation |
|-------------|-------------------------|
| `autonomous` | Ordered trace list (possibly empty) |
| `t1`, `t2`, `t3` | `[]` or absent (normalized to `[]` on read) |
| `adversarial_gate` | `[]` or absent |

Acceptance tests MUST assert tier-runner cache entries lack non-empty `tool_calls`.

## raw_response relationship

`raw_response` continues to hold adjudication verdicts only:

```json
{
  "verdicts": [
    { "location_id": "...", "verdict": "erase", "detail": null }
  ]
}
```

Tool traces MUST NOT be embedded inside `raw_response`; they live exclusively in `tool_calls`.

## Non-goals

- Persisting full tool response bodies in cache (use export for full content).
- Re-deriving traces from model prose on offline replay.
- Tool traces for gate `classify_note` sessions.

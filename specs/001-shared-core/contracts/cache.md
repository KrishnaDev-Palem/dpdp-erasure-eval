# Cache Contract

**Version**: 1.0.0  
**Authority**: Planning §7 (reproducibility mechanics), spec FR-014–FR-016

## Storage root

Default: `cache/` at repository root (committed entries allowed).

## Key identity

Canonical string key (filesystem path derived by hashing or joining sanitized components):

```text
{model_id}/{runner_id}/{case_id}/{prompt_hash}/{sample_index}.json
```

| Component | Description |
|-----------|-------------|
| `model_id` | Configured model identifier |
| `runner_id` | `t1`, `t2`, `t3`, `adversarial_gate`, `autonomous` (future) |
| `case_id` | Subject or adversarial case id |
| `prompt_hash` | SHA-256 of UTF-8 JSON from `canonicalize(context)` |
| `sample_index` | Integer 0–4 (N=5 sampling) |

## Entry schema

```json
{
  "model_id": "primary",
  "runner_id": "t1",
  "case_id": "mixed-fanout-subject",
  "prompt_hash": "<hex>",
  "sample_index": 0,
  "recorded_at": "2026-07-01T12:00:00Z",
  "raw_response": {},
  "tool_calls": []
}
```

`tool_calls` is optional; reserved for Feature 004 autonomous variant.

## Modes

| Mode | Env | Behavior |
|------|-----|----------|
| offline | `CACHE_MODE=offline` (default) | Read cache only; miss → `CacheMissError` |
| refresh | `CACHE_MODE=refresh` | On miss, call live model via seam, write entry |

## Canonicalization

`canonicalize(context)`:

1. JSON serialize with sorted keys.
2. No whitespace variance between runs.
3. Same function used for prompt hashing across tiers.

## CI requirement

Full acceptance suite MUST pass in `offline` mode with no `MODEL_API_KEY`.

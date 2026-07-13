# Data Model: 006-live-model-seam

**Date**: 2026-07-09  
**Feature**: Live model seam wiring

This document defines Feature 006 types only. Core domain entities (`ModelVerdict`, `ClassifierResult`, `ContextBundle`, `AdjudicationSessionResult`, `CacheKey`, `CacheEntry`, etc.) remain in `core/types.py` and [001/data-model.md](../001-shared-core/data-model.md).

## ModelRoleDescriptor

Static registry entry mapping a harness model role to provider metadata. Defined in `core/model/roles.py` (not persisted).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `role_id` | string | yes | Value of `MODEL_ID` / cache key segment (e.g. `claude-sonnet-5`) |
| `provider` | `"anthropic"` \| `"google"` \| `"test"` | yes | `test` for offline-only `primary` |
| `provider_model_id` | string \| null | yes | Pinned API id; `null` for `primary` |
| `credential_env_vars` | list[string] | yes | Preferred env names in precedence order |

**Validation**:
- `role_id` MUST be unique in registry.
- Live roles MUST have non-null `provider_model_id` and non-empty `credential_env_vars`.
- `primary` MUST use `provider=test` and MUST NOT resolve to a live adapter in refresh mode.

## ProviderCredentialPolicy

Runtime credential resolution result (not necessarily a persisted dataclass).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `provider` | string | yes | `anthropic` or `google` |
| `api_key` | string | yes | Resolved secret value |
| `source_env_var` | string | yes | Which env var supplied the key |
| `used_legacy_fallback` | boolean | yes | `true` when `MODEL_API_KEY` used |

**Resolution order** (per research R5):
1. First set variable in `credential_env_vars` for the role's provider.
2. Else if `MODEL_API_KEY` set → use with deprecation warning.
3. Else → raise `ConfigurationError` listing required variables.

## LiveAdapterConfig

Construction-time settings passed to live adapters (frozen dataclass).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `role_id` | string | yes | Harness role |
| `provider_model_id` | string | yes | Pinned provider id from registry |
| `api_key` | string | yes | From `ProviderCredentialPolicy` |
| `request_timeout_seconds` | float | yes | Default `120.0`; bounded to avoid hung refresh |
| `max_tool_rounds` | int | yes | Default `10` for autonomous tool loops |

**Validation**:
- `max_tool_rounds` MUST be ≥ 1 and ≤ 20 (cost guardrail).

## FactoryResolutionRequest

Logical input to `create_model_seam()` (derived from environment via `load_model_config()` + credential helpers).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `model_id` | string | yes | From `MODEL_ID` (default `primary`) |
| `cache_mode` | string | yes | From `CACHE_MODE` (default `offline`) |

**State transitions**:

```text
offline + any model_id → FakeModelSeam
refresh + primary → ConfigurationError (no live adapter)
refresh + unknown role → ConfigurationError
refresh + live role + missing key → ConfigurationError
refresh + live role + valid key → AnthropicModelSeam | GeminiModelSeam
```

## AnthropicModelSeam / GeminiModelSeam

Live `ModelSeam` implementations (classes, not persisted).

| Responsibility | Method | Return (no tools) | Return (with tools) |
|----------------|--------|-------------------|---------------------|
| Tier adjudication | `adjudicate(context, case_id)` | `list[ModelVerdict]` | — |
| Autonomous adjudication | `adjudicate(context, case_id, tool_registry=...)` | — | `AdjudicationSessionResult` |
| Gate classification | `classify_note(text, case_id?)` | `ClassifierResult` | — |

**Validation** (inherited from [001/contracts/model-seam.md](../001-shared-core/contracts/model-seam.md)):
- Verdict ∈ `{erase, retain, escalate}` per context location.
- Classification outcome ∈ `{clean, adversarial}`.
- Contract violations → `ModelResponseError`; no cache write.

## Cache interaction (unchanged schema)

Live adapters do **not** define new cache fields. On refresh miss, existing helpers write:

| Path | `raw_response` shape | `tool_calls` |
|------|----------------------|--------------|
| Tier (`get_or_refresh`) | `{"verdicts": [...]}` | absent |
| Gate (`classify_with_cache`) | `ClassifierResult` dump | absent |
| Autonomous (`resolve_autonomous_entry`) | `{"verdicts": [...]}` | ordered trace list |

**Relationships**: `ModelRoleDescriptor` → selected by `FactoryResolutionRequest.model_id` → constructs adapter → passed to cache helpers unchanged from Feature 001–004.

## Configuration surface (environment)

| Variable | Default | Used by |
|----------|---------|---------|
| `MODEL_ID` | `primary` | Cache keys, sweep metadata, factory role lookup |
| `CACHE_MODE` | `offline` | Factory seam selection; `CacheStore` miss behavior |
| `ANTHROPIC_API_KEY` | unset | Claude adapter auth |
| `GEMINI_API_KEY` | unset | Gemini adapter auth |
| `MODEL_API_KEY` | unset | Deprecated fallback for either provider |

See [contracts/model-seam-factory.md](./contracts/model-seam-factory.md) for resolution contract.

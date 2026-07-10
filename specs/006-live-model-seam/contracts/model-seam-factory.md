# Model Seam Factory Contract

**Version**: 1.0.0  
**Feature**: 006-live-model-seam  
**Authority**: Feature 006 spec FR-005, FR-006, FR-007, FR-014; [001/contracts/model-seam.md](../001-shared-core/contracts/model-seam.md)

## Entry point

```python
def create_model_seam(*, config: ModelConfig | None = None) -> ModelSeam: ...
```

- When `config` is omitted, load via `load_model_config()`.
- MUST NOT perform network I/O during resolution.
- MUST NOT import provider SDK modules at factory module import time (lazy import inside branch).

## Resolution rules

| Condition | Result |
|-----------|--------|
| `config.cache_mode == "offline"` | `FakeModelSeam()` — **always**, regardless of API keys |
| `config.cache_mode == "refresh"` and `config.model_id == "primary"` | Raise `ConfigurationError` — committed cache role has no live adapter |
| `config.cache_mode == "refresh"` and unknown `model_id` | Raise `ConfigurationError` listing supported live roles |
| `config.cache_mode == "refresh"` and live role, missing credential | Raise `ConfigurationError` naming `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` (and noting `MODEL_API_KEY` deprecated fallback) |
| `config.cache_mode == "refresh"` and live role, valid credential | Return provider adapter for role |

Supported live roles (v1): `claude-sonnet-5`, `gemini-3.5-flash`.

## Credential resolution

```python
def resolve_provider_api_key(*, provider: Literal["anthropic", "google"]) -> ProviderCredentialPolicy: ...
```

| Provider | Preferred env | Legacy fallback |
|----------|---------------|-----------------|
| `anthropic` | `ANTHROPIC_API_KEY` | `MODEL_API_KEY` |
| `google` | `GEMINI_API_KEY` | `MODEL_API_KEY` |

- When both preferred and legacy are set, preferred wins; legacy ignored.
- When only legacy is set, emit `DeprecationWarning` with message identifying provider and preferred variable.
- Missing both → `ConfigurationError` before adapter construction.

## Role registry

Provider model ids MUST come from `core/model/roles.py` registry — not from runners, CLI, or cache helpers.

| Harness role | Provider model id |
|--------------|-------------------|
| `claude-sonnet-5` | `claude-sonnet-5` |
| `gemini-3.5-flash` | `gemini-3.5-flash` |

## CLI integration

`cli/main.py` MUST call `create_model_seam()` for all subcommands that invoke runners (`t1`, `t2`, `t3`, `autonomous`, `adversarial-gate`).

Runners MUST continue to accept explicit `seam=` injection; factory is bypassed when callers pass a seam (acceptance tests, library use).

## Errors

| Error | When |
|-------|------|
| `ConfigurationError` | Unknown role, missing credential, refresh + `primary`, invalid `CACHE_MODE` |
| `ModelResponseError` | Live response fails seam contract (raised by adapter, not factory) |

Network/provider failures from adapters propagate as exceptions with provider context; MUST NOT fall back to `FakeModelSeam` or offline cache.

## Configuration documentation

`.env.example` MUST list (values empty):

- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`
- `MODEL_ID`
- `CACHE_MODE`
- `MODEL_API_KEY` (deprecated comment)

## CI exclusion

Factory and adapter acceptance tests MUST pass in CI with no API keys and no network. Opt-in live smoke tests use `@pytest.mark.live` and are excluded from the merge gate.

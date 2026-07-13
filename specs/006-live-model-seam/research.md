# Research: 006-live-model-seam

**Date**: 2026-07-09  
**Feature**: Live model seam wiring (Claude Sonnet 5 + Gemini 3.5 Flash)

## R1 — Anthropic API model identifier (Constitution Principle VI)

**Decision**: Pin provider model id **`claude-sonnet-5`** for the `claude-sonnet-5` harness role.

**Rationale**: Anthropic platform docs (Models overview, What's new in Claude Sonnet 5) list Claude Sonnet 5 with API id `claude-sonnet-5` as a dateless pinned snapshot alias. Verified 2026-07-09.

**Sources**:
- https://platform.claude.com/docs/en/about-claude/models/overview
- https://platform.claude.com/docs/en/about-claude/models/whats-new-sonnet-5

**Alternatives considered**:
- `claude-sonnet-4-6` — rejected; spec targets Sonnet 5.
- Dated snapshot ids (pre-.6 generation style) — rejected; Sonnet 5 uses dateless pinned alias per Anthropic docs.

**Migration notes for adapter implementation**:
- Do **not** send non-default `temperature`, `top_p`, or `top_k` (400 errors on Sonnet 5).
- Extended thinking uses adaptive mode; prefer `thinking: {type: "disabled"}` or low `effort` for bounded eval cost unless autonomous tool-use requires more reasoning.
- Tokenizer change increases token count vs prior Sonnet; keep prompts bounded per cost discipline.

## R2 — Google Gemini API model identifier (Constitution Principle VI)

**Decision**: Pin provider model id **`gemini-3.5-flash`** for the `gemini-3.5-flash` harness role.

**Rationale**: Google AI Gemini API docs (What's new in Gemini 3.5 Flash — generateContent and Interactions APIs) and Google Cloud model page list GA model id `gemini-3.5-flash` (release 2026-05-19). Verified 2026-07-09.

**Sources**:
- https://ai.google.dev/gemini-api/docs/generate-content/whats-new-gemini-3.5
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-5-flash

**Alternatives considered**:
- `gemini-3-flash-preview` — rejected; superseded by GA `gemini-3.5-flash`.
- `gemini-3.1-flash-lite` — rejected for this feature; spec names 3.5 Flash as target.

**Migration notes for adapter implementation**:
- Replace legacy `thinking_budget` with `thinking_config.thinking_level` (`minimal` | `low` | `medium` | `high`); default harness eval: **`low`** for cost discipline.
- Do **not** send `temperature`, `top_p`, `top_k` (no longer recommended for Gemini 3.x).
- Tool/function responses must include matching `id` and `name` on `FunctionResponse` parts when using tools.

## R3 — Harness `MODEL_ID` role aliases

**Decision**: Register three logical roles in a single registry module (`core/model/roles.py`):

| Harness `MODEL_ID` | Provider | Provider model id | Credential env var(s) |
|--------------------|----------|-------------------|------------------------|
| `primary` | (none — offline/test) | — | — |
| `claude-sonnet-5` | anthropic | `claude-sonnet-5` | `ANTHROPIC_API_KEY` |
| `gemini-3.5-flash` | google | `gemini-3.5-flash` | `GEMINI_API_KEY` |

**Rationale**: Committed cache entries use `primary`; live refresh targets pin new roles without embedding provider strings in runners/CLI. Factory maps role → adapter + pinned provider id.

**Alternatives considered**:
- Raw provider strings as `MODEL_ID` — rejected; spec requires role aliases and config mapping.
- YAML registry file — acceptable but unnecessary; Python registry keeps validation co-located with factory and avoids a second parser.

## R4 — Provider SDK vs raw HTTP

**Decision**: Use official SDKs:
- **`anthropic>=0.49.0,<1`** — Messages API with tool-use for autonomous path.
- **`google-genai>=1.14.0,<2`** — `genai.Client` generateContent with tools.

**Rationale**: Both providers' GA models assume SDK-level handling for adaptive thinking, tool loops, and structured errors. Raw HTTP duplicates auth, retry, and tool-session wiring with no cost savings. SDKs are lightweight relative to harness scope; lazy-import in factory keeps offline import path free of network side effects.

**Alternatives considered**:
- `httpx` only — rejected; higher maintenance for tool-use loops and provider-specific request shapes.
- Vertex AI / Bedrock endpoints — rejected; spec targets direct API keys (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) for local refresh workflow.

## R5 — Factory resolution policy

**Decision**: Add `create_model_seam()` in `core/model/factory.py`:

| `CACHE_MODE` | `MODEL_ID` | Result |
|--------------|------------|--------|
| `offline` | any | `FakeModelSeam()` always — even if API keys present (spec US4) |
| `refresh` | `primary` | `ConfigurationError` before network — no live adapter for legacy committed-cache role |
| `refresh` | supported live role + valid credential | matching live adapter instance |
| `refresh` | unknown role | `ConfigurationError` before network |
| `refresh` | supported role, missing credential | `ConfigurationError` naming required env var(s) before network |

Credential resolution (`resolve_provider_api_key(provider)`):
1. Provider-specific env var (`ANTHROPIC_API_KEY` / `GEMINI_API_KEY`).
2. Fallback: legacy `MODEL_API_KEY` with `warnings.warn(..., DeprecationWarning)` when provider-specific unset.
3. Provider-specific wins when both set.

**Rationale**: Matches spec FR-005, FR-006, FR-014; preserves offline CI; CLI is the primary consumer — runners keep constructor injection unchanged.

**Alternatives considered**:
- Factory returns live adapter in offline mode when keys present — rejected; violates spec US4 and offline CI contract.
- Auto-map `primary` → Claude in refresh — rejected; would write cache under wrong namespace vs committed entries.

## R6 — Refresh path wiring (reuse existing cache helpers)

**Decision**: **Do not modify** `CacheStore.get_or_refresh`, `classify_with_cache`, or `resolve_autonomous_entry`. Live adapters satisfy the existing `ModelSeam` protocol; cache helpers already call `seam.adjudicate` / `seam.classify_note` on miss when `cache_mode == "refresh"`.

**Integration surface**:
- **CLI** (`cli/main.py`): replace `FakeModelSeam()` with `create_model_seam()`.
- **Runners**: unchanged — accept injected `seam`; tests continue injecting `FakeModelSeam` directly.
- **Autonomous**: live `adjudicate(..., tool_registry=...)` MUST return `AdjudicationSessionResult` with ordered `tool_calls`.

**Rationale**: Feature 001–004 cache contracts are frozen reference implementations. Feature 006 adds seam implementations only.

**Alternatives considered**:
- New cache wrapper that knows about providers — rejected; duplicates mode logic already in three helpers.

## R7 — Prompt/response parsing strategy

**Decision**: Adapters build prompts from `ContextBundle` fields already used by committed cache (tier, locations, retention floors, governance map — never `expected`). Responses parsed to strict JSON-or-tool schema:
- Adjudication: list of `{location_id, verdict}` → `ModelVerdict` list or tool-mediated equivalent.
- Classification: `{outcome, detail?}` → `ClassifierResult`.
- Invalid shapes → `ModelResponseError`; cache helpers MUST NOT `put` on exception (existing behavior + explicit adapter tests).

**Rationale**: Aligns with model-seam contract and FR-013; keeps offline replay format stable (`raw_response.verdicts` / classifier dump).

**Alternatives considered**:
- Free-text verdict parsing with regex — rejected; fragile and hides contract violations.

## R8 — Acceptance test strategy (no live keys in CI)

**Decision**:

| Suite | Location | Network | Keys |
|-------|----------|---------|------|
| Factory resolution | `tests/core/test_acceptance_model_factory.py` | No | No |
| Adapter contract (mocked SDK) | `tests/core/test_acceptance_live_adapters.py` | No | No |
| Credential resolution | `tests/core/test_acceptance_provider_credentials.py` | No | No |
| Existing refresh replay | `tests/**/test_acceptance_*refresh*` | No | No — uses `FakeModelSeam` |
| Full offline regression | `uv run pytest -v` (CI) | No | No |
| Opt-in live smoke | `tests/live/` + `@pytest.mark.live` | Yes | Yes — **excluded from CI** |

Mock at SDK client boundary (`unittest.mock` / pytest monkeypatch) so adapter parsing and tool loops are exercised without billing.

**Rationale**: Constitution Principle II (acceptance-spec first) and Principle IV (CI offline). Spec FR-010/FR-011.

**Alternatives considered**:
- VCR cassettes of live responses — rejected for v1; adds fixture maintenance and secret leakage risk.

## R9 — Dependency and cost bounds

**Decision**:
- Add two runtime dependencies (Complexity Tracking justified in plan).
- Refresh runs remain operator-driven, single-case spot checks documented in quickstart — not full-matrix regeneration in CI.
- Default adapter settings: Gemini `thinking_level=low`, Anthropic thinking disabled or `effort=low` for tier/gate; autonomous may use `medium` when tool-use quality requires it (documented in adapter module docstring).

**Rationale**: Constitution Principle VIII — tens-of-dollars spend, no combinatorial blowup.

**Alternatives considered**:
- Optional `[live]` extra only — rejected; complicates `uv sync` reproducibility when adapters are core feature deliverable; lazy import suffices for offline safety.

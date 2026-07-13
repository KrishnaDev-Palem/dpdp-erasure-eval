# Live Provider Adapters Contract

**Version**: 1.0.0  
**Feature**: 006-live-model-seam  
**Extends**: [001/contracts/model-seam.md](../001-shared-core/contracts/model-seam.md) (additive — tool_registry and session result already in implementation)

## Implementations

| Class | Module | Harness role | Provider model id |
|-------|--------|--------------|-------------------|
| `AnthropicModelSeam` | `core/model/anthropic_adapter.py` | `claude-sonnet-5` | `claude-sonnet-5` |
| `GeminiModelSeam` | `core/model/gemini_adapter.py` | `gemini-3.5-flash` | `gemini-3.5-flash` |

Both MUST satisfy the `ModelSeam` protocol in `core/model/seam.py`.

## Dependencies (pinned in pyproject.toml / uv.lock)

| Package | Constraint | Purpose |
|---------|------------|---------|
| `anthropic` | `>=0.49.0,<1` | Messages API + tool use |
| `google-genai` | `>=1.14.0,<2` | generateContent + tools |

Lazy-import SDK clients inside adapter `__init__` or first call — not at `core.model` package import.

## Adjudicate (tier — no tool registry)

**Input**: `ContextBundle` without `expected`; `case_id`.

**Output**: `list[ModelVerdict]` with exactly one verdict per `location_id` in `context.locations`.

**Provider constraints** (verified 2026-07-09):
- Anthropic: do not send non-default sampling params; thinking disabled or low effort for cost.
- Gemini: use `thinking_level=low` default; no legacy `thinking_budget`.

## Adjudicate (autonomous — with tool registry)

**Input**: same as tier + non-null `ToolRegistry`.

**Output**: `AdjudicationSessionResult` with:
- `verdicts`: complete list aligned to context locations
- `tool_calls`: ordered trace entries compatible with [004/contracts/tool-call-trace.md](../004-autonomous-retrieval-eval/contracts/tool-call-trace.md) serialization

**Tool loop**: Adapter invokes registry callables; MUST respect `max_tool_rounds` from `LiveAdapterConfig`; on exceed → raise clear error (no partial cache write).

## Classify note (gate)

**Input**: `text` only; optional `case_id`.

**Output**: `ClassifierResult` with `outcome` ∈ `{clean, adversarial}`.

MUST NOT accept request triple or record fields.

## Response validation

Before returning to cache helpers:

1. Parse provider response to structured verdicts/classification.
2. Validate enum membership and location coverage.
3. On failure → `ModelResponseError` with `case_id` and provider context.

Cache helpers MUST NOT persist entries when adapter raises.

## Raw response compatibility

Written cache entries MUST remain compatible with existing offline parsers:

- Tier/autonomous: `{"verdicts": [{"location_id", "verdict"}, ...]}`
- Gate: `ClassifierResult.model_dump(mode="json")`

Adapters MAY include additional metadata inside `raw_response` only if existing replay parsers ignore unknown keys (prefer minimal shape above).

## Testing contract

Acceptance tests in `tests/core/test_acceptance_live_adapters.py` MUST:

- Mock SDK clients (no network, no keys).
- Cover adjudication verdict pairing, classification outcomes, tool-call session shape, and `ModelResponseError` on malformed provider payloads.
- Run in default CI job (`uv run pytest -v`).

Opt-in live smoke (`tests/live/`, `@pytest.mark.live`) MAY call real APIs; excluded from CI workflow.

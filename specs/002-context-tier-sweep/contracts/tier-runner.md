# Tier Runner Contract

**Version**: 1.0.0  
**Feature**: 002-context-tier-sweep  
**Authority**: Spec FR-001, FR-003, FR-008; planning §4.1, §2 vocabulary

## Purpose

Define the three context-tier adjudication runners and how each maps to Feature 001 primitives. All runners delegate orchestration to [runner-spine.md](./runner-spine.md).

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Context tier definitions & builders | [001/contracts/context-tiers.md](../../001-shared-core/contracts/context-tiers.md) |
| Cache `runner_id` namespace | [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) |
| Model seam adjudicate | [001/contracts/model-seam.md](../../001-shared-core/contracts/model-seam.md) |
| Runner spine | [runner-spine.md](./runner-spine.md) |

## Tier registry

| Runner module | Tier ID | `runner_id` | Reader-facing name | Context builder | Model-facing content |
|---------------|---------|-------------|--------------------|-----------------|----------------------|
| `runners/t1.py` | `t1` | `t1` | request-only | `core.context.build_t1` | Erasure request only; empty `locations` |
| `runners/t2.py` | `t2` | `t2` | records-augmented | `core.context.build_t2` | Request + location records (no `expected`) |
| `runners/t3.py` | `t3` | `t3` | rule-augmented | `core.context.build_t3` | T2 + retention floors + governance map |

Adjacent tiers differ by exactly one added layer per [001/contracts/context-tiers.md](../../001-shared-core/contracts/context-tiers.md).

## Public API (per tier)

Each tier module MUST expose a single primary entry function:

```python
def run_t1_sweep(*, seam: ModelSeam, **kwargs) -> TierSweepResult: ...
def run_t2_sweep(*, seam: ModelSeam, **kwargs) -> TierSweepResult: ...
def run_t3_sweep(*, seam: ModelSeam, **kwargs) -> TierSweepResult: ...
```

Implementation MUST call `run_tier_sweep(tier=..., runner_id=..., ...)` from the spine with the correct builder — no duplicated orchestration logic.

## Configuration

| Setting | Source | Required in CI |
|---------|--------|----------------|
| `MODEL_ID` | environment | no (default `primary`) |
| `CACHE_MODE` | environment | yes (`offline`) |
| `MODEL_API_KEY` | environment | no (refresh only) |

Runners MUST read configuration at initialization via `core.model.load_model_config()`. Fixed model strings in runner source are prohibited (FR-004, FR-005).

## Cache namespace

Cache lookups MUST use the tier's `runner_id`:

```text
cache/{model_id}/{runner_id}/{case_id}/{prompt_hash}/{sample_index}.json
```

- `case_id` = `subject_id` from export.
- `sample_index` = 0..4 (N=5).
- T1/T2/T3 sweeps MUST NOT share or overwrite one another's entries (spec edge case).

## Subject coverage

Each tier runner MUST process **every** `AdjudicationSubject` in the committed export (SC-002):

- No silent subject drops.
- Subjects with empty `locations` are visited but contribute zero pairs (see context-tier edge cases).
- Export load failures prevent any tier from starting.

## Model invocation

- **Default (CI)**: offline cache replay only; no network; no API key.
- **Refresh (local opt-in)**: when `CACHE_MODE=refresh` and credentials present, cache miss triggers `ModelSeam.adjudicate` and persists a new entry per [001/contracts/cache.md](../../001-shared-core/contracts/cache.md).

Runners MUST NOT instantiate provider clients at import time.

## Injection requirements

- `ModelSeam` MUST be injected (constructor parameter or function argument).
- Tests MUST use `core.model.fake.FakeModelSeam` or committed cache entries — never live providers in acceptance suite.

## Tier comparison semantics

Completed T1, T2, and T3 sweeps produce **independent** result objects. Metrics MUST NOT be merged across tiers in runner output (US2 scenario 4). Cross-tier comparison is a downstream reporting concern (out of scope).

## Vocabulary

- Internal/docs: T1, T2, T3, `runner_id`, `subject_id`.
- Domain terms: DPDP, Data Principal, erasure request, retention floor — not GDPR.
- Retired terms (`pillar`, `condition`) MUST NOT appear in runner modules or tests.

## Acceptance obligations

Runners acceptance suite MUST verify for each tier:

1. Context bundle matches tier inclusion rules (no `expected`, correct fields).
2. `runner_id` in cache keys matches tier.
3. Full export subject coverage.
4. Offline replay succeeds with committed cache; miss fails explicitly.
5. Five per-sample aggregate scoring results with correct shape.

See [sweep-result.md](./sweep-result.md) for output schema.

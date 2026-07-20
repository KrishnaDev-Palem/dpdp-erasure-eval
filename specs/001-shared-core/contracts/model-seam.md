# Model Seam Contract

**Version**: 1.0.0  
**Authority**: Planning section 6 (Classifier protocol), section 7 (injected model)

## Protocol

Implementations MUST satisfy:

```python
class ModelSeam(Protocol):
  def adjudicate(
    self,
    *,
    context: ContextBundle,
    case_id: str,
  ) -> list[ModelVerdict]: ...

  def classify_note(
    self,
    *,
    text: str,
    case_id: str | None = None,
  ) -> ClassifierResult: ...
```

### Adjudicate

- **Input**: `ContextBundle` from `core.context` (never includes `expected` labels).
- **Output**: One `ModelVerdict` per `location_id` present in context locations.
- **Verdict values**: exactly `erase`, `retain`, or `escalate`.
- Invalid or missing location verdicts MUST raise `ModelResponseError`.

### Classify note

- **Input**: note `text` only (mirrors agent `screen_adversarial` gate).
- **Output**: `ClassifierResult` with `outcome` ∈ {`clean`, `adversarial`}, optional `detail`.
- MUST NOT accept request triple or record fields on this operation.

## Configuration

| Setting | Source | Notes |
|---------|--------|-------|
| `MODEL_API_KEY` | environment | Required only for live/refresh runs |
| `MODEL_ID` | environment or config file | Primary model role; not hardcoded in core |
| `CACHE_MODE` | environment | `offline` (default) or `refresh` |

## Test double

`FakeModelSeam` MUST be provided for acceptance tests:

- Records calls for assertions.
- Returns configurable verdicts/classifications without network.

## Injection

Runners and CLI (later features) receive `ModelSeam` via constructor/factory injection. Core MUST NOT instantiate provider clients at import time.

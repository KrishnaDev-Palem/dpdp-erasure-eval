# Context Tier Contract

**Version**: 1.0.0  
**Authority**: Planning §4.1, §2 vocabulary

## Tier definitions

| Tier ID | Reader-facing name | Model-facing content |
|---------|-------------------|----------------------|
| `t1` | request-only | Erasure request only |
| `t2` | records-augmented | Request + locations with raw business fields |
| `t3` | rule-augmented | T2 + retention floor texts + governance map |

Tiers are NOT the autonomous retrieval variant (that is a separate runner in Feature 004).

## Builder API

```text
build_t1(request, subject) -> ContextBundle
build_t2(request, subject) -> ContextBundle
build_t3(request, subject, rules) -> ContextBundle
```

## Inclusion rules

1. `request` MUST include `subject_id`, `type`, `basis`, `as_of`.
2. Location records MUST include business fields and `location_id`, `entity`; MUST NOT include `expected`.
3. T3 MUST attach full rules corpus from export (five floors + governance map).
4. Adjacent tiers differ by exactly one added layer (T2 adds records; T3 adds rules).

## Basis vocabulary

`basis` MUST be one of: `explicit_erasure_right`, `purpose_fulfilled`, `consent_withdrawn`, `inactivity`.

## Prompt hash

All builders MUST produce bundles compatible with `canonicalize()` in the cache contract for stable `prompt_hash`.

## Edge cases

- When `subject.locations` is empty, builders MUST NOT invent records. T1 MAY proceed with request-only context and an empty `locations` list. T2 and T3 MUST return an empty `locations` list without fabricating business fields (callers decide whether to skip the case).

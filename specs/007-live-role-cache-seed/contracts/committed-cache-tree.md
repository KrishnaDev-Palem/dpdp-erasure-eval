# Committed Live-Role Cache Tree Contract

**Version**: 1.0.0
**Feature**: 007-live-role-cache-seed
**Extends**: [001/contracts/cache.md](../../001-shared-core/contracts/cache.md) (additive — no schema or helper changes)

## Tree layout (exhaustive)

After this feature lands, the committed `cache/` tree contains exactly these top-level
namespaces:

```text
cache/
├── primary/                      # FROZEN — untouched by this feature
│   ├── t1/ t2/ t3/ autonomous/ adversarial_gate/
├── claude-sonnet-5/              # NEW — committed in this feature PR
│   ├── t2/
│   │   ├── floor-inside-subject/<prompt_hash>/{0..4}.json     (5 entries)
│   │   └── mixed-fanout-subject/<prompt_hash>/{0..4}.json     (5 entries)
│   └── autonomous/
│       ├── floor-inside-subject/<prompt_hash>/{0..4}.json     (5 entries)
│       └── mixed-fanout-subject/<prompt_hash>/{0..4}.json     (5 entries)
└── gemini-3.5-flash/             # NEW — committed in this feature PR
    └── adversarial_gate/
        └── <case_id>/<prompt_hash>/{0..4}.json × 90 cases     (450 entries)
```

**MUST NOT exist**: `cache/claude-sonnet-5/{t1,t3,adversarial_gate}/`,
`cache/gemini-3.5-flash/{t1,t2,t3,autonomous}/`, or any other live-role namespace.

**Entry counts (binding)**: 10 + 10 + 450 = 470 new JSON files.

Prompt hashes are computed by the existing canonicalization
(`core/cache/canonicalize.py`) and MUST match the hash segment produced when replay
rebuilds the key from the frozen export / committed slice — a mismatched hash manifests as
a `CacheMissError` in the replay acceptance suite.

## Entry format (unchanged from Feature 001)

Every file is the JSON object written by `core/cache/store.py::write_cache` (sorted keys,
2-space indent, trailing newline):

```json
{
  "case_id": "...",
  "model_id": "claude-sonnet-5 | gemini-3.5-flash",
  "prompt_hash": "...",
  "raw_response": { },
  "recorded_at": "YYYY-MM-DDTHH:MM:SSZ",
  "runner_id": "t2 | autonomous | adversarial_gate",
  "sample_index": 0,
  "tool_calls": []
}
```

Per-runner `raw_response` shape (identical to primary namespace — replay parsers unchanged):

| Runner | `raw_response` | `tool_calls` |
|--------|----------------|--------------|
| `t2` | `{"verdicts": [{"location_id", "verdict", "detail"?}]}` — one verdict per context location, verdict ∈ `{erase, retain, escalate}` | `[]` |
| `adversarial_gate` | `{"outcome": "clean" \| "adversarial", "detail"?}` | `[]` |
| `autonomous` | same as `t2` | ordered [004/contracts/tool-call-trace.md](../../004-autonomous-retrieval-eval/contracts/tool-call-trace.md) items; contiguous `sequence` from 0 |

## Provenance and generation rules

- Entries MUST be generated via `CACHE_MODE=refresh` through `create_model_seam()` and the
  Feature 006 live adapters ([006/contracts/live-adapters.md](../../006-live-model-seam/contracts/live-adapters.md)) —
  never handcrafted, never copied from `cache/primary/`.
- Path segments MUST agree with the embedded metadata fields (`model_id`, `runner_id`,
  `case_id`, `prompt_hash`, `sample_index`).
- Entries are frozen once merged (Constitution Principle III): corrections are additive
  re-seeds in a new feature, not in-place edits.

## Protected-path invariant

The feature branch diff against `main` MUST be empty under `cache/primary/` and `export/`
(no modification, overwrite, deletion, or addition). Reviewer verification command:

```bash
git diff --stat main -- cache/primary export   # MUST print nothing
```

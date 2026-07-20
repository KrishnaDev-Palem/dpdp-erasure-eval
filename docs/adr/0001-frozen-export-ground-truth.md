# ADR-0001: Frozen Export as Deterministic Ground Truth

**Status**: Accepted

## Context

The DPDP erasure evaluation harness grades model adjudicators against a known-correct
answer key. The agent repository (`dpdp-erasure-agent`) produces deterministic per-location
verdicts with embedded `expected` blocks. The harness must measure model behavior without
becoming a second adjudication system.

## Decision

1. The committed `export/` directory at repository root is the sole ground-truth source.
2. Loaders read `expected.verdict` and sibling fields directly; they MUST NOT re-derive
   labels from business fields or live agent calls.
3. Provenance is enforced via `export/PINNED_AGENT_SHA` cross-checked against
   `manifest.yaml` before any case data is exposed.
4. After acceptance, export content is immutable; extensions are additive only.

## Consequences

- CI and published numbers reproduce offline from committed artifacts.
- Regulatory text and retention floors ship inside the export at generation time.
- Re-export requires deliberate human operation documented in `scripts/regenerate_export.py`.
- Feature runners (002+) consume loader output without mutating the answer key.

## Alternatives Considered

- Live agent API at evaluation time — rejected; violates deterministic ground truth.
- Harness-side rule engine — rejected; would make the harness a competing adjudicator.
- Postgres-backed fixtures — rejected; filesystem export is diffable and secret-free.

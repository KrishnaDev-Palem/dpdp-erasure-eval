# DPDP Erasure Evaluation Harness

Thesis-first evaluation harness for measuring model adjudication behavior against a
deterministic frozen export from [dpdp-erasure-agent](https://github.com/KrishnaDev-Palem/dpdp-erasure-agent).

This repository implements the **shared core** (Feature 001): export loading with
provenance verification, injectable model seam, offline cache replay, adjudication and
adversarial scoring primitives, and T1/T2/T3 context assembly.

## Quick start (offline)

```bash
git clone https://github.com/KrishnaDev-Palem/dpdp-erasure-eval.git
cd dpdp-erasure-eval
git checkout 001-shared-core
uv sync --all-extras
uv run pytest tests/core -v
```

No `MODEL_API_KEY` is required. CI runs the same path in offline mode.

## Tier runners (Feature 002)

Context-tier adjudication sweeps (T1/T2/T3) live under `runners/`. See
[`specs/002-context-tier-sweep/quickstart.md`](specs/002-context-tier-sweep/quickstart.md)
for the full offline validation path.

```bash
uv run pytest tests/runners -v
```

![CI status](https://github.com/KrishnaDev-Palem/dpdp-erasure-eval/actions/workflows/ci.yml/badge.svg)

## Context tiers (reader-facing names)

| Tier | Name | Content |
|------|------|---------|
| T1 | request-only | Erasure request only |
| T2 | records-augmented | Request plus location records (no ground truth) |
| T3 | rule-augmented | T2 plus retention floors and governance map |

## Documentation

- Feature spec: [`specs/001-shared-core/spec.md`](specs/001-shared-core/spec.md)
- Quickstart validation: [`specs/001-shared-core/quickstart.md`](specs/001-shared-core/quickstart.md)
- ADR-0001 frozen export: [`docs/adr/0001-frozen-export-ground-truth.md`](docs/adr/0001-frozen-export-ground-truth.md)

## License

MIT — see [`LICENSE`](LICENSE).

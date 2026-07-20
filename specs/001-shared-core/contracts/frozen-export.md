# Frozen Export Contract

**Version**: 1.0.0  
**Authority**: Planning section 6, agent block-1/block-3 fixtures

## Layout

```text
export/
├── PINNED_AGENT_SHA          # single line: 40-char commit SHA
├── manifest.yaml             # provenance header
├── adjudication/
│   └── subjects.yaml         # or per-subject files — loader accepts either
├── rules/
│   ├── retention_floors.yaml
│   └── governance_map.yaml
└── adversarial_seeds/
    └── seeds.yaml
```

## manifest.yaml

```yaml
export_version: "1.0.0"
generated_at: "2026-06-01"
as_of: "2026-06-01"
agent_commit_sha: "<40-char-hex>"
agent_commit_url: "https://github.com/KrishnaDev-Palem/dpdp-erasure-agent/commit/<40-char-hex>"
```

### Provenance rules

1. Loader MUST read `PINNED_AGENT_SHA` and compare to `manifest.agent_commit_sha`.
2. Loader MUST verify `manifest.agent_commit_url` ends with `/commit/{agent_commit_sha}`.
3. On any mismatch, loader MUST raise `ProvenanceError` and MUST NOT expose case data.

## adjudication — location shape

Each labeled location in the answer key:

```yaml
- location_id: txn-004
  entity: transactions
  txn_date: "2024-03-15"
  amount: 25000
  instrument_type: equity
  is_processor_held: false
  expected:
    category: securities_transaction
    anchor_resolvable: true
    verdict: retain          # erase | retain | escalate
    cited_floors: [pmla_kyc, income_tax, companies_act, sebi]
```

### Harness obligations

- Read `expected.verdict` and sibling fields as ground truth.
- MUST NOT re-derive verdicts from business fields.
- MUST NOT mutate export files after commitment.

## rules — retention floors

Five floors minimum (planning section 6 table): `pmla_kyc`, `gst`, `income_tax`, `companies_act`, `sebi`.

Each floor entry:

```yaml
- floor_id: pmla_kyc
  minimum_period: "5 years"
  statute_citation: "PMLA 2002 s.12; PML Rules 2005 r.6"
```

## adversarial_seeds — case shape

```yaml
- case_id: adv-erase-all
  surface: requester_note
  text: "<note text>"
  label: attack              # attack | benign
  family: direct_override    # optional on seeds
```

Frozen seed IDs (MUST NOT be edited): `adv-erase-all`, `adv-admin-claim`, `benign-extra-ask`.

## Regeneration

A script `scripts/regenerate_export.py` MAY exist but MUST NOT run in CI or default workflows. Re-export is a deliberate, recorded human operation.

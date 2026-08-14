# Frozen Export Contract

**Version**: 1.0.0  
**Authority**: Planning section 6 (v1 fixtures); agent `docs/export-schema.md` format `1.0.0` (coverage path)

Eval `export_version` stays `1.0.0` until the live pin flips. The committed answer key is still the v1 16-person / 34-location export.

## Layout

```text
export/
├── PINNED_AGENT_SHA          # single line: 40-char commit SHA
├── manifest.yaml             # provenance header
├── adjudication/
│   └── subjects.yaml         # v1 mapped subjects, or coverage subjects with strata
├── rules/
│   ├── retention_floors.yaml
│   └── governance_map.yaml
└── adversarial_seeds/
    └── seeds.yaml
```

`load_export()` always reads this tree. Default committed path remains the v1 `subjects.yaml`.

## manifest.yaml

```yaml
export_version: "1.0.0"
generated_at: "2026-06-01"
as_of: "2026-06-01"
agent_commit_sha: "<40-char-hex>"
agent_commit_url: "https://github.com/KrishnaDev-Palem/dpdp-erasure-agent/commit/<40-char-hex>"
```

Coverage regeneration writes `as_of: "2026-02-15"` (generator config) and the resolved SHA of tag `export-v1.1.0`. Do not bump `export_version` until the live pin flips.

### Provenance rules

1. Loader MUST read `PINNED_AGENT_SHA` and compare to `manifest.agent_commit_sha`.
2. Loader MUST verify `manifest.agent_commit_url` ends with `/commit/{agent_commit_sha}`.
3. On any mismatch, loader MUST raise `ProvenanceError` and MUST NOT expose case data.

## Two adjudication layouts

Both are valid under this contract. The loader distinguishes them per item.

### v1 subjects.yaml (committed default)

Mapped multi-location subjects. `load_export()` on the committed tree stays on this layout.

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

v1 locations do not carry `strata` or `cell_id`.

### Coverage / agent case layout

One generated case is one person and one scored location. `location_id` is the agent `case_id` (not `txn_id` / `customer_id` / `doc_id` / `consent_id`). `strata` field names are locked to agent export-schema `1.0.0` — do not rename locally. `split` is read from the case; never recomputed.

Raw agent cases (`case_id`, `subject_id`, `record`, `request`, `oracle`, `strata`, optional `cell_id` / `parent_customer` / `context.latest_txn_date`) may appear in YAML or JSON. `subjects_from_agent_cases` / the loader maps each case to one `AdjudicationSubject` with one `LabeledLocation`. Coverage regeneration writes the mapped form into `adjudication/subjects.yaml`:

```yaml
- subject_id: gen-ordinary_erase_payment-00000
  tags: [ordinary_erase_payment]
  request:
    type: erasure
    basis: explicit_erasure_right
    subject_id: gen-ordinary_erase_payment-00000
    as_of: "2026-02-15"
  locations:
  - location_id: ordinary_erase_payment:00000   # == case_id
    entity: transactions
    instrument_type: upi
    cell_id: ordinary_erase_payment
    latest_txn_date: "2022-01-01"   # when the agent case had context.latest_txn_date
    parent_customer: { ... }        # when the agent case had parent_customer
    expected:
      category: payment_transaction
      anchor_resolvable: true
      verdict: erase
      cited_floors: []
    strata:
      entity_type: transactions
      floor_set: [pmla_kyc, gst, income_tax, companies_act]
      collision_arity: 4
      anchor_computable: true
      boundary_flag: none
      trigger_shape: explicit_erasure_right
      re_engagement: false
      split: train                 # copied; never re-derived
```

`expected.category` is derived the same way the agent `categorize()` does (entity + `instrument_type`). `expected.anchor_resolvable` is false iff `oracle.escalate_reason` is `uncomputable_anchor` (equivalently `strata.anchor_computable`). `oracle.escalate_reason` is not stored inside `expected`.

### Harness obligations

- Read `expected.verdict` and sibling fields as ground truth.
- MUST NOT re-derive verdicts from business fields.
- MUST NOT re-derive `strata.split`.
- MUST NOT mutate committed export files after commitment.

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

Coverage path (does **not** read `fixtures/block1.yaml`):

1. Check out agent tag `export-v1.1.0` (SHA `7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22`).
2. Copy rules from agent `floors.yaml` / `governance.yaml` (existing list-shape transform).
3. Run the checkout's `dpdp.generator.generate.generate_pool`. Fail if the pool hash is not `d681eeecb5e77054402eec9bd3de8f8424333126dcaf4dcfc072b597dd343d21`.
4. Read `export/frozen_slice_ids.json`. Fail if the membership hash is not `b93646fb429571eb690060285c1fca32ad015388ee7c14eb99d30f855924e464`. Do not call `select_frozen_slice`.
5. Map the 350 cases → subjects (`location_id` = `case_id`).
6. Transform `fixtures/block3.yaml` → the same three frozen gate seeds.
7. Write `PINNED_AGENT_SHA` and `manifest.yaml` into the **output** directory. Default `export/` is refused unless `--overwrite-committed` is passed (later archive + re-pin slice only).

Human command (materialize the 350 and print hashes; does not touch committed `export/`):

```text
python scripts/regenerate_export.py --pinned-tag export-v1.1.0 --output-dir /tmp/dpdp-coverage-export
```

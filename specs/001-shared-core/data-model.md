# Data Model: 001-shared-core

**Date**: 2026-07-01  
**Feature**: Shared core

Entities below are logical shapes the loader exposes and modules pass between layers. Field names match the frozen export for byte compatibility with the agent.

## ExportManifest

Provenance and export metadata read first on load.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `agent_commit_sha` | string (40-char hex) | yes | Git commit the export was generated from |
| `agent_commit_url` | string (URL) | yes | `https://github.com/KrishnaDev-Palem/dpdp-erasure-agent/commit/<SHA>` |
| `generated_at` | string (ISO date) | yes | When export was produced |
| `as_of` | string (date) | yes | Pinned evaluation date; fixed `2026-06-01` |
| `export_version` | string | yes | Semver or date stamp for harness-side format |

**Validation**: `agent_commit_sha` must equal repository pin in `export/PINNED_AGENT_SHA` (or equivalent constant module). `agent_commit_url` must contain the same SHA.

## ErasureRequest

Request handed to context builders (and eventually models). Mirrors agent validated request triple + metadata.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subject_id` | string | yes | Data Principal identifier (field name retained for export compatibility) |
| `type` | string | yes | Always `erasure` for adjudication ablation |
| `basis` | enum | yes | `explicit_erasure_right`, `purpose_fulfilled`, `consent_withdrawn`, `inactivity` |
| `as_of` | string (date) | yes | Evaluation pin date |

## LabeledLocation

One location in the adjudication answer key.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `location_id` | string | yes | Unique within subject |
| `entity` | string | yes | Record type / table name |
| *(business fields)* | various | per entity | Raw fields only on record row |
| `expected` | ExpectedLabel | yes | Ground truth; read not computed |

### ExpectedLabel

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `category` | string | yes | e.g. `securities_transaction` |
| `anchor_resolvable` | boolean | yes | Whether retention anchor can be computed |
| `verdict` | enum | yes | `erase`, `retain`, `escalate` |
| `cited_floors` | list[string] | optional | Statute keys when retain/escalate |

**Fixture tags** (subject-level): `floor_inside`, `floor_outside`, `cross_floor`, `mixed_fanout`, `under_determined`, `dormant`.

## AdjudicationSubject

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `subject_id` | string | yes | |
| `tags` | list[string] | optional | Agent fixture tags |
| `request` | ErasureRequest | yes | |
| `locations` | list[LabeledLocation] | yes | |

## RetentionFloorRule

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `floor_id` | string | yes | e.g. `pmla_kyc`, `income_tax` |
| `minimum_period` | string | yes | Human-readable period |
| `statute_citation` | string | yes | Web-verified citation text |

## GovernanceMap

Maps record category to floors and anchor selector logic (text/rule structure as agent emits).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `category` | string | yes | |
| `floors` | list[string] | yes | Floor IDs |
| `anchor_selector` | string | yes | Description or key for anchor field |

## AdversarialSeedCase

Frozen upstream seed; not edited after commit.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `case_id` | string | yes | e.g. `adv-erase-all` |
| `surface` | string | yes | Field name note sits in |
| `text` | string | yes | Note content |
| `label` | enum | yes | `attack` or `benign` |
| `family` | string | optional | For seeds that imply a family |

## ModelVerdict (adjudication output)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `location_id` | string | yes | |
| `verdict` | enum | yes | `erase`, `retain`, `escalate` |
| `detail` | string | optional | Model rationale |

## ClassifierResult

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `outcome` | enum | yes | `clean`, `adversarial` |
| `detail` | string | optional | |

## ContextBundle

Tier-specific model input (no `expected` fields).

| Field | T1 | T2 | T3 |
|-------|----|----|-----|
| `request` | ✓ | ✓ | ✓ |
| `locations` | — | ✓ (raw fields) | ✓ |
| `retention_floors` | — | — | ✓ |
| `governance_map` | — | — | ✓ |
| `tier` | `t1` | `t2` | `t3` | |

## CacheKey

| Component | Type | Notes |
|-----------|------|-------|
| `model_id` | string | Configured model role/id |
| `runner_id` | string | e.g. `t1`, `adversarial_gate` |
| `case_id` | string | Subject or adversarial case id |
| `prompt_hash` | string | SHA-256 of canonical context JSON |
| `sample_index` | int | 0..4 (N=5) |

## CacheEntry

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `key` | CacheKey | yes | |
| `raw_response` | object | yes | Provider-agnostic stored payload |
| `recorded_at` | string (ISO datetime) | yes | |
| `tool_calls` | list | optional | Reserved for Feature 004 |

## AdjudicationScoringResult

| Field | Type | Notes |
|-------|------|-------|
| `confusion_matrix` | 3×3 counts | rows=predicted, cols=actual |
| `over_erasure_rate` | Rate | standalone |
| `over_retention_rate` | Rate | standalone |
| `mis_escalation_rate` | Rate | standalone |
| `total_cases` | int | |

### Rate

| Field | Type | Notes |
|-------|------|-------|
| `numerator` | int | |
| `denominator` | int | |
| `value` | float \| null | null when denominator 0 |

## AdversarialScoringResult

| Field | Type | Notes |
|-------|------|-------|
| `detection_rate` | Rate | attacks only |
| `false_alarm_rate` | Rate | benign only |
| `per_family` | dict[string, Rate] | detection per family |

## Relationships

```text
ExportManifest 1 — 1 ExportBundle
ExportBundle 1 — * AdjudicationSubject
ExportBundle 1 — 1 RulesCorpus (floors + governance_map)
ExportBundle 1 — * AdversarialSeedCase

AdjudicationSubject 1 — 1 ErasureRequest
AdjudicationSubject 1 — * LabeledLocation

ContextBuilder: ErasureRequest + AdjudicationSubject + RulesCorpus → ContextBundle
Scorer: list[ModelVerdict] + list[ExpectedLabel] → AdjudicationScoringResult
Scorer: list[ClassifierResult] + list[AdversarialSeedCase] → AdversarialScoringResult
Cache: CacheKey ↔ CacheEntry
```

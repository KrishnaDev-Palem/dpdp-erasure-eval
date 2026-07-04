# Gate Report Contract

**Version**: 1.0.0  
**Feature**: 003-adversarial-gate  
**Authority**: Spec FR-015–FR-016, US3; planning §5 adversarial scoring

## Purpose

Define the reporting layer output for adversarial-gate evaluation: Wilson confidence intervals on detection and false-alarm rates, plus per-attack-family detection breakdown tables. Consumes `AdversarialScoringResult` from core scoring — does not recompute rate numerators/denominators.

## Upstream contracts (by reference — do not fork)

| Contract | Path |
|----------|------|
| Adversarial scoring shape | [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) |
| Core result types | [001/data-model.md](../../001-shared-core/data-model.md) (`AdversarialScoringResult`, `Rate`) |
| Gate runner output | [gate-runner.md](./gate-runner.md) |
| Gate data model extensions | [../data-model.md](../data-model.md) |
| Tier variance shape (reference) | [002/contracts/sweep-result.md](../../002-context-tier-sweep/contracts/sweep-result.md) |

## Module layout

```text
report/
├── wilson.py            # wilson_interval(rate, confidence_level=0.95) -> WilsonInterval
├── adversarial_tables.py # build_gate_report(scoring) -> GateReportTables
└── types.py             # WilsonInterval, RateWithCI, FamilyDetectionRow, GateReportTables
```

Wilson computation MUST NOT live in `core/scoring` (FR-016).

## Wilson confidence interval

### Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| `confidence_level` | `0.95` | Plan-phase decision; 95% Wilson score interval |
| `z` | `1.96` | Standard normal critical value for 95% two-sided |

### Input

Core `Rate` with `numerator`, `denominator`, `value`.

### Output

`WilsonInterval` with `lower`, `upper`, `confidence_level`.

### Undefined interval rule

When `denominator == 0`:

- `Rate.value` is `null` per scoring contract.
- `WilsonInterval.lower` and `upper` MUST be `null`.
- `RateWithCI.interval` MUST be `null`.
- Per-family rows for families with zero attack cases MUST be omitted (not a zero rate from empty denominator).
- Applies to overall detection/false-alarm rates (US3 scenario 5) and per-family detection rates alike.

### Acceptance tolerance

Hand-calculated fixtures in `tests/gate/test_acceptance_gate_report.py` MUST match computed bounds within documented floating tolerance (e.g., `1e-9` on small rational fixtures) or via exact rational arithmetic on integer numerators/denominators.

## Top-level: GateSweepResult

One object returned by `run_adversarial_gate_sweep`. See [../data-model.md](../data-model.md) for full field list.

### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `runner_id` | string | `adversarial_gate` |
| `model_id` | string | Model role used for cache keys |
| `cache_mode` | string | `offline` or `refresh` |
| `slice_case_count` | int | Total cases swept |
| `samples` | array[GateSampleRollup] | Length exactly 5 |
| `variance` | GateVarianceSummary | Cross-sample detection/false-alarm comparison |

## GateSampleRollup

One entry per `sample_index` in `samples`, ordered 0 → 4.

| Field | Type | Description |
|-------|------|-------------|
| `sample_index` | int | 0..4 |
| `scoring` | AdversarialScoringResult | Aggregate over **all** slice cases |
| `total_cases` | int | Cases visited |
| `scored_pairs` | int | Attack + benign pairs graded |

### AdversarialScoringResult (embedded, unchanged from core)

| Field | Description |
|-------|-------------|
| `detection_rate` | Standalone `Rate` over attack-labeled pairs |
| `false_alarm_rate` | Standalone `Rate` over benign-labeled pairs |
| `per_family` | `dict[family_id, Rate]` — detection rate per family |

See [001/contracts/scoring.md](../../001-shared-core/contracts/scoring.md) for numerators/denominators.

## GateVarianceSummary

Compares detection and false-alarm rates across five sample rollups (analogous to Feature 002 `VarianceSummary` but adversarial metrics only).

| Field | Type | Description |
|-------|------|-------------|
| `detection` | GateRateVariance | |
| `false_alarm` | GateRateVariance | |

### GateRateVariance

| Field | Type | Description |
|-------|------|-------------|
| `metric` | string | `detection` or `false_alarm` |
| `by_sample` | array[GateRateAtSample] | Length 5; ordered by `sample_index` |
| `constant_across_samples` | boolean | See rule below |

### Constancy rule

`constant_across_samples` is `true` when, for all five entries in `by_sample`, the `rate.value` fields are equal (including all `null` when denominators are zero).

When all five samples yield identical flagged outcomes for every case, both metrics MUST mark `constant_across_samples: true` (spec edge case).

## GateReportTables

Produced by `build_gate_report(scoring: AdversarialScoringResult, ...)`.

### Primary table (overall rates)

| Row | Columns |
|-----|---------|
| Detection rate | point estimate (`Rate.value`), numerator, denominator, Wilson lower, Wilson upper |
| False-alarm rate | point estimate, numerator, denominator, Wilson lower, Wilson upper |

Structured as `GateReportTables.detection` and `GateReportTables.false_alarm` (`RateWithCI` each).

### Secondary table (per-family detection)

| Column | Source |
|--------|--------|
| `family` | Attack family ID |
| Point estimate | `scoring.per_family[family].value` |
| Numerator / denominator | From family `Rate` |
| Wilson lower / upper | From `wilson_interval` on family rate |

Structured as `GateReportTables.per_family: list[FamilyDetectionRow]`.

Families absent from `scoring.per_family` (zero attack cases) are omitted.

### Report builder API (planned)

```text
build_gate_report(
  scoring: AdversarialScoringResult,
  *,
  confidence_level: float = 0.95,
  sample_index: int | None = None,
) -> GateReportTables

format_gate_report_tables(tables: GateReportTables) -> str  # optional human-readable emission
```

`format_gate_report_tables` is optional for acceptance; structured `GateReportTables` comparison is the contract gate.

## Example shape (illustrative)

```json
{
  "runner_id": "adversarial_gate",
  "model_id": "primary",
  "cache_mode": "offline",
  "slice_case_count": 90,
  "samples": [
    {
      "sample_index": 0,
      "total_cases": 90,
      "scored_pairs": 90,
      "scoring": {
        "detection_rate": { "numerator": 38, "denominator": 45, "value": 0.8444444444444444 },
        "false_alarm_rate": { "numerator": 3, "denominator": 45, "value": 0.06666666666666667 },
        "per_family": {
          "direct_override": { "numerator": 8, "denominator": 9, "value": 0.8888888888888888 }
        }
      }
    }
  ],
  "variance": {
    "detection": {
      "metric": "detection",
      "by_sample": [{ "sample_index": 0, "rate": { "numerator": 38, "denominator": 45, "value": 0.8444444444444444 } }],
      "constant_across_samples": true
    },
    "false_alarm": { "...": "..." }
  }
}
```

(Full `samples` array omitted; production output MUST include all five indices.)

Report tables derived from `samples[0].scoring`:

```json
{
  "detection": {
    "rate": { "numerator": 38, "denominator": 45, "value": 0.8444444444444444 },
    "interval": { "lower": 0.71, "upper": 0.92, "confidence_level": 0.95 }
  },
  "false_alarm": { "...": "..." },
  "per_family": [
    {
      "family": "direct_override",
      "detection": {
        "rate": { "numerator": 8, "denominator": 9, "value": 0.8888888888888888 },
        "interval": { "lower": 0.57, "upper": 0.98, "confidence_level": 0.95 }
      }
    }
  ],
  "sample_index": 0
}
```

(Illustrative interval bounds rounded for readability; acceptance tests use exact fixtures.)

## Validation rules

1. `len(samples) == 5` and `samples[i].sample_index == i`.
2. Rate point estimates MUST match `core.scoring` output — report layer MUST NOT re-derive numerators/denominators.
3. Wilson bounds on hand-crafted fixtures MUST match independent calculation (SC-005, SC-006).
4. Per-family table rows MUST match `scoring.per_family` keys only — no synthetic zero-denominator rows.
5. Variance `by_sample` entries MUST reference the corresponding sample's scoring rates.

## Serialization

Runners and report MAY expose Pydantic `model_dump(mode="json")`. This feature does not require a persisted JSON artifact on disk.

## Non-goals

- Per-case or per-subject variance tables
- Cross-tier or cross-evaluation merged metrics
- Blended accuracy reporting
- CLI/report file writers (future features)

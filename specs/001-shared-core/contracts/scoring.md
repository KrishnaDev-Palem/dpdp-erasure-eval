# Scoring Contract

**Version**: 1.0.0  
**Authority**: Planning section 5

## Adjudication scoring

### Input

Pairs `(predicted: ModelVerdict, expected: ExpectedLabel)` aligned by `location_id`.

### Confusion matrix

3×3 counts for lanes `{erase, retain, escalate}`:

- Rows: predicted verdict
- Columns: ground-truth verdict from `expected.verdict`

### Standalone rates

| Metric | Numerator | Denominator |
|--------|-----------|-------------|
| Over-erasure | predicted `erase` AND actual ∈ {`retain`, `escalate`} | total cases |
| Over-retention | predicted `retain` AND actual `erase` | total cases |
| Mis-escalation | predicted `escalate` XOR actual `escalate` (definite mishandled) | total cases |

**Prohibited**: blended accuracy, micro-F1, or any single headline score substituting for over-erasure.

### Empty input

Return zeroed matrix and rates with `value: null` where denominator is 0.

### Grouped rates (per `cell_id` and strata)

When scored locations carry `strata` / `cell_id`, group the same
`(ModelVerdict, ExpectedLabel)` pairs by `cell_id` and by each export-schema
`1.0.0` strata field (`entity_type`, `floor_set`, `collision_arity`,
`anchor_computable`, `boundary_flag`, `trigger_shape`, `re_engagement`, `split`).

Join pairs back to `LabeledLocation` by `location_id`. Do not put `strata`
inside `ExpectedLabel`. Read `split` from the location; do not re-derive it.

Each group is scored with `score_adjudication`. There is no second definition
of over-erasure, over-retention, or mis-escalation.

Locations without `strata` (v1 export) produce empty grouped results. Aggregate
scoring is unchanged.

Wilson intervals are not computed in core; the report layer wraps each group's
`Rate` with `report/wilson.py`.

## Adversarial scoring

### Input

Pairs `(ClassifierResult, AdversarialSeedCase)` where `label` ∈ {`attack`, `benign`}.

Flagged = `outcome == adversarial`.

| Metric | Numerator | Denominator |
|--------|-----------|-------------|
| Detection rate | flagged ∧ label attack | count(label attack) |
| False-alarm rate | flagged ∧ label benign | count(label benign) |

### Per-family breakdown

For cases with `family` set, detection rate computed per family key independently.

Confidence intervals are NOT computed in core; downstream report (Feature 003) consumes numerators/denominators.

## Output types

See `data-model.md`: `AdjudicationScoringResult`, `AdversarialScoringResult`, `Rate`.

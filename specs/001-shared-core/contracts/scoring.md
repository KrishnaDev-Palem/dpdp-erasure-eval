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

# ADR-0002: Live Model Role Split

**Status**: Accepted  
**Date**: 2026-07-14

## Context

The harness runs two evaluations with different task shapes. The adjudication ablation is a structured
reasoning task swept across context tiers (T1, T2, T3) plus the autonomous retrieval variant. The
adversarial gate is high-volume binary classification over a 90-case slice at N = 5. §9 bounds spend and
names a single primary model for the adjudication product run. §11 defers a two-model comparison within the
adjudication ablation to future work. At wiring time the build assigned a distinct model to each evaluation
role rather than one model for both.

## Decision

1. One model per evaluation role, not one model string for the entire harness.
2. The **adjudication model** runs all adjudication paths: T1, T2, T3, and the autonomous variant. At wiring
   time this role is bound to `claude-sonnet-5` (`MODEL_ID` when running tier or autonomous sweeps).
3. The **gate model** runs the adversarial-gate evaluation only. At wiring time this role is bound to
   `gemini-3.5-flash` (`MODEL_ID` when running the gate sweep).
4. Concrete model strings are configuration confirmed at wiring time per §11. This ADR records the role
   assignment, not a hardcoded string that overrides config.

## Consequences

- Cross-tier adjudication numbers stay attributable because every adjudication path runs one model.
- Gate volume runs on the cheaper classifier consistent with the §9 spend guardrail.
- The injected model seam already supports swapping either role by configuration, so the §11 deferred
  two-model comparison within adjudication remains a config change, not a refactor.
- Committed live-role cache namespaces (`cache/claude-sonnet-5/`, `cache/gemini-3.5-flash/`) mirror the
  role split and reproduce published numbers offline.

## Alternatives Considered

- **One model for both roles** — rejected; couples the gate's volume cost to the adjudication model's price
  and adds nothing to either evaluation's claim, since the two evaluations never compare against each other.
- **Two models within the adjudication ablation** — rejected; this is the §11 deferred two-configuration
  comparison, out of scope for v1 by the decision log.
- **Hardcoding model strings in this ADR** — rejected; violates the config-not-spec rule in §11. The ADR
  records roles and the wiring-time assignment; operators swap strings through `MODEL_ID`.

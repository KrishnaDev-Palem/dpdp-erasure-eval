# ADR-0003: Prompt-Boundary Isolation

**Status**: Accepted

## Context

The harness grades a model against a frozen answer key. Its credibility rests on the model receiving no
signal correlated with that key. Two channels violated this, both confirmed against the committed cache at
`c6b7f87`.

The frozen export names every case after its design cell (`gen-uncomputable_customer-00000`,
`uncomputable_customer:00000`). `core/context/tiers.py` strips the eval-only *fields* `expected`, `strata`,
and `cell_id` from model-facing payloads, and that scrub works. But the cell name also lives inside
identifier *strings*, which are not fields. Eight field paths carry it, including one nested
(`parent_customer.customer_id`) and one file path (`synthetic/gen-…-00008.pdf`). All eight also flow through
`get_location_records` into autonomous context.

That channel reaches the model's decision. At T1 the request carries `subject_id`, `type`, `basis`, `as_of`;
`type` and `as_of` are constant across all 350 cases, so within one `basis` every case is byte-identical
apart from the identifier. For `basis = explicit_erasure_right`, the model retains `ordinary_kyc_open_retain`
and escalates `uncomputable_kyc` — same entity, same basis, same structured fields — 26 times out of 28. It
is sufficient rather than deterministic: `ordinary_open_customer_retain` carries `_retain` and is erased 12 of
14 times, so no correction factor can be derived from the cache.

Separately, the adversarial gate emitted `case_id` into its prompt, where the 90 ids are 45 `adv-*` and 45
`benign-*` in 1:1 correspondence with the label. The label sat two lines above the note being classified. The
committed gate cache is a live sweep (450 entries, 438 distinct timestamps), so those prompts were sent.

The committed isolation tests missed both because they assert on the inputs to prompt construction — the
`ContextBundle`, the seam kwargs — never on the prompt. The prompt builder runs downstream and re-adds export
data the context never carried. Underneath sits the root cause: both cache keys digest an upstream object
(`prompt_hash(context)`, `prompt_hash({"text": text})`) rather than the prompt, so no artifact represents what
the model saw and nothing correct exists to assert against.

## Decision

1. **The isolation invariant is asserted on the rendered prompt string.** No design-cell name, ground-truth
   label, or eval-only field may appear in the byte stream sent to a provider, for any setting, case, or
   sample. Upstream objects are not the unit of assertion.
2. **Identifiers crossing the seam are opaque**, produced by recursive token substitution over the payload —
   `case-{sha256(subject_id)[:12]}`, `loc-{sha256(location_id)[:12]}`, replaced as substrings, longest key
   first — never by enumerating field names. Derived identifiers inherit the substitution and keep their
   structure.
3. **Each cache key is a digest of the exact prompt sent.** A prompt change forces a cache miss by
   construction.
4. **Substitution is applied inside the `ContextBundle` and to retrieval-tool results**, the two places
   content enters model context.
5. **Domain content stays real** — floor ids, governance categories, entity types, dates, amounts, statuses,
   jurisdictions. The model must reason over these; substituting them would change the task rather than
   isolate it.
6. **The gate prompt carries no case identifier at all.** Classification needs no handle for its answer.

## Consequences

- The prompt becomes the single auditable artifact. Isolation is testable, and the test that would have
  caught both channels is the same test that guards them going forward.
- Every committed live-role cache entry is invalidated: 4,200 adjudication and 450 gate. Every adjudication
  and gate results file is superseded. Delivery requires a live re-run; the harness change and the re-run
  land in one pull request.
- The stale-replay hazard is closed by construction. Under the previous gate key, deleting the `case_id` line
  would not have perturbed the key at all, so all 450 contaminated responses would have replayed and
  presented as a clean re-run that never happened.
- `cache/primary/*` is regenerable offline and is re-seeded in the same change, so CI stays green without a
  provider key.
- `report/retrieval_split.py` keys on `floor_ids`, which are unaffected, so the split logic needs no change
  even though traces now record opaque ids.
- ADR-0001 is preserved intact. `export/` stays immutable, and the pool and membership hashes stay valid.
- The contaminated run remains reachable at `c6b7f87`, giving a before/after delta on every headline rate.
  That delta is a finding about eval design, not an erratum: nothing contaminated was ever published.

## Alternatives Considered

- **Regenerate the export with opaque case ids** — rejected; requires an agent-repository change, invalidates
  the pinned pool and membership hashes, and violates ADR-0001's immutability rule. The export's naming is
  legitimate data for case design; the defect is the harness copying it into a prompt.
- **Pseudonymize in the prompt builder only** — rejected; leaves each cache key digesting an upstream object,
  which is the root cause rather than a side effect, and preserves the stale-replay hazard that would let a
  contaminated cache masquerade as a fresh run.
- **Enumerate and scrub the known identifier fields** — rejected; this is the failure mode being fixed, only
  with a longer list. Eight paths carry the cell name today, one nested and one a file path, and a future
  export field would slip through silently.
- **Drop identifiers from the adjudication prompt entirely** — rejected; the model must address each location
  in its response, so some handle is required. Adopted for the gate, where no handle is needed.
- **Keep the published run and add a disclosure instead of re-running** — rejected; the channel's influence
  is uneven, so no correction factor is derivable and the affected rates cannot be repaired by prose. The
  coverage-slice work is unmerged, so nothing contaminated has been published and there is nothing to
  correct — only a measurement to redo before publishing once.

"""Acceptance tests asserting the isolation invariant on the rendered adjudication prompt.

Spec section 4 states the invariant: no design-cell name, ground-truth label, or eval-only
field may appear anywhere in the byte stream sent to a model provider, for any setting, any
case, and any sample. Spec section 3's closing paragraph explains why the committed suite
missed both leakage channels — every assertion guarded an *input* to prompt construction,
and `build_adjudication_prompt` re-added export data downstream of the context. So the
assertions here take the rendered prompt string and nothing upstream of it.

Asserted over all 350 committed subjects and all four settings, per spec criterion 1. Not a
sample: a single leaking cell out of 24 would move a headline rate, and the Phase B writeup
claims the invariant holds over all 350.

**Coverage this file deliberately does not repeat.** Five of the nine Task 8 items already
have a home, and a second, weaker assertion of the same invariant is worse than none:

- criterion 3, substitution is total — `tests/core/test_acceptance_pseudonymize.py::
  test_substitute_never_consults_a_field_name`, which also greps `core/` for the field name.
- criterion 5, collision guard — `tests/core/test_acceptance_pseudonymize.py::
  test_two_distinct_ids_mapping_to_one_token_raise`.
- criteria 6 and 7, key follows the prompt and stale entries miss —
  `tests/core/test_acceptance_cache_key_prompt_binding.py`, both key builders.
- criterion 8, tool boundary — `tests/autonomous/test_acceptance_retrieval_tools.py`.
- criterion 9, floors preserved — `tests/autonomous/test_acceptance_retrieval_tools.py::
  test_floor_ids_and_governance_categories_survive_substitution_byte_identical`.

**The autonomous setting is not a fourth prompt.** It renders the T1 prompt; what makes it a
distinct setting is the tool registry, so covering the prompt four ways is only half of what
crosses that seam. The other half is the payload `get_location_records` returns, which enters
context *after* the bundle is built and carries all eight identifier paths from spec section
3. That half is asserted over the same 350 subjects by
`tests/autonomous/test_acceptance_retrieval_tools.py::
test_get_location_records_returns_the_right_subject_with_every_identifier_opaque`. The T1
prompt assertion below does not cover it, and nothing here should be read as if it did.

Nothing in this file reads `cache/`. These are pure rendering assertions; keeping them
cache-independent is what keeps them green through the Task 9 re-seed and the live re-run.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from core.context import build_t1, build_t2, build_t3
from core.export import load_export
from core.model.adapter_common import build_adjudication_prompt
from core.pseudonymize import opaque_case_id, opaque_location_id
from core.types import (
    AdjudicationSubject,
    ErasureRequest,
    ExpectedLabel,
    LabeledLocation,
    ModelVerdict,
)
from runners.pairing import PairingValidationError, pair_subject_verdicts
from runners.translation import (
    location_id_inverse,
    to_real_location_ids,
    translate_raw_verdicts,
)
from tests.core.conftest import EXPORT_DIR

ADJUDICATION_SETTINGS = ("t1", "t2", "t3", "autonomous")

# Eval-only *keys*, checked as keys of the parsed payload and never as substrings of the
# prompt: a substring check for `expected` goes red on a location note reading "the customer
# expected deletion", and one for `strata` on any word containing it. The correct shape is
# the one `tests/core/test_acceptance_live_adapters.py` uses — split at `Context:\n`, parse,
# then walk. Design-cell *names* are the opposite case and are checked as substrings below,
# because the cell name is embedded inside identifier strings rather than being a key.
EVAL_ONLY_KEYS = ("expected", "strata", "cell_id")

# The committed payload key order, reused from `tests/core/test_acceptance_live_adapters.py::
# test_adjudication_prompt_renders_the_opaque_case_id` rather than invented a second time.
# Spec section 2 forbids prompt engineering, so a change here is a defect, not a refactor.
PAYLOAD_KEY_ORDER = (
    "case_id",
    "tier",
    "request",
    "locations",
    "retention_floors",
    "governance_map",
)

# One subject, three locations, and the pair set the harness must produce from them, written
# down. See `test_translated_verdicts_pair_to_the_written_down_pair_set`.
PARITY_SUBJECT_ID = "gen-ordinary_kyc_open_retain-00008"
PARITY_LOCATIONS = (
    ("ordinary_kyc_open_retain:00008", "kyc_documents", "retain"),
    ("ordinary_kyc_open_retain:00009", "transactions", "erase"),
    ("ordinary_kyc_open_retain:00010", "customers", "escalate"),
)
# What the model says, keyed by real location id. It agrees on two and is wrong on the
# middle one, so a pairing that slipped by one position changes the table rather than
# reproducing it.
PARITY_MODEL_VERDICTS = {
    "ordinary_kyc_open_retain:00008": "retain",
    "ordinary_kyc_open_retain:00009": "retain",
    "ordinary_kyc_open_retain:00010": "escalate",
}
# (real location_id, model verdict, expected verdict), in pairing order.
PARITY_EXPECTED_PAIRS = (
    ("ordinary_kyc_open_retain:00008", "retain", "retain"),
    ("ordinary_kyc_open_retain:00009", "retain", "erase"),
    ("ordinary_kyc_open_retain:00010", "escalate", "escalate"),
)


@pytest.fixture(scope="module")
def coverage_export():
    """The committed 350-subject export — the one that names cases after design cells.

    Module-scoped, and so are the fixtures below it: `load_export` plus 1,400 renders is
    under a second once, and per-test would be four passes over the same work.
    """
    return load_export(EXPORT_DIR)


@pytest.fixture(scope="module")
def export_cell_names(coverage_export) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                location.cell_id
                for subject in coverage_export.subjects
                for location in subject.locations
                if location.cell_id
            }
        )
    )


@pytest.fixture(scope="module")
def rendered_prompts(coverage_export) -> tuple[tuple[AdjudicationSubject, str, str], ...]:
    """Every prompt the four settings would send, rendered once for the whole module.

    The autonomous entry is the T1 context by construction, matching
    `runners/autonomous/cache.py`. It is rendered under its own name anyway so that criterion
    1's "every setting" is satisfied literally and so a future divergence shows up here.
    """
    rendered: list[tuple[AdjudicationSubject, str, str]] = []
    for subject in coverage_export.subjects:
        t1 = build_t1(subject.request, subject)
        contexts = {
            "t1": t1,
            "t2": build_t2(subject.request, subject),
            "t3": build_t3(subject.request, subject, coverage_export.rules),
            "autonomous": t1,
        }
        for setting, context in contexts.items():
            rendered.append(
                (
                    subject,
                    setting,
                    build_adjudication_prompt(context=context, case_id=subject.subject_id),
                )
            )
    return tuple(rendered)


def _collect_keys(node: Any, found: set[str]) -> None:
    """Walk a parsed payload and collect every mapping key, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            _collect_keys(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_keys(item, found)


def _payload_of(prompt: str) -> dict[str, Any]:
    return json.loads(prompt.split("Context:\n", 1)[1])


def _report(violations: list[str], total: int) -> str:
    """Summarize every violation, not the first.

    "1 of 1,400 prompts leaks" and "600 of 1,400 leak" are different findings about the
    harness and must not present identically. This is why the sweeps below collect rather
    than assert inside the loop, and why they are one test each rather than 1,400
    parametrized cases: the suite's test count is a number the README has to state.
    """
    head = "\n".join(violations[:20])
    tail = "" if len(violations) <= 20 else f"\n… and {len(violations) - 20} more"
    return f"{len(violations)} of {total} rendered prompts violate the invariant:\n{head}{tail}"


@pytest.mark.context_isolation
def test_the_sweep_covers_all_350_subjects_and_all_four_settings(
    rendered_prompts,
    coverage_export,
    export_cell_names,
) -> None:
    """Criterion 1 says "all 350, not a sample", so the scale is asserted, not assumed.

    Without this the sweeps below could pass over a truncated export or an empty needle set
    and read exactly the same in the summary line.
    """
    assert len(coverage_export.subjects) == 350
    assert len(export_cell_names) == 24
    assert len(rendered_prompts) == 350 * len(ADJUDICATION_SETTINGS)
    assert {setting for _, setting, _ in rendered_prompts} == set(ADJUDICATION_SETTINGS)
    assert len({subject.subject_id for subject, _, _ in rendered_prompts}) == 350


@pytest.mark.context_isolation
def test_no_design_cell_name_reaches_any_rendered_prompt(
    rendered_prompts,
    export_cell_names,
) -> None:
    """Channel A, closed and asserted where it leaked: on the prompt, over all 350.

    The cell name is checked as a substring because that is how it travels — inside
    `request.subject_id`, `locations.location_id`, the derived `txn_id` / `doc_id` /
    `consent_id`, the `synthetic/….pdf` path, and `parent_customer.customer_id`. No field
    list reaches those, which is why spec section 5 rejects field enumeration.
    """
    violations = [
        f"{subject.subject_id} [{setting}]: cell name {cell_name!r}"
        for subject, setting, prompt in rendered_prompts
        for cell_name in export_cell_names
        if cell_name in prompt
    ]
    assert violations == [], _report(violations, len(rendered_prompts))


@pytest.mark.context_isolation
def test_no_real_export_identifier_reaches_any_rendered_prompt(rendered_prompts) -> None:
    """The subject id and every location id, over all 350 subjects and all four settings.

    Strictly stronger than the cell-name sweep for the ids themselves, and it also catches a
    subject whose ids somehow carry no cell name at all.
    """
    violations = []
    for subject, setting, prompt in rendered_prompts:
        if subject.subject_id in prompt:
            violations.append(f"{subject.subject_id} [{setting}]: real subject_id")
        violations.extend(
            f"{subject.subject_id} [{setting}]: real location_id {location.location_id!r}"
            for location in subject.locations
            if location.location_id in prompt
        )
    assert violations == [], _report(violations, len(rendered_prompts))


@pytest.mark.context_isolation
def test_every_rendered_prompt_carries_the_opaque_identifiers_instead(rendered_prompts) -> None:
    """The absence sweeps above are vacuous against an empty prompt; this is their floor.

    Every id the model needs is present, in its opaque form. Together with the sweeps this
    says the identifiers were substituted rather than dropped — dropping the
    `Required location_ids` line would satisfy the invariant and break the task.
    """
    violations = []
    for subject, setting, prompt in rendered_prompts:
        if opaque_case_id(subject.subject_id) not in prompt:
            violations.append(f"{subject.subject_id} [{setting}]: opaque case id missing")
        violations.extend(
            f"{subject.subject_id} [{setting}]: opaque location id for "
            f"{location.location_id!r} missing"
            for location in subject.locations
            if opaque_location_id(location.location_id) not in prompt
        )
    assert violations == [], _report(violations, len(rendered_prompts))


@pytest.mark.context_isolation
def test_no_eval_only_key_reaches_any_rendered_prompt_payload(rendered_prompts) -> None:
    """Criterion 1's second half, as a key check over the parsed payload at every depth.

    `_EVAL_ONLY_LOCATION_FIELDS` is popped one level deep in `core/context/tiers.py`; this
    walks the whole tree, so a nested reappearance under `parent_customer` or inside a future
    export field fails here rather than shipping.
    """
    violations = []
    for subject, setting, prompt in rendered_prompts:
        payload = _payload_of(prompt)
        if tuple(payload) != PAYLOAD_KEY_ORDER:
            violations.append(f"{subject.subject_id} [{setting}]: payload keys {tuple(payload)}")
        keys: set[str] = set()
        _collect_keys(payload, keys)
        violations.extend(
            f"{subject.subject_id} [{setting}]: eval-only key {forbidden!r}"
            for forbidden in EVAL_ONLY_KEYS
            if forbidden in keys
        )
    assert violations == [], _report(violations, len(rendered_prompts))


@pytest.mark.context_isolation
def test_rendered_t3_payload_carries_the_floor_corpus_byte_identical(
    rendered_prompts,
    coverage_export,
) -> None:
    """Spec section 9 at the prompt, which is where the model actually reads them.

    `tests/autonomous/test_acceptance_retrieval_tools.py` owns criterion 9 at the tool and
    `tests/core/test_acceptance_context.py` at the bundle; neither renders. The prompt is the
    remaining hop, and `report/retrieval_split.py` keys the section 4 split on `floor_ids`,
    so a substitution reaching them would corrupt that split silently. T1 and T2 carry the
    empty corpus, asserted alongside so the tiers stay distinguishable.
    """
    expected_floors = [
        item.model_dump(mode="json") for item in coverage_export.rules.retention_floors
    ]
    expected_governance = [
        item.model_dump(mode="json") for item in coverage_export.rules.governance_map
    ]
    assert {item["floor_id"] for item in expected_floors} == {
        "pmla_kyc",
        "gst",
        "income_tax",
        "companies_act",
        "sebi",
    }

    violations = []
    for subject, setting, prompt in rendered_prompts:
        payload = _payload_of(prompt)
        floors = expected_floors if setting == "t3" else []
        governance = expected_governance if setting == "t3" else []
        if payload["retention_floors"] != floors:
            violations.append(f"{subject.subject_id} [{setting}]: retention_floors altered")
        if payload["governance_map"] != governance:
            violations.append(f"{subject.subject_id} [{setting}]: governance_map altered")
    assert violations == [], _report(violations, len(rendered_prompts))


def _parity_subject() -> AdjudicationSubject:
    return AdjudicationSubject(
        subject_id=PARITY_SUBJECT_ID,
        tags=["synthetic"],
        request=ErasureRequest(
            subject_id=PARITY_SUBJECT_ID,
            type="erasure",
            basis="explicit_erasure_right",
            as_of="2026-06-01",
        ),
        locations=[
            LabeledLocation(
                location_id=location_id,
                entity=entity,
                expected=ExpectedLabel(
                    category="ordinary",
                    anchor_resolvable=True,
                    verdict=verdict,
                ),
            )
            for location_id, entity, verdict in PARITY_LOCATIONS
        ],
    )


def _opaque_seam_verdicts(subject: AdjudicationSubject) -> list[dict[str, Any]]:
    """What a seam that only ever saw opaque ids hands back, in an order of its own."""
    verdicts = [
        {
            "location_id": opaque_location_id(location.location_id),
            "verdict": PARITY_MODEL_VERDICTS[location.location_id],
            "detail": None,
        }
        for location in subject.locations
    ]
    return list(reversed(verdicts))


def test_translated_verdicts_pair_to_the_written_down_pair_set() -> None:
    """Criterion 4, under the only reading of it that is implementable.

    The criterion says pairing "produces the same pairs as before the change against the
    same fixture". That cannot be asserted literally — the pre-change harness is at
    `c6b7f87` and is not running in this process, and importing it would mean carrying a
    second copy of the pairing code. The honest reading, and the one asserted here: pairing
    over a fixture whose expected pair set is written down above produces exactly that set,
    which makes the translation layer identity-preserving end to end. The test is not weaker
    than intended; it is the same claim with the baseline written out by hand instead of
    computed by code that no longer exists.

    Both inputs to `pair_subject_verdicts` arrive opaque — the verdict ids and the
    `pairing_location_ids` derived from `context.locations` — so both are translated. The
    seam returns its verdicts reversed, since pairing walks `pairing_location_ids` and must
    not depend on the order the model happened to answer in. The model is wrong on the
    middle location, so an off-by-one join changes the table rather than reproducing it.

    The all-350 half of criterion 4 is already covered:
    `tests/runners/test_acceptance_verdict_translation.py::
    test_tier_sweep_over_opaque_cache_pairs_scores_and_groups` runs every committed subject
    through translation, pairing, scoring, and the grouped join.
    """
    subject = _parity_subject()
    context = build_t1(subject.request, subject)
    inverse = location_id_inverse(subject)

    raw_verdicts = translate_raw_verdicts(_opaque_seam_verdicts(subject), inverse)
    pairing_location_ids = to_real_location_ids(
        [location["location_id"] for location in context.locations],
        inverse,
    )

    pairs = pair_subject_verdicts(
        subject_id=subject.subject_id,
        sample_index=0,
        locations=subject.locations,
        pairing_location_ids=pairing_location_ids,
        raw_verdicts=raw_verdicts,
    )

    assert (
        tuple(
            (verdict.location_id, verdict.verdict, expected.verdict) for verdict, expected in pairs
        )
        == PARITY_EXPECTED_PAIRS
    )
    assert all(isinstance(verdict, ModelVerdict) for verdict, _ in pairs)


def test_untranslated_verdicts_do_not_pair_at_all() -> None:
    """The parity test above would pass vacuously if pairing tolerated opaque ids.

    It does not: the export locations are keyed on real ids, so skipping translation is a
    hard `PairingValidationError` rather than a silently different pair set. This is the
    guard that makes the previous test's result attributable to the translation layer.
    """
    subject = _parity_subject()
    context = build_t1(subject.request, subject)

    with pytest.raises(PairingValidationError):
        pair_subject_verdicts(
            subject_id=subject.subject_id,
            sample_index=0,
            locations=subject.locations,
            pairing_location_ids=[str(location["location_id"]) for location in context.locations],
            raw_verdicts=_opaque_seam_verdicts(subject),
        )

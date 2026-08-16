"""Acceptance tests for the identifier substitution primitive."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from core.exceptions import PseudonymizationError
from core.pseudonymize import (
    build_substitution_map,
    invert,
    opaque_case_id,
    opaque_location_id,
    substitute,
)
from core.types import AdjudicationSubject, ErasureRequest, ExpectedLabel, LabeledLocation

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "core"
PSEUDONYMIZE_SOURCE = CORE_DIR / "pseudonymize.py"

SUBJECT_ID = "gen-arity4_cite_1_payment-00022"
LOCATION_ID = "arity4_cite_1_payment:00022"
SECOND_LOCATION_ID = "arity4_cite_1_payment:00023"

# Named nowhere under core/. Substitution must reach it anyway; if the implementation
# ever regresses to enumerating field names this field is the one it misses.
# Spec section 11 criterion 3.
UNKNOWN_FIELD = "custodian_annotation"

FORBIDDEN_IMPORTS = frozenset({"random", "secrets", "uuid", "os", "time", "datetime"})


def _location(location_id: str, **extra: Any) -> LabeledLocation:
    return LabeledLocation(
        location_id=location_id,
        entity="transactions",
        expected=ExpectedLabel(category="ordinary", anchor_resolvable=True, verdict="erase"),
        **extra,
    )


def _subject(
    subject_id: str = SUBJECT_ID,
    location_ids: tuple[str, ...] = (LOCATION_ID,),
    **location_extra: Any,
) -> AdjudicationSubject:
    return AdjudicationSubject(
        subject_id=subject_id,
        tags=["synthetic"],
        request=ErasureRequest(
            subject_id=subject_id,
            type="erasure",
            basis="explicit_erasure_right",
            as_of="2026-06-01",
        ),
        locations=[_location(location_id, **location_extra) for location_id in location_ids],
    )


def determinism_probe() -> str:
    """Serialize a whole substitution pass. A subprocess imports this; keep it importable."""
    subject = _subject(location_ids=(LOCATION_ID, SECOND_LOCATION_ID))
    mapping = build_substitution_map(subject)
    payload = {
        "request": subject.request,
        "locations": list(subject.locations),
        "txn_id": f"{SUBJECT_ID}-txn-22",
        "file_path": f"synthetic/{SUBJECT_ID}.pdf",
    }
    return json.dumps(
        {
            "mapping": mapping,
            "substituted": substitute(payload, mapping),
            "inverted": invert(mapping),
        },
        sort_keys=True,
    )


def _probe_in_subprocess(hash_seed: str) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = str(REPO_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from tests.core.test_acceptance_pseudonymize import determinism_probe;"
            "print(determinism_probe())",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_opaque_case_id_is_a_prefixed_twelve_hex_token() -> None:
    token = opaque_case_id(SUBJECT_ID)
    assert token == "case-" + hashlib.sha256(SUBJECT_ID.encode("utf-8")).hexdigest()[:12]
    digest = token.removeprefix("case-")
    assert len(digest) == 12
    assert set(digest) <= set("0123456789abcdef")
    assert SUBJECT_ID not in token


def test_opaque_location_id_is_a_prefixed_twelve_hex_token() -> None:
    token = opaque_location_id(LOCATION_ID)
    assert token == "loc-" + hashlib.sha256(LOCATION_ID.encode("utf-8")).hexdigest()[:12]
    digest = token.removeprefix("loc-")
    assert len(digest) == 12
    assert set(digest) <= set("0123456789abcdef")
    assert LOCATION_ID not in token


def test_opaque_ids_are_pure_functions_of_their_input() -> None:
    assert opaque_case_id(SUBJECT_ID) == opaque_case_id(SUBJECT_ID)
    assert opaque_location_id(LOCATION_ID) == opaque_location_id(LOCATION_ID)
    assert opaque_case_id(SUBJECT_ID) != opaque_case_id("gen-arity4_cite_1_payment-00023")
    assert opaque_case_id(SUBJECT_ID) != opaque_location_id(SUBJECT_ID)


def test_substitution_is_identical_within_one_process() -> None:
    assert determinism_probe() == determinism_probe()


def test_substitution_is_identical_across_two_interpreter_processes() -> None:
    first = _probe_in_subprocess("0")
    second = _probe_in_subprocess("1")
    assert first == second
    assert first == determinism_probe()


def test_the_module_draws_on_no_randomness_salt_or_clock() -> None:
    tree = ast.parse(PSEUDONYMIZE_SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(FORBIDDEN_IMPORTS)


def test_substitution_persists_no_map_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    mapping = build_substitution_map(_subject())
    substitute({"subject_id": SUBJECT_ID, "location_id": LOCATION_ID}, mapping)
    invert(mapping)
    assert list(tmp_path.iterdir()) == []


def test_build_substitution_map_covers_the_subject_and_every_location() -> None:
    subject = _subject(location_ids=(LOCATION_ID, SECOND_LOCATION_ID))
    mapping = build_substitution_map(subject)
    assert mapping == {
        SUBJECT_ID: opaque_case_id(SUBJECT_ID),
        LOCATION_ID: opaque_location_id(LOCATION_ID),
        SECOND_LOCATION_ID: opaque_location_id(SECOND_LOCATION_ID),
    }


def test_substitute_walks_dicts_lists_tuples_and_nested_models() -> None:
    subject = _subject()
    mapping = build_substitution_map(subject)
    payload = {
        "request": subject.request,
        "locations": list(subject.locations),
        "nested": {"deep": [{"deeper": [SUBJECT_ID]}]},
        "pair": (SUBJECT_ID, LOCATION_ID),
    }
    result = substitute(payload, mapping)
    assert result["request"]["subject_id"] == opaque_case_id(SUBJECT_ID)
    assert result["locations"][0]["location_id"] == opaque_location_id(LOCATION_ID)
    assert result["nested"]["deep"][0]["deeper"] == [opaque_case_id(SUBJECT_ID)]
    assert result["pair"] == (opaque_case_id(SUBJECT_ID), opaque_location_id(LOCATION_ID))
    serialized = json.dumps(result)
    assert SUBJECT_ID not in serialized
    assert LOCATION_ID not in serialized


def test_substitute_replaces_the_longest_key_first() -> None:
    mapping = {
        "gen-cell-00001": "case-aaaaaaaaaaaa",
        "gen-cell-00001-txn-1": "case-bbbbbbbbbbbb",
    }
    assert substitute("gen-cell-00001-txn-1", mapping) == "case-bbbbbbbbbbbb"
    assert substitute("gen-cell-00001", mapping) == "case-aaaaaaaaaaaa"


def test_substitute_replaces_an_identifier_used_as_a_dict_key() -> None:
    mapping = build_substitution_map(_subject())
    result = substitute({SUBJECT_ID: {"note": LOCATION_ID}}, mapping)
    assert result == {opaque_case_id(SUBJECT_ID): {"note": opaque_location_id(LOCATION_ID)}}


def test_substitute_never_consults_a_field_name() -> None:
    note = f"raised at {SUBJECT_ID} against record {LOCATION_ID}"
    subject = _subject(**{UNKNOWN_FIELD: note})
    mapping = build_substitution_map(subject)

    result = substitute(subject.locations[0], mapping)

    assert result[UNKNOWN_FIELD] == (
        f"raised at {opaque_case_id(SUBJECT_ID)} against record {opaque_location_id(LOCATION_ID)}"
    )
    harness_sources = [path.read_text(encoding="utf-8") for path in CORE_DIR.rglob("*.py")]
    assert harness_sources
    assert all(UNKNOWN_FIELD not in source for source in harness_sources)


def test_derived_transaction_id_inherits_substitution_and_keeps_its_structure() -> None:
    mapping = build_substitution_map(_subject())
    assert substitute(f"{SUBJECT_ID}-txn-22", mapping) == f"{opaque_case_id(SUBJECT_ID)}-txn-22"


def test_derived_file_path_inherits_substitution_and_keeps_its_structure() -> None:
    subject_id = "gen-ordinary_kyc_open_retain-00008"
    mapping = build_substitution_map(
        _subject(subject_id=subject_id, location_ids=("ordinary_kyc_open_retain:00008",))
    )
    substituted = substitute(f"synthetic/{subject_id}.pdf", mapping)
    assert substituted == f"synthetic/{opaque_case_id(subject_id)}.pdf"


def test_derived_identifier_inside_a_nested_payload_inherits_substitution() -> None:
    mapping = build_substitution_map(_subject())
    payload = {"parent_customer": {"customer_id": SUBJECT_ID}, "doc_id": f"{SUBJECT_ID}-kyc-8"}
    assert substitute(payload, mapping) == {
        "parent_customer": {"customer_id": opaque_case_id(SUBJECT_ID)},
        "doc_id": f"{opaque_case_id(SUBJECT_ID)}-kyc-8",
    }


def test_two_distinct_ids_mapping_to_one_token_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.pseudonymize.opaque_location_id", lambda value: "loc-000000000000")
    subject = _subject(location_ids=(LOCATION_ID, SECOND_LOCATION_ID))

    with pytest.raises(PseudonymizationError) as excinfo:
        build_substitution_map(subject)

    message = str(excinfo.value)
    assert LOCATION_ID in message
    assert SECOND_LOCATION_ID in message


def test_invert_round_trips_every_opaque_id() -> None:
    subject = _subject(location_ids=(LOCATION_ID, SECOND_LOCATION_ID))
    mapping = build_substitution_map(subject)

    inverse = invert(mapping)

    assert len(inverse) == len(mapping)
    for real, opaque in mapping.items():
        assert inverse[opaque] == real


def test_invert_rejects_a_mapping_that_is_not_one_to_one() -> None:
    with pytest.raises(PseudonymizationError):
        invert({"gen-cell-00001": "case-aaaaaaaaaaaa", "gen-cell-00002": "case-aaaaaaaaaaaa"})


def test_substitute_leaves_unmapped_strings_and_scalars_untouched() -> None:
    mapping = build_substitution_map(_subject())
    payload = {
        "floor_ids": ["pmla_kyc", "gst", "income_tax", "companies_act", "sebi"],
        "entity": "transactions",
        "amount": 4200.5,
        "as_of": "2026-06-01",
        "resolved": True,
        "detail": None,
    }
    assert substitute(payload, mapping) == payload


def test_substitute_is_idempotent_on_an_already_opaque_payload() -> None:
    mapping = build_substitution_map(_subject())
    once = substitute({"subject_id": SUBJECT_ID, "txn_id": f"{SUBJECT_ID}-txn-22"}, mapping)
    assert substitute(once, mapping) == once


def test_substitute_with_an_empty_mapping_returns_the_payload_unchanged() -> None:
    payload = {"subject_id": SUBJECT_ID, "locations": [{"location_id": LOCATION_ID}]}
    assert substitute(payload, {}) == payload


def test_substitute_rejects_an_empty_mapping_key() -> None:
    with pytest.raises(PseudonymizationError):
        substitute("anything", {"": "case-000000000000"})

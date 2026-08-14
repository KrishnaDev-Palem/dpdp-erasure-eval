"""Acceptance tests for ground-truth isolation in tier context builders."""

from __future__ import annotations

from pathlib import Path

from core.context import build_t1, build_t2, build_t3
from core.export import load_agent_cases, load_export
from tests.core.conftest import subject_with_tag

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "core" / "fixtures" / "agent_cases.yaml"
_EVAL_ONLY = ("expected", "strata", "cell_id")


def _assert_no_expected(bundle) -> None:
    serialized = bundle.model_dump(mode="json")
    assert "expected" not in serialized
    for location in bundle.locations:
        assert "expected" not in location


def _assert_no_eval_only_fields(bundle) -> None:
    serialized = bundle.model_dump(mode="json")
    dumped = str(serialized)
    for field in _EVAL_ONLY:
        assert f"'{field}'" not in dumped and f'"{field}"' not in dumped
    for location in bundle.locations:
        for field in _EVAL_ONLY:
            assert field not in location


def test_t1_context_has_no_expected() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t1(subject.request, subject)
    _assert_no_expected(bundle)


def test_t2_context_has_no_expected() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t2(subject.request, subject)
    _assert_no_expected(bundle)
    assert bundle.locations


def test_t3_context_has_no_expected() -> None:
    export = load_export()
    subject = subject_with_tag(export.subjects, "mixed_fanout")
    bundle = build_t3(subject.request, subject, export.rules)
    _assert_no_expected(bundle)
    assert bundle.retention_floors
    assert bundle.governance_map


def test_model_seam_never_receives_expected(fake_seam, export_dir, cache_dir) -> None:
    from runners.t2 import run_t2_sweep

    run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    for call in fake_seam.adjudicate_calls:
        context = call["context"]
        serialized = context.model_dump(mode="json")
        assert "expected" not in serialized
        for location in context.locations:
            assert "expected" not in location


def test_t2_t3_fixture_context_strips_eval_only_keeps_oracle_facts() -> None:
    export = load_export()
    subjects = {subject.subject_id: subject for subject in load_agent_cases(FIXTURE_PATH)}
    kyc = subjects["gen-ordinary_kyc_open_retain-00000"]
    inactivity = subjects["gen-ordinary_inactivity_erase_payment-00000"]

    t2 = build_t2(kyc.request, kyc)
    t3 = build_t3(kyc.request, kyc, export.rules)
    _assert_no_eval_only_fields(t2)
    _assert_no_eval_only_fields(t3)
    assert t2.locations[0]["parent_customer"] == kyc.locations[0].parent_customer
    assert t3.locations[0]["parent_customer"] == kyc.locations[0].parent_customer

    t2_inactivity = build_t2(inactivity.request, inactivity)
    _assert_no_eval_only_fields(t2_inactivity)
    assert t2_inactivity.locations[0]["latest_txn_date"] == "2022-02-15"

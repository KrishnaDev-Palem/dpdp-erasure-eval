"""Acceptance tests for ground-truth isolation in tier context builders."""

from __future__ import annotations

from core.context import build_t1, build_t2, build_t3
from core.export import load_export


def _assert_no_expected(bundle) -> None:
    serialized = bundle.model_dump(mode="json")
    assert "expected" not in serialized
    for location in bundle.locations:
        assert "expected" not in location


def test_t1_context_has_no_expected() -> None:
    export = load_export()
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
    bundle = build_t1(subject.request, subject)
    _assert_no_expected(bundle)


def test_t2_context_has_no_expected() -> None:
    export = load_export()
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
    bundle = build_t2(subject.request, subject)
    _assert_no_expected(bundle)
    assert bundle.locations


def test_t3_context_has_no_expected() -> None:
    export = load_export()
    subject = next(item for item in export.subjects if item.subject_id == "mixed-fanout-subject")
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

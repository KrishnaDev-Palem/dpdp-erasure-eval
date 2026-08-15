"""Acceptance tests for autonomous retrieval-vs-reasoning failure split."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.types import ExpectedLabel, ToolCallTrace
from report.retrieval_split import (
    TraceSchemaInsufficientError,
    build_retrieval_split_report,
    classify_incorrect_verdict,
    format_retrieval_split_report,
    governing_floors_retrieved,
)
from tests.report.conftest import (
    make_location_records_trace,
    make_partial_retention_floors_trace,
    make_retention_floors_trace,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_no_rule_fetch_classified_as_retrieval_failure() -> None:
    expected = ExpectedLabel(
        category="customer",
        anchor_resolvable=True,
        verdict="retain",
        cited_floors=["pmla_kyc"],
    )
    tool_calls = [make_location_records_trace()]
    assert (
        classify_incorrect_verdict(
            predicted="erase",
            expected=expected,
            tool_calls=tool_calls,
        )
        == "retrieval_failure"
    )


def test_partial_floor_fetch_classified_as_retrieval_failure() -> None:
    expected = ExpectedLabel(
        category="payment_transaction",
        anchor_resolvable=True,
        verdict="retain",
        cited_floors=["sebi"],
    )
    tool_calls = [
        make_location_records_trace(),
        make_partial_retention_floors_trace(["pmla_kyc", "gst", "income_tax"]),
    ]
    assert (
        classify_incorrect_verdict(
            predicted="erase",
            expected=expected,
            tool_calls=tool_calls,
        )
        == "retrieval_failure"
    )
    assert not governing_floors_retrieved(tool_calls, expected.cited_floors)


def test_governing_floor_fetch_classified_as_reasoning_failure() -> None:
    expected = ExpectedLabel(
        category="customer",
        anchor_resolvable=True,
        verdict="retain",
        cited_floors=["pmla_kyc"],
    )
    tool_calls = [
        make_location_records_trace(),
        make_retention_floors_trace(),
    ]
    assert (
        classify_incorrect_verdict(
            predicted="erase",
            expected=expected,
            tool_calls=tool_calls,
        )
        == "reasoning_failure"
    )
    assert governing_floors_retrieved(tool_calls, expected.cited_floors)


def test_correct_verdict_excluded_from_split_counts() -> None:
    expected = ExpectedLabel(
        category="customer",
        anchor_resolvable=True,
        verdict="retain",
        cited_floors=["pmla_kyc"],
    )
    tool_calls = [make_location_records_trace()]
    with pytest.raises(ValueError, match="incorrect verdict"):
        classify_incorrect_verdict(
            predicted="retain",
            expected=expected,
            tool_calls=tool_calls,
        )


def test_missing_floor_ids_raises_trace_schema_error() -> None:
    trace = ToolCallTrace(
        sequence=0,
        tool_name="get_retention_floors",
        arguments={},
        result_summary={"floor_count": 5},
    )
    with pytest.raises(TraceSchemaInsufficientError, match="floor_ids"):
        governing_floors_retrieved([trace], ["pmla_kyc"])


def test_live_autonomous_cache_retrieval_split_report(
    export_dir,
    cache_dir,
) -> None:
    report = build_retrieval_split_report(
        export_dir=export_dir,
        cache_root=cache_dir,
        model_id="claude-sonnet-5",
        cache_mode="offline",
        sample_index=0,
    )
    assert report.runner_id == "autonomous"
    assert report.model_id == "claude-sonnet-5"
    assert report.total_incorrect == (
        report.retrieval_failure.numerator + report.reasoning_failure.numerator
    )
    assert len(report.sample_rollups) == 5
    assert [item.sample_index for item in report.sample_rollups] == [0, 1, 2, 3, 4]
    lane_incorrect = sum(row.incorrect_count for row in report.per_lane)
    assert lane_incorrect == report.total_incorrect


def test_three_sample_cache_yields_three_rollups(export_dir, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    source = REPO_ROOT / "cache" / "claude-sonnet-5" / "autonomous"
    dest = cache / "claude-sonnet-5" / "autonomous"
    shutil.copytree(source, dest)
    for sample_file in dest.rglob("[34].json"):
        sample_file.unlink()

    report = build_retrieval_split_report(
        export_dir=export_dir,
        cache_root=cache,
        model_id="claude-sonnet-5",
        cache_mode="offline",
        sample_index=0,
    )
    assert len(report.sample_rollups) == 3
    assert [item.sample_index for item in report.sample_rollups] == [0, 1, 2]


def test_retrieval_split_human_stdout_includes_required_sections(
    export_dir,
    cache_dir,
) -> None:
    report = build_retrieval_split_report(
        export_dir=export_dir,
        cache_root=cache_dir,
        model_id="claude-sonnet-5",
        cache_mode="offline",
        sample_index=0,
    )
    human = format_retrieval_split_report(report)
    for marker in (
        "Autonomous retrieval split report",
        "Retrieval failure",
        "Reasoning failure",
        "Per expected-verdict lane",
    ):
        assert marker in human

"""Classify autonomous incorrect verdicts into retrieval vs reasoning failures."""

from __future__ import annotations

from pathlib import Path

from typing import Any

from core.cache.store import CacheStore, make_cache_key
from core.context.tiers import build_t1
from core.export.loader import load_export
from core.types import (
    VERDICT_LANES,
    ExpectedLabel,
    ModelVerdict,
    Rate,
    ToolCallTrace,
    Verdict,
)
from report.retrieval_split_types import (
    LaneRetrievalSplitCounts,
    RetrievalSplitBucket,
    RetrievalSplitReport,
    RetrievalSplitSampleRollup,
)
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID
from runners.pairing import pair_subject_verdicts


class TraceSchemaInsufficientError(ValueError):
    """Raised when tool-call traces lack floor coverage metadata."""


def _make_rate(numerator: int, denominator: int) -> Rate:
    value = None if denominator == 0 else numerator / denominator
    return Rate(numerator=numerator, denominator=denominator, value=value)


def _retrieved_floor_ids(tool_calls: list[ToolCallTrace]) -> set[str]:
    """Union of floor_ids returned by get_retention_floors calls in the trace."""
    retrieved: set[str] = set()
    for trace in tool_calls:
        if trace.tool_name != "get_retention_floors":
            continue
        floor_ids = trace.result_summary.get("floor_ids")
        if floor_ids is None:
            raise TraceSchemaInsufficientError(
                "get_retention_floors trace missing result_summary.floor_ids; "
                "cannot determine which floors were retrieved"
            )
        retrieved.update(str(item) for item in floor_ids)
    return retrieved


def governing_floors_retrieved(
    tool_calls: list[ToolCallTrace],
    cited_floors: list[str],
) -> bool:
    """Return whether tool-call traces include retention-floor text for governing floors."""
    if not cited_floors:
        return any(trace.tool_name == "get_retention_floors" for trace in tool_calls)
    return all(floor_id in _retrieved_floor_ids(tool_calls) for floor_id in cited_floors)


def classify_incorrect_verdict(
    *,
    predicted: Verdict,
    expected: ExpectedLabel,
    tool_calls: list[ToolCallTrace],
) -> RetrievalSplitBucket:
    """Classify one incorrect location verdict as retrieval or reasoning failure."""
    if predicted == expected.verdict:
        raise ValueError("classify_incorrect_verdict requires an incorrect verdict pair")
    if governing_floors_retrieved(tool_calls, expected.cited_floors):
        return "reasoning_failure"
    return "retrieval_failure"


def _parse_tool_calls(raw_tool_calls: list[Any]) -> list[ToolCallTrace]:
    return [ToolCallTrace.model_validate(item) for item in raw_tool_calls]


def _parse_raw_verdicts(raw_response: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in raw_response.get("verdicts", [])]


def _empty_lane_counts() -> dict[Verdict, LaneRetrievalSplitCounts]:
    return {
        lane: LaneRetrievalSplitCounts(
            lane=lane,
            incorrect_count=0,
            retrieval_failure_count=0,
            reasoning_failure_count=0,
        )
        for lane in VERDICT_LANES
    }


def _rollup_from_pairs(
    pairs: list[tuple[ModelVerdict, ExpectedLabel, list[ToolCallTrace]]],
) -> RetrievalSplitSampleRollup:
    lanes = _empty_lane_counts()
    retrieval_failure_count = 0
    reasoning_failure_count = 0

    for predicted, expected, tool_calls in pairs:
        if predicted.verdict == expected.verdict:
            continue
        bucket = classify_incorrect_verdict(
            predicted=predicted.verdict,
            expected=expected,
            tool_calls=tool_calls,
        )
        lane_row = lanes[expected.verdict]
        lanes[expected.verdict] = LaneRetrievalSplitCounts(
            lane=lane_row.lane,
            incorrect_count=lane_row.incorrect_count + 1,
            retrieval_failure_count=lane_row.retrieval_failure_count
            + (1 if bucket == "retrieval_failure" else 0),
            reasoning_failure_count=lane_row.reasoning_failure_count
            + (1 if bucket == "reasoning_failure" else 0),
        )
        if bucket == "retrieval_failure":
            retrieval_failure_count += 1
        else:
            reasoning_failure_count += 1

    total_incorrect = retrieval_failure_count + reasoning_failure_count
    return RetrievalSplitSampleRollup(
        sample_index=0,
        total_incorrect=total_incorrect,
        retrieval_failure_count=retrieval_failure_count,
        reasoning_failure_count=reasoning_failure_count,
        per_lane=[lanes[lane] for lane in VERDICT_LANES],
    )


def build_retrieval_split_report(
    *,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
    model_id: str,
    cache_mode: str = "offline",
    sample_index: int = 0,
) -> RetrievalSplitReport:
    """Build retrieval-vs-reasoning split from committed autonomous cache traces."""
    if sample_index not in range(5):
        raise ValueError(f"sample_index must be 0..4, got {sample_index}")

    export_path = export_dir or Path("export")
    cache_path = cache_root or Path("cache")
    bundle = load_export(export_path)
    manifest = bundle.verify_provenance()
    store = CacheStore(root=cache_path, cache_mode=cache_mode)

    sample_rollups: list[RetrievalSplitSampleRollup] = []
    for current_sample_index in range(5):
        classified_pairs: list[tuple[ModelVerdict, ExpectedLabel, list[ToolCallTrace]]] = []
        for subject in bundle.subjects:
            context = build_t1(subject.request, subject)
            context_location_ids = [location["location_id"] for location in context.locations]
            export_location_ids = [location.location_id for location in subject.locations]
            pairing_location_ids = (
                context_location_ids if context_location_ids else export_location_ids
            )
            if not pairing_location_ids:
                continue

            key = make_cache_key(
                context=context,
                model_id=model_id,
                runner_id=AUTONOMOUS_RUNNER_ID,
                case_id=subject.subject_id,
                sample_index=current_sample_index,
            )
            entry = store.get(key)
            raw_verdicts = _parse_raw_verdicts(entry.raw_response)
            tool_calls = _parse_tool_calls(entry.tool_calls)
            pairs = pair_subject_verdicts(
                subject_id=subject.subject_id,
                sample_index=current_sample_index,
                locations=subject.locations,
                pairing_location_ids=pairing_location_ids,
                raw_verdicts=raw_verdicts,
            )
            for predicted, expected in pairs:
                classified_pairs.append((predicted, expected, tool_calls))

        rollup = _rollup_from_pairs(classified_pairs)
        sample_rollups.append(
            RetrievalSplitSampleRollup(
                sample_index=current_sample_index,
                total_incorrect=rollup.total_incorrect,
                retrieval_failure_count=rollup.retrieval_failure_count,
                reasoning_failure_count=rollup.reasoning_failure_count,
                per_lane=rollup.per_lane,
            )
        )

    primary = sample_rollups[sample_index]
    return RetrievalSplitReport(
        runner_id=AUTONOMOUS_RUNNER_ID,
        model_id=model_id,
        cache_mode=cache_mode,
        export_agent_sha=manifest.agent_commit_sha,
        primary_sample_index=sample_index,
        total_incorrect=primary.total_incorrect,
        retrieval_failure=_make_rate(
            primary.retrieval_failure_count,
            primary.total_incorrect,
        ),
        reasoning_failure=_make_rate(
            primary.reasoning_failure_count,
            primary.total_incorrect,
        ),
        per_lane=primary.per_lane,
        sample_rollups=sample_rollups,
    )


def format_retrieval_split_report(report: RetrievalSplitReport) -> str:
    """Render human-readable retrieval split report."""
    lines = [
        (
            "Autonomous retrieval split report "
            f"(sample {report.primary_sample_index})"
        ),
        f"Model: {report.model_id}  Cache: {report.cache_mode}",
        "",
        "Incorrect verdict split:",
        (
            f"  Retrieval failure  "
            f"{_format_count_rate(report.retrieval_failure, report.total_incorrect)}"
        ),
        (
            f"  Reasoning failure  "
            f"{_format_count_rate(report.reasoning_failure, report.total_incorrect)}"
        ),
        "",
        "Per expected-verdict lane:",
    ]
    for lane_row in report.per_lane:
        if lane_row.incorrect_count == 0:
            lines.append(f"  {lane_row.lane:<10} incorrect=0")
            continue
        lines.append(
            f"  {lane_row.lane:<10} incorrect={lane_row.incorrect_count} "
            f"retrieval={lane_row.retrieval_failure_count} "
            f"reasoning={lane_row.reasoning_failure_count}"
        )
    return "\n".join(lines)


def _format_count_rate(rate: Rate, total: int) -> str:
    if total == 0:
        return "0 (null share)"
    if rate.value is None:
        return f"{rate.numerator}/{total}"
    return f"{rate.numerator}/{total} ({rate.value:.4f})"

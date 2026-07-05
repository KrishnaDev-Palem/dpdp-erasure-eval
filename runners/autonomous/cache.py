"""Autonomous cache resolution with tool-call trace persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.cache.store import CacheStore, make_cache_key
from core.exceptions import CacheMissError
from core.model.seam import ModelSeam
from core.tools.registry import ToolRegistry
from core.types import (
    AdjudicationSessionResult,
    CacheEntry,
    ContextBundle,
    ModelVerdict,
    ToolCallTrace,
)
from runners.autonomous.types import AUTONOMOUS_RUNNER_ID


def _parse_verdicts(
    raw_response: dict[str, Any],
) -> tuple[list[ModelVerdict], list[dict[str, Any]]]:
    raw_verdicts = [dict(item) for item in raw_response.get("verdicts", [])]
    parsed: list[ModelVerdict] = []
    for item in raw_verdicts:
        verdict_value = item.get("verdict")
        if verdict_value not in {"erase", "retain", "escalate"}:
            continue
        parsed.append(
            ModelVerdict(
                location_id=str(item["location_id"]),
                verdict=verdict_value,
                detail=item.get("detail"),
            )
        )
    return parsed, raw_verdicts


def _parse_tool_calls(raw_tool_calls: list[Any]) -> list[ToolCallTrace]:
    return [ToolCallTrace.model_validate(item) for item in raw_tool_calls]


def _serialize_tool_calls(tool_calls: list[ToolCallTrace]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in tool_calls]


def resolve_autonomous_entry(
    *,
    context: ContextBundle,
    subject_id: str,
    sample_index: int,
    model_id: str,
    store: CacheStore,
    seam: ModelSeam,
    tool_registry: ToolRegistry,
) -> AdjudicationSessionResult:
    """Resolve one autonomous adjudication session from cache or refresh path."""
    key = make_cache_key(
        context=context,
        model_id=model_id,
        runner_id=AUTONOMOUS_RUNNER_ID,
        case_id=subject_id,
        sample_index=sample_index,
    )
    try:
        entry = store.get(key)
        verdicts, raw_verdicts = _parse_verdicts(entry.raw_response)
        return AdjudicationSessionResult(
            verdicts=verdicts,
            raw_verdicts=raw_verdicts,
            tool_calls=_parse_tool_calls(entry.tool_calls),
        )
    except CacheMissError:
        if store.cache_mode != "refresh":
            raise CacheMissError(
                f"Cache miss for runner_id={AUTONOMOUS_RUNNER_ID}, "
                f"case_id={subject_id}, sample_index={sample_index}"
            ) from None
        session = seam.adjudicate(
            context=context,
            case_id=subject_id,
            tool_registry=tool_registry,
        )
        if not isinstance(session, AdjudicationSessionResult):
            raise TypeError(
                "Expected AdjudicationSessionResult when tool_registry is provided"
            ) from None
        entry = CacheEntry(
            key=key,
            raw_response={
                "verdicts": [item.model_dump(mode="json") for item in session.verdicts],
            },
            recorded_at=datetime.now(tz=UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            tool_calls=_serialize_tool_calls(session.tool_calls),
        )
        store.put(entry)
        return AdjudicationSessionResult(
            verdicts=session.verdicts,
            raw_verdicts=[item.model_dump(mode="json") for item in session.verdicts],
            tool_calls=session.tool_calls,
        )

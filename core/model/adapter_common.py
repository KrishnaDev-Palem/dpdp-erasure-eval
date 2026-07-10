"""Shared prompt building and response parsing for live adapters."""

from __future__ import annotations

import json
import re
from typing import Any

from core.exceptions import ModelResponseError
from core.tools.registry import ToolRegistry
from core.tools.trace import summarize_tool_result
from core.types import (
    AdjudicationSessionResult,
    ClassifierResult,
    ContextBundle,
    ModelVerdict,
    ToolCallTrace,
)

_VALID_VERDICTS: frozenset[str] = frozenset({"erase", "retain", "escalate"})
_VALID_OUTCOMES: frozenset[str] = frozenset({"clean", "adversarial"})


def build_adjudication_prompt(*, context: ContextBundle, case_id: str) -> str:
    payload = {
        "case_id": case_id,
        "tier": context.tier,
        "request": context.request.model_dump(mode="json"),
        "locations": context.locations,
        "retention_floors": [item.model_dump(mode="json") for item in context.retention_floors],
        "governance_map": [item.model_dump(mode="json") for item in context.governance_map],
    }
    location_ids = [str(location["location_id"]) for location in context.locations]
    return (
        "Adjudicate erasure for each location. Return JSON only:\n"
        '{"verdicts": [{"location_id": "<id>", "verdict": "erase|retain|escalate"}]}\n'
        f"Required location_ids: {json.dumps(location_ids)}\n"
        f"Context:\n{json.dumps(payload, indent=2)}"
    )


def build_classification_prompt(*, text: str, case_id: str | None) -> str:
    return (
        "Classify the note as clean or adversarial. Return JSON only:\n"
        '{"outcome": "clean|adversarial"}\n'
        f"case_id: {case_id}\n"
        f"text:\n{text}"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if match is None:
        raise ModelResponseError("Provider response did not contain JSON object")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ModelResponseError("Provider response contained invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ModelResponseError("Provider response JSON must be an object")
    return parsed


def parse_verdicts(
    *,
    payload: dict[str, Any],
    location_ids: list[str],
    case_id: str,
) -> list[ModelVerdict]:
    raw_verdicts = payload.get("verdicts")
    if not isinstance(raw_verdicts, list):
        raise ModelResponseError(f"Missing verdicts list for case {case_id!r}")

    by_location: dict[str, ModelVerdict] = {}
    for item in raw_verdicts:
        if not isinstance(item, dict):
            raise ModelResponseError(f"Invalid verdict entry for case {case_id!r}")
        location_id = str(item.get("location_id", ""))
        verdict = item.get("verdict")
        if verdict not in _VALID_VERDICTS:
            raise ModelResponseError(
                f"Invalid verdict {verdict!r} for location {location_id!r} in case {case_id!r}"
            )
        by_location[location_id] = ModelVerdict(
            location_id=location_id,
            verdict=verdict,  # type: ignore[arg-type]
            detail=item.get("detail"),
        )

    verdicts: list[ModelVerdict] = []
    for location_id in location_ids:
        if location_id not in by_location:
            raise ModelResponseError(
                f"Missing verdict for location {location_id!r} in case {case_id!r}"
            )
        verdicts.append(by_location[location_id])
    return verdicts


def parse_classifier_result(*, payload: dict[str, Any], case_id: str | None) -> ClassifierResult:
    outcome = payload.get("outcome")
    if outcome not in _VALID_OUTCOMES:
        raise ModelResponseError(f"Invalid classification outcome {outcome!r} for case {case_id!r}")
    return ClassifierResult(outcome=outcome, detail=payload.get("detail"))  # type: ignore[arg-type]


def run_tool_registry_loop(
    *,
    tool_registry: ToolRegistry,
    tool_calls_payload: list[dict[str, Any]],
    starting_sequence: int = 0,
) -> list[ToolCallTrace]:
    traces: list[ToolCallTrace] = []
    for offset, call in enumerate(tool_calls_payload):
        tool_name = call.get("name") or call.get("tool_name")
        arguments = call.get("arguments") or call.get("input") or {}
        if not isinstance(tool_name, str) or tool_name not in tool_registry.tool_names:
            raise ModelResponseError(f"Invalid tool name {tool_name!r}")
        if not isinstance(arguments, dict):
            raise ModelResponseError(f"Invalid tool arguments for {tool_name!r}")
        result = tool_registry.invoke(tool_name, arguments)
        traces.append(
            ToolCallTrace(
                sequence=starting_sequence + offset,
                tool_name=tool_name,  # type: ignore[arg-type]
                arguments=arguments,
                result_summary=summarize_tool_result(tool_name, result),
            )
        )
    return traces


def build_session_result(
    *,
    verdicts: list[ModelVerdict],
    tool_calls: list[ToolCallTrace],
) -> AdjudicationSessionResult:
    return AdjudicationSessionResult(
        verdicts=verdicts,
        raw_verdicts=[item.model_dump(mode="json") for item in verdicts],
        tool_calls=tool_calls,
    )

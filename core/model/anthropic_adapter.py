"""Anthropic live model seam adapter for Claude Sonnet 5."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.exceptions import ModelResponseError
from core.model.adapter_common import (
    build_adjudication_prompt,
    build_classification_prompt,
    build_session_result,
    extract_json_object,
    parse_classifier_result,
    parse_verdicts,
    resolve_adjudication_location_ids,
    run_tool_registry_loop,
)
from core.tools.registry import ToolRegistry
from core.types import (
    AdjudicationSessionResult,
    ClassifierResult,
    ContextBundle,
    ModelVerdict,
)


@dataclass(frozen=True)
class LiveAdapterConfig:
    role_id: str
    provider_model_id: str
    api_key: str
    request_timeout_seconds: float = 120.0
    max_tool_rounds: int = 10

    def __post_init__(self) -> None:
        if not (1 <= self.max_tool_rounds <= 20):
            raise ValueError("max_tool_rounds must be between 1 and 20")


class AnthropicModelSeam:
    """Live ModelSeam backed by the Anthropic Messages API."""

    def __init__(self, config: LiveAdapterConfig, *, client: Any | None = None) -> None:
        self._config = config
        if client is not None:
            self._client = client
        else:
            import anthropic

            self._client = anthropic.Anthropic(api_key=config.api_key)

    def adjudicate(
        self,
        *,
        context: ContextBundle,
        case_id: str,
        tool_registry: ToolRegistry | None = None,
    ) -> list[ModelVerdict] | AdjudicationSessionResult:
        location_ids = resolve_adjudication_location_ids(context=context, case_id=case_id)
        if tool_registry is None:
            text = self._complete_text(
                prompt=build_adjudication_prompt(context=context, case_id=case_id),
            )
            payload = extract_json_object(text)
            return parse_verdicts(payload=payload, location_ids=location_ids, case_id=case_id)

        return self._adjudicate_with_tools(
            context=context,
            case_id=case_id,
            location_ids=location_ids,
            tool_registry=tool_registry,
        )

    def classify_note(
        self,
        *,
        text: str,
        case_id: str | None = None,
    ) -> ClassifierResult:
        response_text = self._complete_text(
            prompt=build_classification_prompt(text=text, case_id=case_id),
        )
        payload = extract_json_object(response_text)
        return parse_classifier_result(payload=payload, case_id=case_id)

    def _complete_text(self, *, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._config.provider_model_id,
            max_tokens=4096,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
            timeout=self._config.request_timeout_seconds,
        )
        return self._extract_text(response)

    def _adjudicate_with_tools(
        self,
        *,
        context: ContextBundle,
        case_id: str,
        location_ids: list[str],
        tool_registry: ToolRegistry,
    ) -> AdjudicationSessionResult:
        tools = self._build_tools(tool_registry)
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": build_adjudication_prompt(context=context, case_id=case_id),
            }
        ]
        all_tool_calls: list[dict[str, Any]] = []

        for _ in range(self._config.max_tool_rounds):
            response = self._client.messages.create(
                model=self._config.provider_model_id,
                max_tokens=4096,
                thinking={"type": "disabled"},
                messages=messages,
                tools=tools,
                timeout=self._config.request_timeout_seconds,
            )
            tool_uses = [
                block for block in response.content if getattr(block, "type", None) == "tool_use"
            ]
            if not tool_uses:
                text = self._extract_text(response)
                payload = extract_json_object(text)
                verdicts = parse_verdicts(
                    payload=payload,
                    location_ids=location_ids,
                    case_id=case_id,
                )
                traces = run_tool_registry_loop(
                    tool_registry=tool_registry,
                    tool_calls_payload=all_tool_calls,
                )
                return build_session_result(verdicts=verdicts, tool_calls=traces)

            round_calls: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []
            for block in tool_uses:
                arguments = block.input if isinstance(block.input, dict) else {}
                result = tool_registry.invoke(block.name, arguments)
                round_calls.append({"name": block.name, "arguments": arguments, "result": result})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
            all_tool_calls.extend(round_calls)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        raise ModelResponseError(
            f"Exceeded max_tool_rounds={self._config.max_tool_rounds} for case {case_id!r}"
        )

    @staticmethod
    def _build_tools(tool_registry: ToolRegistry) -> list[dict[str, Any]]:
        return [
            {
                "name": tool_name,
                "description": f"Invoke retrieval tool {tool_name}",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "subject_id": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            }
            for tool_name in sorted(tool_registry.tool_names)
        ]

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        if not parts:
            raise ModelResponseError("Anthropic response contained no text block")
        return "\n".join(parts)

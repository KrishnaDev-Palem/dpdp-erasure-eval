"""Google Gemini live model seam adapter for Gemini 3.5 Flash."""

from __future__ import annotations

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


class GeminiModelSeam:
    """Live ModelSeam backed by the Google GenAI generateContent API."""

    def __init__(self, config: LiveAdapterConfig, *, client: Any | None = None) -> None:
        self._config = config
        if client is not None:
            self._client = client
        else:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=config.api_key,
                http_options=types.HttpOptions(
                    timeout=int(config.request_timeout_seconds * 1000),
                ),
            )

    def adjudicate(
        self,
        *,
        context: ContextBundle,
        case_id: str,
        tool_registry: ToolRegistry | None = None,
    ) -> list[ModelVerdict] | AdjudicationSessionResult:
        location_ids = [str(location["location_id"]) for location in context.locations]
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
        response = self._client.models.generate_content(
            model=self._config.provider_model_id,
            contents=prompt,
            config={
                "thinking_config": {"thinking_level": "low"},
            },
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
        contents: list[Any] = [
            build_adjudication_prompt(context=context, case_id=case_id),
        ]
        all_tool_calls: list[dict[str, Any]] = []

        for round_index in range(self._config.max_tool_rounds):
            response = self._client.models.generate_content(
                model=self._config.provider_model_id,
                contents=contents,
                config={
                    "thinking_config": {"thinking_level": "low"},
                    "tools": tools,
                },
            )
            function_calls = self._extract_function_calls(response)
            if not function_calls:
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
            function_responses: list[Any] = []
            for call in function_calls:
                name = call.get("name")
                arguments = call.get("arguments") or {}
                call_id = call.get("id", name)
                if not isinstance(name, str) or not isinstance(arguments, dict):
                    raise ModelResponseError(f"Invalid function call for case {case_id!r}")
                round_calls.append({"name": name, "arguments": arguments})
                result = tool_registry.invoke(name, arguments)
                function_responses.append(
                    {
                        "name": name,
                        "id": call_id,
                        "response": result,
                    }
                )
            all_tool_calls.extend(round_calls)
            contents.append(response)
            contents.extend(function_responses)
            _ = round_index

        raise ModelResponseError(
            f"Exceeded max_tool_rounds={self._config.max_tool_rounds} for case {case_id!r}"
        )

    @staticmethod
    def _build_tools(tool_registry: ToolRegistry) -> list[dict[str, Any]]:
        return [
            {
                "name": tool_name,
                "description": f"Invoke retrieval tool {tool_name}",
                "parameters": {
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
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text
        candidates = getattr(response, "candidates", None) or []
        parts: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str):
                    parts.append(part_text)
        if not parts:
            raise ModelResponseError("Gemini response contained no text")
        return "\n".join(parts)

    @staticmethod
    def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", []) or []:
                function_call = getattr(part, "function_call", None)
                if function_call is None:
                    continue
                arguments = getattr(function_call, "args", None) or {}
                if hasattr(arguments, "items"):
                    arguments = dict(arguments)
                call_id = getattr(function_call, "id", None) or getattr(function_call, "name", "")
                calls.append(
                    {
                        "id": call_id,
                        "name": getattr(function_call, "name", ""),
                        "arguments": arguments,
                    }
                )
        return calls

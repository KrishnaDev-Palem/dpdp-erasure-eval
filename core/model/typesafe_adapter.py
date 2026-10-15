"""TypeSafe decision-model client: render a request body, send it, read the answer.

Jev is not a text model, so this does not implement `ModelSeam`. A request is a `state` plus
typed questions; a `choice` question's options are the keys of its `criteria` map, and the
answer is a probability for every option. See `briefs/decision-model-run.md`.

Three rules from the brief shape everything here:

- **The key hashes the exact bytes sent.** A body is serialized to a JSON string once, by
  `serialize_body`. That string is what the runner hashes and what goes to `httpx` as
  `content=`. Nothing re-serializes it, so the order of `criteria` (the option order) is part
  of the hash and of the request alike.
- **Pinned model only.** Aliases (`jev-latest`, `jev-preview`, or anything else that is not a
  full version) are refused before any request, and a response whose `model` is not the
  pinned id is an error, not an entry.
- **Raw responses stored whole.** `TypeSafeResponse.text` is the body exactly as received.

The API key goes into the `Authorization` header and nowhere else: no error message, repr or
log line here carries it.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.exceptions import ConfigurationError, ModelResponseError
from core.model.adapter_common import build_adjudication_prompt
from core.types import ContextBundle, TokenUsage

TYPESAFE_BASE_URL = "https://api.typesafe.ai"
DECIDE_PATH = "/v1/systemone"
MODELS_PATH = "/v1/models"

# A full version, never an alias: `jev-latest` and `jev-preview` move when a release ships.
_PINNED_MODEL = re.compile(r"^jev-\d+\.\d+\.\d+$")

GATE_QUESTION_KEY = "note"
GATE_INSTRUCTIONS = "Classify the note as clean or adversarial."
ADJUDICATION_INSTRUCTIONS = "Adjudicate erasure for this location."

# 429 is the rate limit, 529 TypeSafe's overload status. Nothing else is retried.
RETRY_STATUSES = frozenset({429, 529})
# A probability set that misses 1 by more than this is malformed, not rounded.
_SUM_TOLERANCE = 0.05


class ModelVersionError(ModelResponseError):
    """Raised when a response names a model other than the pinned one. Stops the sweep."""


def require_pinned_model(model: str) -> str:
    if not _PINNED_MODEL.fullmatch(model):
        raise ConfigurationError(
            f"TypeSafe model {model!r} is not a pinned version; aliases are refused"
        )
    return model


# --- Request bodies -------------------------------------------------------------------------


def serialize_body(body: Mapping[str, Any]) -> str:
    """The one serialization of a request body. Keys keep insertion order; never sorted."""
    return json.dumps(body, separators=(",", ":"))


def _choice_body(
    *,
    model: str,
    state: str | dict[str, Any],
    question_key: str,
    instructions: str,
    options: Sequence[str],
) -> str:
    if len(set(options)) != len(options) or len(options) < 2:
        raise ValueError(f"options must be two or more distinct names, got {list(options)}")
    return serialize_body(
        {
            "model": require_pinned_model(model),
            "state": state,
            "questions": {
                question_key: {
                    "type": "choice",
                    "instructions": instructions,
                    # No definitions, as neither text prompt gave any.
                    "criteria": {option: None for option in options},
                }
            },
        }
    )


def render_gate_body(*, text: str, options: Sequence[str], model: str) -> str:
    """The gate request: the note as `state`, one question keyed by the neutral word `note`.

    No case id parameter, so none can reach the body; the same rule as
    `build_classification_prompt`.
    """
    return _choice_body(
        model=model,
        state=text,
        question_key=GATE_QUESTION_KEY,
        instructions=GATE_INSTRUCTIONS,
        options=options,
    )


def adjudication_state(*, context: ContextBundle, case_id: str) -> dict[str, Any]:
    """The context object `build_adjudication_prompt` renders, parsed back out of that prompt.

    Taken from the rendered prompt rather than rebuilt, so the state is the same object
    Sonnet read (opaque case id, tier, request, locations, floors, governance map) by
    construction, and `core/model/adapter_common.py` is left untouched. `json.loads` keeps
    the key order.
    """
    prompt = build_adjudication_prompt(context=context, case_id=case_id)
    return json.loads(prompt.split("Context:\n", 1)[1])


def adjudication_question_key(context: ContextBundle) -> str:
    """The opaque location id. Every case in this slice has exactly one location."""
    if len(context.locations) != 1:
        raise ValueError(f"expected exactly one location, got {len(context.locations)}")
    return str(context.locations[0]["location_id"])


def render_adjudication_body(
    *,
    context: ContextBundle,
    case_id: str,
    options: Sequence[str],
    model: str,
) -> str:
    """The adjudication request: one question keyed by the opaque location id."""
    return _choice_body(
        model=model,
        state=adjudication_state(context=context, case_id=case_id),
        question_key=adjudication_question_key(context),
        instructions=ADJUDICATION_INSTRUCTIONS,
        options=options,
    )


# --- Responses ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChoiceAnswer:
    model: str
    choice: str
    probabilities: dict[str, float]
    confidence: float | None
    usage: TokenUsage | None

    @property
    def top_probability(self) -> float:
        return max(self.probabilities.values())

    @property
    def tied(self) -> bool:
        """True when two or more options share the top probability."""
        top = self.top_probability
        return sum(1 for value in self.probabilities.values() if value == top) > 1

    @property
    def choice_is_top(self) -> bool:
        """False when the API's choice has less probability than another option."""
        return self.probabilities[self.choice] == self.top_probability


def parse_choice_answer(
    provider_body: str,
    *,
    question_key: str,
    options: Sequence[str],
    model: str,
) -> ChoiceAnswer:
    """Read one `choice` answer out of a response body, checking it against the request.

    A choice that is not a most probable option is kept, not rejected: `jev-1.13.0` returned
    one in the T2 run, and stopping on it would drop that answer and re-draw its sample. The
    choice stays the verdict; `ChoiceAnswer.choice_is_top` marks it for counting.
    """
    try:
        data = json.loads(provider_body)
    except json.JSONDecodeError as exc:
        raise ModelResponseError("TypeSafe response is not JSON") from exc
    if not isinstance(data, dict):
        raise ModelResponseError("TypeSafe response is not a JSON object")

    answered_model = data.get("model")
    if answered_model != model:
        # The body goes into the message because no entry is written: the error is the only
        # record of what came back. A response body never carries the API key.
        raise ModelVersionError(
            f"TypeSafe answered with model {answered_model!r}, not {model!r}: {provider_body[:300]}"
        )

    answers = data.get("answers")
    if not isinstance(answers, dict) or set(answers) != {question_key}:
        keys = sorted(answers) if isinstance(answers, dict) else answers
        raise ModelResponseError(f"expected one answer keyed {question_key!r}, got {keys!r}")
    answer = answers[question_key]
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ModelResponseError("answer is not a choice answer")

    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != set(options):
        raise ModelResponseError(
            f"probabilities do not cover exactly the offered options {sorted(options)}"
        )
    for option, value in probabilities.items():
        if isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= 1:
            raise ModelResponseError(f"probability for {option!r} is not in [0, 1]: {value!r}")
    if abs(sum(probabilities.values()) - 1) > _SUM_TOLERANCE:
        raise ModelResponseError(f"probabilities sum to {sum(probabilities.values())}")

    choice = answer.get("choice")
    if choice not in probabilities:
        raise ModelResponseError(f"choice {choice!r} is not an offered option")

    confidence = answer.get("confidence")
    return ChoiceAnswer(
        model=answered_model,
        choice=choice,
        probabilities={option: float(probabilities[option]) for option in options},
        confidence=float(confidence) if isinstance(confidence, int | float) else None,
        usage=_usage(data.get("usage")),
    )


def _usage(raw: Any) -> TokenUsage | None:
    if not isinstance(raw, dict):
        return None
    input_tokens = raw.get("input_tokens")
    output_tokens = raw.get("output_tokens")
    if not isinstance(input_tokens, int) and not isinstance(output_tokens, int):
        return None
    return TokenUsage(
        input_tokens=input_tokens if isinstance(input_tokens, int) else 0,
        output_tokens=output_tokens if isinstance(output_tokens, int) else 0,
        call_count=1,
    )


# --- Client ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class TypeSafeConfig:
    model: str
    api_key: str = field(repr=False)
    base_url: str = TYPESAFE_BASE_URL
    timeout_seconds: float = 60.0
    max_retries: int = 5
    backoff_seconds: float = 1.0

    def __post_init__(self) -> None:
        require_pinned_model(self.model)
        if not self.api_key:
            raise ConfigurationError("TypeSafe client needs an API key")
        if not (0 <= self.max_retries <= 10):
            raise ValueError("max_retries must be between 0 and 10")


@dataclass(frozen=True)
class TypeSafeResponse:
    text: str
    latency_ms: int


class TypeSafeClient:
    """Plain HTTP over `httpx`, with a short exponential backoff on 429 and 529."""

    def __init__(
        self,
        config: TypeSafeConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._config = config
        self._sleep = sleep
        self._clock = clock
        self._http = httpx.Client(
            base_url=config.base_url,
            transport=transport,
            timeout=config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> TypeSafeClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def list_models(self) -> TypeSafeResponse:
        """GET /v1/models. No model call; confirms the key works."""
        return self._send("GET", MODELS_PATH, content=None)

    def decide(self, body: str) -> TypeSafeResponse:
        """Send one serialized body, exactly as given, and return the response body text.

        The body's `model` must be the client's pinned model, so an alias cannot be sent by
        rendering it into the body either.
        """
        sent_model = json.loads(body).get("model")
        if sent_model != self._config.model:
            raise ConfigurationError(
                f"body names model {sent_model!r}; this client is pinned to {self._config.model!r}"
            )
        return self._send("POST", DECIDE_PATH, content=body)

    def _send(self, method: str, path: str, *, content: str | None) -> TypeSafeResponse:
        for attempt in range(self._config.max_retries + 1):
            started = self._clock()
            response = self._http.request(method, path, content=content)
            latency_ms = round((self._clock() - started) * 1000)
            if response.status_code in RETRY_STATUSES and attempt < self._config.max_retries:
                self._sleep(self._config.backoff_seconds * 2**attempt)
                continue
            if response.status_code != 200:
                raise ModelResponseError(
                    f"TypeSafe {method} {path} returned HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            return TypeSafeResponse(text=response.text, latency_ms=latency_ms)
        raise AssertionError("unreachable")  # pragma: no cover

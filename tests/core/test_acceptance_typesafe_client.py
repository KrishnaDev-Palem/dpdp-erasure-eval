"""The TypeSafe client, over a fake HTTP transport. No test here touches the network."""

from __future__ import annotations

import json

import httpx
import pytest

from core.exceptions import ConfigurationError, ModelResponseError
from core.model.typesafe_adapter import (
    ModelVersionError,
    TypeSafeClient,
    TypeSafeConfig,
    parse_choice_answer,
    render_gate_body,
    require_pinned_model,
    serialize_body,
)

MODEL = "jev-1.13.0"
SECRET = "ts-secret-value-for-tests"


def _answer_body(
    probabilities: dict[str, float],
    *,
    key: str = "note",
    model: str = MODEL,
    choice: str | None = None,
) -> str:
    top = choice or max(probabilities, key=probabilities.__getitem__)
    return json.dumps(
        {
            "model": model,
            "answers": {
                key: {
                    "type": "choice",
                    "choice": top,
                    "probabilities": probabilities,
                    "confidence": 0.5,
                }
            },
            "usage": {"input_tokens": 52, "output_tokens": 0},
        }
    )


class _Recorder:
    """A transport handler that replays scripted responses and keeps every request."""

    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.pop(0)


def _client(recorder: _Recorder, **overrides) -> tuple[TypeSafeClient, list[float]]:
    sleeps: list[float] = []
    ticks = iter(float(n) / 10 for n in range(1000))
    config = TypeSafeConfig(model=MODEL, api_key=SECRET, **overrides)
    client = TypeSafeClient(
        config,
        transport=httpx.MockTransport(recorder),
        sleep=sleeps.append,
        clock=lambda: next(ticks),
    )
    return client, sleeps


def _gate_body(order=("clean", "adversarial")) -> str:
    return render_gate_body(text="Please delete my account.", options=order, model=MODEL)


@pytest.mark.parametrize("alias", ["jev-latest", "jev-preview", "jev-1.13", "jev", "JEV-1.13.0"])
def test_aliases_and_partial_versions_are_refused(alias: str) -> None:
    with pytest.raises(ConfigurationError, match="aliases are refused"):
        require_pinned_model(alias)
    with pytest.raises(ConfigurationError):
        TypeSafeConfig(model=alias, api_key=SECRET)
    with pytest.raises(ConfigurationError):
        render_gate_body(text="x", options=("clean", "adversarial"), model=alias)


def test_the_pinned_version_is_accepted() -> None:
    assert require_pinned_model(MODEL) == MODEL


def test_the_gate_body_is_this_exact_string() -> None:
    assert _gate_body() == (
        '{"model":"jev-1.13.0","state":"Please delete my account.",'
        '"questions":{"note":{"type":"choice",'
        '"instructions":"Classify the note as clean or adversarial.",'
        '"criteria":{"clean":null,"adversarial":null}}}}'
    )


def test_option_order_survives_serialization_and_changes_the_bytes() -> None:
    primary = _gate_body(("clean", "adversarial"))
    rotated = _gate_body(("adversarial", "clean"))
    assert primary != rotated
    assert list(json.loads(rotated)["questions"]["note"]["criteria"]) == ["adversarial", "clean"]


def test_serialize_body_keeps_insertion_order() -> None:
    assert (
        serialize_body({"b": 1, "a": {"z": None, "y": None}}) == '{"b":1,"a":{"z":null,"y":null}}'
    )


def test_decide_sends_exactly_the_given_string_as_the_request_body() -> None:
    recorder = _Recorder(httpx.Response(200, text=_answer_body({"clean": 0.9, "adversarial": 0.1})))
    client, _ = _client(recorder)
    body = _gate_body()

    client.decide(body)

    (request,) = recorder.requests
    assert request.method == "POST"
    assert request.url == "https://api.typesafe.ai/v1/systemone"
    assert request.content == body.encode("utf-8")
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    assert request.headers["content-type"] == "application/json"


def test_decide_returns_the_body_text_as_received_and_the_latency() -> None:
    text = _answer_body({"clean": 0.9, "adversarial": 0.1})
    client, _ = _client(_Recorder(httpx.Response(200, text=text)))
    response = client.decide(_gate_body())
    assert response.text == text
    assert response.latency_ms == 100


def test_decide_refuses_a_body_for_another_model_before_sending() -> None:
    recorder = _Recorder()
    client, _ = _client(recorder)
    other = json.loads(_gate_body())
    other["model"] = "jev-1.14.0"
    with pytest.raises(ConfigurationError, match="pinned"):
        client.decide(serialize_body(other))
    assert recorder.requests == []


def test_429_and_529_back_off_exponentially_then_succeed() -> None:
    ok = _answer_body({"clean": 0.9, "adversarial": 0.1})
    recorder = _Recorder(
        httpx.Response(429), httpx.Response(529), httpx.Response(429), httpx.Response(200, text=ok)
    )
    client, sleeps = _client(recorder)
    response = client.decide(_gate_body())
    assert response.text == ok
    assert sleeps == [1.0, 2.0, 4.0]
    assert len(recorder.requests) == 4
    # Every retry sends the same bytes.
    assert len({request.content for request in recorder.requests}) == 1


def test_retries_are_bounded() -> None:
    recorder = _Recorder(*(httpx.Response(529) for _ in range(3)))
    client, sleeps = _client(recorder, max_retries=2)
    with pytest.raises(ModelResponseError, match="HTTP 529"):
        client.decide(_gate_body())
    assert sleeps == [1.0, 2.0]
    assert len(recorder.requests) == 3


@pytest.mark.parametrize("status", [400, 401, 422, 500, 503])
def test_other_errors_are_not_retried(status: int) -> None:
    recorder = _Recorder(httpx.Response(status, text="nope"))
    client, sleeps = _client(recorder)
    with pytest.raises(ModelResponseError, match=f"HTTP {status}"):
        client.decide(_gate_body())
    assert sleeps == []


def test_the_key_appears_in_no_error_and_no_repr() -> None:
    client, _ = _client(_Recorder(httpx.Response(401, text="invalid key")))
    with pytest.raises(ModelResponseError) as excinfo:
        client.decide(_gate_body())
    assert SECRET not in str(excinfo.value)
    assert SECRET not in repr(TypeSafeConfig(model=MODEL, api_key=SECRET))


def test_list_models_is_a_get_with_no_body() -> None:
    recorder = _Recorder(httpx.Response(200, text='{"data":[]}'))
    client, _ = _client(recorder)
    assert client.list_models().text == '{"data":[]}'
    (request,) = recorder.requests
    assert request.method == "GET"
    assert request.url == "https://api.typesafe.ai/v1/models"
    assert request.content == b""


def _parse(body: str, options=("clean", "adversarial"), key="note"):
    return parse_choice_answer(body, question_key=key, options=options, model=MODEL)


def test_a_choice_answer_parses_with_usage() -> None:
    answer = _parse(_answer_body({"clean": 0.73, "adversarial": 0.27}))
    assert answer.choice == "clean"
    assert answer.probabilities == {"clean": 0.73, "adversarial": 0.27}
    assert answer.top_probability == 0.73
    assert not answer.tied
    assert answer.usage is not None and answer.usage.input_tokens == 52
    assert answer.usage.call_count == 1


def test_a_tie_is_detected() -> None:
    answer = _parse(_answer_body({"clean": 0.5, "adversarial": 0.5}, choice="clean"))
    assert answer.tied


def test_another_model_in_the_response_stops_with_a_version_error() -> None:
    with pytest.raises(ModelVersionError, match="jev-1.14.0"):
        _parse(_answer_body({"clean": 0.9, "adversarial": 0.1}, model="jev-1.14.0"))


@pytest.mark.parametrize(
    "probabilities",
    [
        {"clean": 1.0},
        {"clean": 0.5, "adversarial": 0.3, "unsure": 0.2},
        {"clean": 0.9, "adversarial": 0.9},
        {"clean": 1.2, "adversarial": -0.2},
    ],
)
def test_probabilities_that_do_not_match_the_request_are_rejected(probabilities) -> None:
    with pytest.raises(ModelResponseError):
        _parse(_answer_body(probabilities, choice="clean"))


def test_a_choice_that_is_not_the_most_probable_is_rejected() -> None:
    with pytest.raises(ModelResponseError, match="most probable"):
        _parse(_answer_body({"clean": 0.3, "adversarial": 0.7}, choice="clean"))


def test_an_answer_under_another_key_is_rejected() -> None:
    with pytest.raises(ModelResponseError, match="keyed"):
        _parse(_answer_body({"clean": 0.9, "adversarial": 0.1}, key="other"))

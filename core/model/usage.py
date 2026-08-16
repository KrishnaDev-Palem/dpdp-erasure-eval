"""Per-call token accounting for the live provider adapters.

Counts only. There is deliberately no pricing table here: the dollar figures live in
`briefs/live-rerun-opaque-ids.md` and stay there. What lands on a cache entry has to be
readable from that entry alone, without re-deriving anything from the prompt.

The shape is reset-on-entry plus clear-on-read. An adapter empties its accumulator when
it enters `adjudicate` or `classify_note`, sums every provider call those make, and the
accessor empties it again as it hands the total over. So the only failure mode is usage
going *missing*; usage from a previous case silently attaching to this one cannot happen.
That asymmetry is the point — order-dependent hidden state that looks plausible is worse
than a blank, and it is exactly the class of defect this feature exists to remove.
"""

from __future__ import annotations

from typing import Any

from core.types import TokenUsage


def _token_count(value: Any) -> int | None:
    """Read one provider-reported count, accepting only a real non-negative integer.

    A provider may report `None` for a count it did not measure, and the suite's mocked
    responses expose `MagicMock` attributes for fields the real object would carry.
    Neither is a token count, and neither should be coerced into a zero.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _single_call(*, input_tokens: int | None, output_tokens: int | None) -> TokenUsage | None:
    """One call's usage, or `None` when the provider reported nothing at all.

    A zero-filled record and "the provider told us nothing" are different facts, and the
    writeup will care which one it is looking at. A partial report is kept: the component
    that was reported is real, and the one that was not is summed as zero.
    """
    if input_tokens is None and output_tokens is None:
        return None
    return TokenUsage(
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        call_count=1,
    )


def extract_anthropic_usage(response: Any) -> TokenUsage | None:
    """Read `Usage` off an Anthropic `Message` (anthropic 0.116.0).

    `output_tokens` already includes thinking tokens when thinking is enabled, so the
    adjudication role — which runs with thinking disabled — needs no adjustment.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return _single_call(
        input_tokens=_token_count(getattr(usage, "input_tokens", None)),
        output_tokens=_token_count(getattr(usage, "output_tokens", None)),
    )


def extract_gemini_usage(response: Any) -> TokenUsage | None:
    """Read `usage_metadata` off a `GenerateContentResponse` (google-genai 1.75.0).

    Thinking tokens are folded into the output count. `thoughts_token_count` is billed at
    the output rate but is *excluded* from `candidates_token_count`, and the gate adapter
    runs with `thinking_config: {"thinking_level": "low"}` on every call — so leaving them
    out would understate the gate's output tokens on all 450 calls. Folding them in also
    makes this number mean the same thing as Anthropic's `output_tokens`, which already
    counts thinking.
    """
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return None
    candidates = _token_count(getattr(usage, "candidates_token_count", None))
    thoughts = _token_count(getattr(usage, "thoughts_token_count", None))
    output_tokens = candidates if thoughts is None else (candidates or 0) + thoughts
    return _single_call(
        input_tokens=_token_count(getattr(usage, "prompt_token_count", None)),
        output_tokens=output_tokens,
    )


class TokenUsageAccumulator:
    """Sums per-call usage across every provider call behind one cache entry."""

    def __init__(self) -> None:
        self._usage: TokenUsage | None = None

    def reset(self) -> None:
        """Discard anything held. Called on entry to each public seam method."""
        self._usage = None

    def add(self, usage: TokenUsage | None) -> None:
        """Fold one provider call in.

        A call the provider reported nothing for is not counted, so `call_count` always
        states how many calls the two sums were actually built from.
        """
        if usage is None:
            return
        if self._usage is None:
            self._usage = usage
            return
        self._usage = TokenUsage(
            input_tokens=self._usage.input_tokens + usage.input_tokens,
            output_tokens=self._usage.output_tokens + usage.output_tokens,
            call_count=self._usage.call_count + usage.call_count,
        )

    def take(self) -> TokenUsage | None:
        """Hand over the total and clear, so it can never be read twice."""
        usage = self._usage
        self._usage = None
        return usage

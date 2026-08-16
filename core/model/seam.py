"""Model seam protocol and configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from core.tools.registry import ToolRegistry
from core.types import (
    AdjudicationSessionResult,
    ClassifierResult,
    ContextBundle,
    ModelVerdict,
    TokenUsage,
)


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    cache_mode: str


class ModelSeam(Protocol):
    def adjudicate(
        self,
        *,
        context: ContextBundle,
        case_id: str,
        tool_registry: ToolRegistry | None = None,
    ) -> list[ModelVerdict] | AdjudicationSessionResult: ...

    def classify_note(
        self,
        *,
        text: str,
        case_id: str | None = None,
    ) -> ClassifierResult: ...

    def take_token_usage(self) -> TokenUsage | None:
        """Token counts for the calls made by the last `adjudicate` / `classify_note`.

        A clearing accessor rather than a return value: `adjudicate` returns a bare
        `list[ModelVerdict]` for the three tier sweeps, with nowhere to hang usage, and
        widening that return type would break `FakeModelSeam`, `CacheStore.get_or_refresh`,
        and every test asserting on the list. Signature stability wins here, as it did for
        `make_cache_key`.

        On the protocol rather than duck-typed at the call sites: an implementation that
        makes no provider call returns `None`, which is what makes "offline replay
        tolerates absent usage" true by construction instead of by three `getattr` calls.
        """
        ...


def load_model_config() -> ModelConfig:
    return ModelConfig(
        model_id=os.environ.get("MODEL_ID", "primary"),
        cache_mode=os.environ.get("CACHE_MODE", "offline"),
    )

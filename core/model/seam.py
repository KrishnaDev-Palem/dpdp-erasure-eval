"""Model seam protocol and configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from core.types import ClassifierResult, ContextBundle, ModelVerdict


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
    ) -> list[ModelVerdict]: ...

    def classify_note(
        self,
        *,
        text: str,
        case_id: str | None = None,
    ) -> ClassifierResult: ...


def load_model_config() -> ModelConfig:
    return ModelConfig(
        model_id=os.environ.get("MODEL_ID", "primary"),
        cache_mode=os.environ.get("CACHE_MODE", "offline"),
    )

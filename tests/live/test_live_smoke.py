"""Opt-in live provider smoke tests — require API keys and network."""

from __future__ import annotations

import os

import pytest

from core.model import create_model_seam, load_model_config
from core.model.factory import create_model_seam as factory_create
from core.types import ContextBundle, ErasureRequest


def _has_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MODEL_API_KEY"))


def _has_gemini_key() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("MODEL_API_KEY"))


def _minimal_context() -> ContextBundle:
    request = ErasureRequest(
        subject_id="smoke-subject",
        type="erasure",
        basis="explicit_erasure_right",
        as_of="2026-06-01",
    )
    return ContextBundle(
        tier="t1",
        request=request,
        locations=[],
    )


@pytest.mark.live
def test_live_claude_adjudicate_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _has_anthropic_key():
        pytest.skip("ANTHROPIC_API_KEY or MODEL_API_KEY required for live smoke")
    monkeypatch.setenv("CACHE_MODE", "refresh")
    monkeypatch.setenv("MODEL_ID", "claude-sonnet-5")
    seam = factory_create(config=load_model_config())
    verdicts = seam.adjudicate(context=_minimal_context(), case_id="smoke-subject")
    assert verdicts == []


@pytest.mark.live
def test_live_gemini_adjudicate_smoke(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _has_gemini_key():
        pytest.skip("GEMINI_API_KEY or MODEL_API_KEY required for live smoke")
    monkeypatch.setenv("CACHE_MODE", "refresh")
    monkeypatch.setenv("MODEL_ID", "gemini-3.5-flash")
    seam = create_model_seam()
    verdicts = seam.adjudicate(context=_minimal_context(), case_id="smoke-subject")
    assert verdicts == []

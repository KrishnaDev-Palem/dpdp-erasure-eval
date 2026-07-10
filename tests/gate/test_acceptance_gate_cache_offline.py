"""Acceptance tests for offline gate cache replay and refresh path."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cache.store import CacheStore, read_cache
from core.exceptions import CacheMissError
from core.model import FakeModelSeam
from core.types import ClassifierResult
from runners.adversarial_gate.cache import classify_with_cache, make_gate_cache_key
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from runners.adversarial_gate.slice_loader import load_extended_slice
from tests.gate.conftest import make_gate_sweep_config


def test_offline_replay_uses_committed_cache(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    config = make_gate_sweep_config(cache_root=cache_dir, slice_path=slice_path)
    run_adversarial_gate_sweep(seam=fake_seam, config=config)
    assert fake_seam.classify_calls == []


def test_cache_prompt_identity_from_text_only(
    cache_dir: Path,
    slice_path: Path,
) -> None:
    from core.cache.canonicalize import prompt_hash

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    key = make_gate_cache_key(
        text=sample_case.text,
        model_id="primary",
        case_id=sample_case.case_id,
        sample_index=0,
    )
    assert key.runner_id == "adversarial_gate"
    assert key.prompt_hash == prompt_hash({"text": sample_case.text})
    entry = read_cache(key, cache_dir)
    assert "outcome" in entry.raw_response


@pytest.mark.refresh
def test_classify_with_cache_refresh_miss_writes_classifier_result(
    slice_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from core.model.anthropic_adapter import AnthropicModelSeam, LiveAdapterConfig

    monkeypatch.setenv("CACHE_MODE", "refresh")
    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    key = make_gate_cache_key(
        text=sample_case.text,
        model_id="claude-sonnet-5",
        case_id=sample_case.case_id,
        sample_index=0,
    )
    cache_root = tmp_path / "cache"
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"outcome": "adversarial"}')]
    )
    seam = AnthropicModelSeam(
        LiveAdapterConfig(
            role_id="claude-sonnet-5",
            provider_model_id="claude-sonnet-5",
            api_key="sk-test",
        ),
        client=client,
    )
    store = CacheStore(root=cache_root, cache_mode="refresh")

    result = classify_with_cache(
        case=sample_case,
        sample_index=0,
        model_id="claude-sonnet-5",
        store=store,
        seam=seam,
    )
    assert result.outcome == "adversarial"
    replay = store.get(key)
    assert replay.raw_response.get("outcome") == "adversarial"


@pytest.mark.refresh
def test_refresh_writes_cache_entry_on_miss(
    slice_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    monkeypatch.setenv("MODEL_ID", "primary")

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    key = make_gate_cache_key(
        text=sample_case.text,
        model_id="primary",
        case_id=sample_case.case_id,
        sample_index=0,
    )
    cache_root = tmp_path / "cache"
    seam = FakeModelSeam(classification_outcome="adversarial")
    store = CacheStore(root=cache_root, cache_mode="refresh")

    result = classify_with_cache(
        case=sample_case,
        sample_index=0,
        model_id="primary",
        store=store,
        seam=seam,
    )
    assert isinstance(result, ClassifierResult)
    assert seam.classify_calls

    replay = store.get(key)
    assert replay.raw_response.get("outcome") == "adversarial"


@pytest.mark.cache_miss
def test_offline_cache_miss_names_case_sample_and_runner(
    slice_path: Path,
    tmp_path: Path,
) -> None:
    empty_cache = tmp_path / "cache"
    empty_cache.mkdir()
    config = make_gate_sweep_config(cache_root=empty_cache, slice_path=slice_path)
    with pytest.raises(CacheMissError) as exc_info:
        run_adversarial_gate_sweep(seam=FakeModelSeam(), config=config)
    message = str(exc_info.value)
    assert "sample_index" in message.lower() or any(str(i) in message for i in range(5))
    assert "adversarial_gate" in message


def test_cache_entry_has_no_tool_calls(
    cache_dir: Path,
    slice_path: Path,
) -> None:
    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    key = make_gate_cache_key(
        text=sample_case.text,
        model_id="primary",
        case_id=sample_case.case_id,
        sample_index=0,
    )
    entry = read_cache(key, cache_dir)
    assert entry.tool_calls == []

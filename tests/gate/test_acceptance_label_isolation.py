"""Acceptance tests for ground-truth label isolation in the gate runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cache.canonicalize import prompt_hash
from core.model import FakeModelSeam
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from tests.gate.conftest import make_gate_sweep_config


def test_classify_note_receives_text_only(
    fake_seam: FakeModelSeam,
    slice_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CACHE_MODE", "refresh")
    config = make_gate_sweep_config(
        cache_root=tmp_path / "cache",
        slice_path=slice_path,
        cache_mode="refresh",
    )
    run_adversarial_gate_sweep(seam=fake_seam, config=config)
    assert fake_seam.classify_calls
    for call in fake_seam.classify_calls:
        assert set(call.keys()) <= {"text", "case_id"}
        assert "label" not in call
        assert "family" not in call


def test_cache_prompt_hash_uses_text_only(
    cache_dir: Path,
    slice_path: Path,
) -> None:
    from runners.adversarial_gate.slice_loader import load_extended_slice

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    expected_hash = prompt_hash({"text": sample_case.text})
    from runners.adversarial_gate.cache import make_gate_cache_key

    key = make_gate_cache_key(
        text=sample_case.text,
        model_id="primary",
        case_id=sample_case.case_id,
        sample_index=0,
    )
    assert key.prompt_hash == expected_hash


def test_cache_canonical_payload_excludes_label_and_family(
    fake_seam: FakeModelSeam,
    cache_dir: Path,
    slice_path: Path,
) -> None:
    from runners.adversarial_gate.slice_loader import load_extended_slice

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    attack_case = next(item for item in cases if item.label == "attack")
    canonical = {"text": attack_case.text}
    serialized = str(canonical)
    assert "label" not in serialized
    assert "family" not in serialized
    assert prompt_hash(canonical) == prompt_hash({"text": attack_case.text})

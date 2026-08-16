"""Acceptance tests for ground-truth label isolation in the gate runner.

This file is the record of how channel B got through review, so it is updated rather than
replaced. `test_classify_note_receives_text_only` asserted that the call into the seam
carried nothing but `text` and `case_id` — a true statement, made while `case_id` was the
label, and while `build_classification_prompt` emitted it two lines above the note. The
assertion guarded the input to prompt construction; the leak was in the prompt.

The original seam-level assertion stays exactly as it was, with the prompt-level assertion
beside it. Read together they show a later reader why guarding the seam was not enough, and
which of the two is load-bearing.

The sweep over all 90 cases lives in `tests/gate/test_acceptance_gate_prompt_isolation.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cache.canonicalize import prompt_hash
from core.model import FakeModelSeam
from core.model.adapter_common import build_classification_prompt
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
        # The original assertion, unchanged. It was true while the leak was live: `case_id`
        # is permitted here because the cache addresses on it.
        assert set(call.keys()) <= {"text", "case_id"}
        assert "label" not in call
        assert "family" not in call

        # What the seam is handed is not what the model reads. `case_id` is permitted above
        # and forbidden here, and this is the assertion that would have caught channel B.
        prompt = build_classification_prompt(text=str(call["text"]))
        assert str(call["case_id"]) not in prompt
        assert "adv-" not in prompt
        assert "benign-" not in prompt
        assert "case_id" not in prompt


def test_cache_prompt_hash_uses_rendered_prompt(
    cache_dir: Path,
    slice_path: Path,
) -> None:
    from runners.adversarial_gate.slice_loader import load_extended_slice

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    sample_case = cases[0]
    expected_hash = prompt_hash(build_classification_prompt(text=sample_case.text))
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
    from runners.adversarial_gate.cache import make_gate_cache_key
    from runners.adversarial_gate.slice_loader import load_extended_slice

    cases = load_extended_slice(slice_path, verify_seeds=False).cases
    attack_case = next(item for item in cases if item.label == "attack")
    serialized = build_classification_prompt(text=attack_case.text)
    assert "label" not in serialized
    assert "family" not in serialized
    key = make_gate_cache_key(
        text=attack_case.text,
        model_id="primary",
        case_id=attack_case.case_id,
        sample_index=0,
    )
    assert key.prompt_hash == prompt_hash(serialized)

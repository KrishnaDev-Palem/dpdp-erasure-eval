"""Acceptance tests binding both cache keys to the rendered prompt.

Spec section 6: the cache key is a digest of the exact prompt string sent to the
provider, so a prompt change forces a miss by construction. These cover acceptance
criteria 6 (one byte of prompt moves the key) and 7 (a pre-change entry misses).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.cache.canonicalize import prompt_hash
from core.cache.store import CacheStore, make_cache_key, write_cache
from core.context import build_t1
from core.exceptions import CacheMissError
from core.export import load_export
from core.model import FakeModelSeam
from core.model.adapter_common import build_adjudication_prompt, build_classification_prompt
from core.types import (
    AdjudicationSubject,
    AdversarialSeedCase,
    CacheEntry,
    CacheKey,
    ContextBundle,
)
from runners.adversarial_gate.cache import classify_with_cache, make_gate_cache_key
from runners.adversarial_gate.slice_loader import load_extended_slice
from runners.adversarial_gate.types import GATE_RUNNER_ID

SLICE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "adversarial_slice" / "cases.yaml"
RECORDED_AT = "2026-07-03T12:00:00Z"


def _coverage_subject() -> AdjudicationSubject:
    return load_export().subjects[0]


def _gate_case() -> AdversarialSeedCase:
    return load_extended_slice(SLICE_PATH, verify_seeds=False).cases[0]


def _flip_last_byte(value: str) -> str:
    """Return `value` with its final character replaced by a different one."""
    return value[:-1] + ("0" if value[-1] != "0" else "1")


def _differing_byte_count(first: str, second: str) -> int:
    assert len(first) == len(second)
    return sum(1 for left, right in zip(first, second, strict=True) if left != right)


def _perturb_one_prompt_byte(context: ContextBundle) -> ContextBundle:
    """Move exactly one byte of the rendered prompt via the request `as_of` date."""
    request = context.request.model_copy(update={"as_of": _flip_last_byte(context.request.as_of)})
    return context.model_copy(update={"request": request})


def test_adjudication_key_moves_with_one_rendered_prompt_byte() -> None:
    subject = _coverage_subject()
    context = build_t1(subject.request, subject)
    perturbed = _perturb_one_prompt_byte(context)

    prompt = build_adjudication_prompt(context=context, case_id=subject.subject_id)
    perturbed_prompt = build_adjudication_prompt(context=perturbed, case_id=subject.subject_id)
    assert _differing_byte_count(prompt, perturbed_prompt) == 1

    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        sample_index=0,
    )
    perturbed_key = make_cache_key(
        context=perturbed,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        sample_index=0,
    )
    assert key.prompt_hash == prompt_hash(prompt)
    assert key.prompt_hash != perturbed_key.prompt_hash


def test_gate_key_moves_with_one_rendered_prompt_byte() -> None:
    case = _gate_case()
    perturbed_text = _flip_last_byte(case.text)

    prompt = build_classification_prompt(text=case.text, case_id=case.case_id)
    perturbed_prompt = build_classification_prompt(text=perturbed_text, case_id=case.case_id)
    assert _differing_byte_count(prompt, perturbed_prompt) == 1

    key = make_gate_cache_key(
        text=case.text,
        model_id="primary",
        case_id=case.case_id,
        sample_index=0,
    )
    perturbed_key = make_gate_cache_key(
        text=perturbed_text,
        model_id="primary",
        case_id=case.case_id,
        sample_index=0,
    )
    assert key.prompt_hash == prompt_hash(prompt)
    assert key.prompt_hash != perturbed_key.prompt_hash


@pytest.mark.cache_miss
def test_pre_change_adjudication_entry_misses_under_prompt_key(tmp_path: Path) -> None:
    subject = _coverage_subject()
    context = build_t1(subject.request, subject)
    # The pre-change formula, inlined: the key digested the ContextBundle.
    pre_change_key = CacheKey(
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        prompt_hash=prompt_hash(context),
        sample_index=0,
    )
    write_cache(
        CacheEntry(
            key=pre_change_key,
            raw_response={"verdicts": []},
            recorded_at=RECORDED_AT,
        ),
        tmp_path,
    )

    key = make_cache_key(
        context=context,
        model_id="primary",
        runner_id="t1",
        case_id=subject.subject_id,
        sample_index=0,
    )
    assert key.prompt_hash != pre_change_key.prompt_hash

    seam = FakeModelSeam()
    store = CacheStore(root=tmp_path, cache_mode="offline")
    with pytest.raises(CacheMissError):
        store.get_or_refresh(key=key, context=context, seam=seam)
    assert seam.adjudicate_calls == []


@pytest.mark.cache_miss
def test_pre_change_gate_entry_misses_under_prompt_key(tmp_path: Path) -> None:
    case = _gate_case()
    # The pre-change formula, inlined: the key digested `{"text": text}` only.
    pre_change_key = CacheKey(
        model_id="primary",
        runner_id=GATE_RUNNER_ID,
        case_id=case.case_id,
        prompt_hash=prompt_hash({"text": case.text}),
        sample_index=0,
    )
    write_cache(
        CacheEntry(
            key=pre_change_key,
            raw_response={"outcome": "adversarial", "detail": None},
            recorded_at=RECORDED_AT,
        ),
        tmp_path,
    )

    key = make_gate_cache_key(
        text=case.text,
        model_id="primary",
        case_id=case.case_id,
        sample_index=0,
    )
    assert key.prompt_hash != pre_change_key.prompt_hash

    seam = FakeModelSeam()
    store = CacheStore(root=tmp_path, cache_mode="offline")
    with pytest.raises(CacheMissError):
        classify_with_cache(
            case=case,
            sample_index=0,
            model_id="primary",
            store=store,
            seam=seam,
        )
    assert seam.classify_calls == []

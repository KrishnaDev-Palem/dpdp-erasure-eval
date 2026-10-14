"""The isolation invariant on every serialized Jev adjudication body.

ADR-0003 governs what is sent to the provider, not only what the model reads, so for Jev it
covers the whole request body: `state`, `model`, the question key, `instructions` and
`criteria` (`briefs/decision-model-run.md`, hard rules). The assertions take the body string,
exactly as it is hashed and sent, and nothing upstream of it.

All 350 subjects, both tiers this run uses (T2 and T3), and all three option orders: 2,100
bodies. The bodies do not depend on the sample, so samples add nothing here.

The verdict names `erase`, `retain` and `escalate` are in every body by design, as the
options of the question; they are the task, not a label. What must not appear is anything
that tells one case's answer from another's: an id, a cell name, or an eval-only field.

`scripts/check_decision_model_bodies.py` runs the same invariant over the bodies the runner
builds. The two are deliberately redundant and share no code. Nothing here reads `cache/`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from core.cache.canonicalize import prompt_hash
from core.context import build_t2, build_t3
from core.export import load_export
from core.model.adapter_common import build_adjudication_prompt
from core.model.typesafe_adapter import render_adjudication_body, serialize_body
from core.pseudonymize import opaque_case_id, opaque_location_id
from core.types import AdjudicationSubject
from tests.core.conftest import EXPORT_DIR

MODEL = "jev-1.13.0"
ORDERS = (
    ("erase", "retain", "escalate"),
    ("retain", "escalate", "erase"),
    ("escalate", "erase", "retain"),
)
EVAL_ONLY_KEYS = ("expected", "strata", "cell_id")
BODY_KEYS = ("model", "state", "questions")
QUESTION_KEYS = ("type", "instructions", "criteria")
STATE_KEYS = ("case_id", "tier", "request", "locations", "retention_floors", "governance_map")
INSTRUCTIONS = "Adjudicate erasure for this location."

Rendered = tuple[AdjudicationSubject, str, tuple[str, ...], str]


@pytest.fixture(scope="module")
def coverage_export():
    return load_export(EXPORT_DIR)


@pytest.fixture(scope="module")
def cell_names(coverage_export) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                location.cell_id
                for subject in coverage_export.subjects
                for location in subject.locations
                if location.cell_id
            }
        )
    )


@pytest.fixture(scope="module")
def contexts(coverage_export):
    return {
        (subject.subject_id, tier): context
        for subject in coverage_export.subjects
        for tier, context in (
            ("t2", build_t2(subject.request, subject)),
            ("t3", build_t3(subject.request, subject, coverage_export.rules)),
        )
    }


@pytest.fixture(scope="module")
def bodies(coverage_export, contexts) -> tuple[Rendered, ...]:
    return tuple(
        (
            subject,
            tier,
            order,
            render_adjudication_body(
                context=contexts[(subject.subject_id, tier)],
                case_id=subject.subject_id,
                options=order,
                model=MODEL,
            ),
        )
        for subject in coverage_export.subjects
        for tier in ("t2", "t3")
        for order in ORDERS
    )


def _keys(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            _keys(value, found)
    elif isinstance(node, list):
        for item in node:
            _keys(item, found)


def _report(violations: list[str], total: int) -> str:
    head = "\n".join(violations[:20])
    tail = "" if len(violations) <= 20 else f"\n… and {len(violations) - 20} more"
    return f"{len(violations)} of {total} bodies violate the invariant:\n{head}{tail}"


def _tag(subject: AdjudicationSubject, tier: str, order: tuple[str, ...]) -> str:
    return f"{subject.subject_id} [{tier} {'/'.join(order)}]"


@pytest.mark.context_isolation
def test_the_sweep_covers_350_subjects_two_tiers_and_three_orders(bodies, cell_names) -> None:
    assert len(bodies) == 350 * 2 * 3
    assert len(cell_names) == 24
    assert len({subject.subject_id for subject, *_ in bodies}) == 350
    assert all(len(subject.locations) == 1 for subject, *_ in bodies)


@pytest.mark.context_isolation
def test_no_cell_name_or_real_identifier_reaches_any_body(bodies, cell_names) -> None:
    violations = []
    for subject, tier, order, body in bodies:
        tag = _tag(subject, tier, order)
        violations.extend(f"{tag}: cell name {name!r}" for name in cell_names if name in body)
        if subject.subject_id in body:
            violations.append(f"{tag}: real subject_id")
        violations.extend(
            f"{tag}: real location_id {location.location_id!r}"
            for location in subject.locations
            if location.location_id in body
        )
    assert violations == [], _report(violations, len(bodies))


@pytest.mark.context_isolation
def test_no_eval_only_key_reaches_any_body_at_any_depth(bodies) -> None:
    violations = []
    for subject, tier, order, body in bodies:
        found: set[str] = set()
        _keys(json.loads(body), found)
        violations.extend(
            f"{_tag(subject, tier, order)}: eval-only key {key!r}"
            for key in EVAL_ONLY_KEYS
            if key in found
        )
    assert violations == [], _report(violations, len(bodies))


@pytest.mark.context_isolation
def test_every_body_has_exactly_the_brief_s_shape(bodies) -> None:
    """Model, one question keyed by the opaque location id, criteria in the run's order."""
    violations = []
    for subject, tier, order, body in bodies:
        tag = _tag(subject, tier, order)
        parsed = json.loads(body)
        if tuple(parsed) != BODY_KEYS:
            violations.append(f"{tag}: body keys {tuple(parsed)}")
            continue
        if parsed["model"] != MODEL:
            violations.append(f"{tag}: model {parsed['model']!r}")
        key = opaque_location_id(subject.locations[0].location_id)
        if list(parsed["questions"]) != [key]:
            violations.append(f"{tag}: question keys {list(parsed['questions'])}")
            continue
        question = parsed["questions"][key]
        if tuple(question) != QUESTION_KEYS:
            violations.append(f"{tag}: question fields {tuple(question)}")
        if question["type"] != "choice" or question["instructions"] != INSTRUCTIONS:
            violations.append(f"{tag}: type or instructions changed")
        if list(question["criteria"].items()) != [(option, None) for option in order]:
            violations.append(f"{tag}: criteria {question['criteria']}")
    assert violations == [], _report(violations, len(bodies))


@pytest.mark.context_isolation
def test_every_state_is_the_object_the_text_prompt_renders(bodies, contexts) -> None:
    """Same object Sonnet read, key order included, with the opaque case id in it."""
    violations = []
    for subject, tier, order, body in bodies:
        tag = _tag(subject, tier, order)
        state = json.loads(body)["state"]
        prompt = build_adjudication_prompt(
            context=contexts[(subject.subject_id, tier)], case_id=subject.subject_id
        )
        if state != json.loads(prompt.split("Context:\n", 1)[1]):
            violations.append(f"{tag}: state differs from the text prompt's context")
        if tuple(state) != STATE_KEYS:
            violations.append(f"{tag}: state keys {tuple(state)}")
        if state.get("case_id") != opaque_case_id(subject.subject_id):
            violations.append(f"{tag}: case id is not the opaque handle")
    assert violations == [], _report(violations, len(bodies))


@pytest.mark.context_isolation
def test_each_body_is_its_own_serialization_and_orders_hash_apart(bodies) -> None:
    """The string is what is hashed and sent; re-serializing it must not change a byte."""
    violations = []
    hashes: dict[tuple[str, str], set[str]] = {}
    for subject, tier, order, body in bodies:
        if serialize_body(json.loads(body)) != body:
            violations.append(f"{_tag(subject, tier, order)}: body is not canonical")
        hashes.setdefault((subject.subject_id, tier), set()).add(prompt_hash(body))
    violations.extend(
        f"{case} {tier}: orders share a hash" for (case, tier), h in hashes.items() if len(h) != 3
    )
    assert violations == [], _report(violations, len(bodies))

"""The A3 control prompt differs from the default T1 prompt only in the emptied `locations` list."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from core.context.tiers import build_t1
from core.export.loader import load_export
from core.model.adapter_common import build_adjudication_prompt

REPO_ROOT = Path(__file__).resolve().parents[2]


def _control_module():
    path = REPO_ROOT / "scripts" / "control_t1_empty_locations.py"
    spec = importlib.util.spec_from_file_location("control_t1_empty_locations", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _split(prompt: str) -> tuple[str, dict]:
    head, body = prompt.split("Context:\n", 1)
    return head, json.loads(body)


def test_control_prompt_is_the_default_prompt_with_locations_emptied() -> None:
    control = _control_module()
    subjects = load_export(REPO_ROOT / "export").subjects
    assert len(subjects) == 350
    for subject in subjects:
        context = build_t1(subject.request, subject)
        default = build_adjudication_prompt(context=context, case_id=subject.subject_id)
        rendered = control.render_empty_locations_prompt(
            context=context, case_id=subject.subject_id
        )
        default_head, default_payload = _split(default)
        head, payload = _split(rendered)
        assert head == default_head, subject.subject_id
        assert default_payload["locations"], subject.subject_id
        assert payload == {**default_payload, "locations": []}, subject.subject_id
        assert rendered == default_head + "Context:\n" + json.dumps(
            {**default_payload, "locations": []}, indent=2
        )
        assert subject.subject_id not in rendered

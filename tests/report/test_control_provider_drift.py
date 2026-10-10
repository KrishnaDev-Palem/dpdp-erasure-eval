"""The provider-drift control's re-sent numbers re-score from the committed control cache."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from core.export.loader import load_export
from runners.adversarial_gate.slice_loader import load_extended_slice

REPO_ROOT = Path(__file__).resolve().parents[2]


def _drift_module():
    path = REPO_ROOT / "scripts" / "control_provider_drift.py"
    spec = importlib.util.spec_from_file_location("control_provider_drift", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resent_numbers_rescore_from_the_committed_drift_cache() -> None:
    drift = _drift_module()
    committed = json.loads(
        (REPO_ROOT / "results" / "control-provider-drift.json").read_text(encoding="utf-8")
    )
    subjects = load_export(REPO_ROOT / "export").subjects
    cases = load_extended_slice(
        REPO_ROOT / "fixtures/adversarial_slice/cases.yaml", verify_seeds=False
    ).cases
    t1 = [
        {k: v for k, v in row.items() if k != "verdicts"}
        for row in drift._t1_per_try(drift.DRIFT_ROOT, subjects)
    ]
    assert t1 == committed["t1"]["resent"]
    assert drift._gate_per_try(drift.DRIFT_ROOT, cases) == committed["gate"]["resent"]
    assert committed["usage"]["t1"]["calls"] == 1050
    assert committed["usage"]["adversarial_gate"]["calls"] == 450

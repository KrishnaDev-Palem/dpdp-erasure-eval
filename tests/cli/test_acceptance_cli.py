"""Acceptance tests for the dpdp-eval CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

ADJUDICATION_JSON_KEYS = {
    "tier",
    "runner_id",
    "model_id",
    "cache_mode",
    "export_agent_sha",
    "primary_sample_index",
    "primary_metrics",
    "confusion_matrix",
    "sample_rollups",
    "variance",
}

GATE_JSON_KEYS = {
    "detection",
    "false_alarm",
    "per_family",
    "sample_index",
}


@pytest.fixture(autouse=True)
def _offline_cache_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE_MODE", "offline")
    monkeypatch.delenv("MODEL_API_KEY", raising=False)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "subcommand",
    ["t1", "t2", "t3", "autonomous"],
)
def test_adjudication_subcommand_exits_zero_and_emits_json_keys(subcommand: str) -> None:
    result = _run_cli(subcommand, "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= ADJUDICATION_JSON_KEYS
    metrics = payload["primary_metrics"]
    assert {"over_erasure", "over_retention", "mis_escalation"} <= set(metrics.keys())
    for metric in ("over_erasure", "over_retention", "mis_escalation"):
        assert "rate" in metrics[metric]
        assert "interval" in metrics[metric]


def test_adversarial_gate_subcommand_exits_zero_and_emits_json_keys() -> None:
    result = _run_cli("adversarial-gate", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= GATE_JSON_KEYS


def test_cli_human_output_when_json_not_set() -> None:
    result = _run_cli("t1")
    assert result.returncode == 0, result.stderr
    assert "Adjudication report" in result.stdout
    assert "Over-erasure" in result.stdout


def test_cli_output_writes_json_file(tmp_path: Path) -> None:
    out_file = tmp_path / "report.json"
    result = _run_cli("t2", "--output", str(out_file))
    assert result.returncode == 0, result.stderr
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["tier"] == "t2"


def test_cli_sample_index_flag() -> None:
    result = _run_cli("t1", "--json", "--sample-index", "2")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["primary_sample_index"] == 2

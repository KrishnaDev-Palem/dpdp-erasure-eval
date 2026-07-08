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


def test_cli_adjudication_human_stdout_includes_required_sections() -> None:
    result = _run_cli("t1")
    assert result.returncode == 0, result.stderr
    for marker in (
        "Adjudication report",
        "Over-erasure",
        "Over-retention",
        "Mis-escalation",
        "Confusion matrix",
        "Cross-sample variance",
    ):
        assert marker in result.stdout


def test_cli_adjudication_human_stdout_section_order() -> None:
    result = _run_cli("t1")
    assert result.returncode == 0, result.stderr
    out = result.stdout

    title = out.index("Adjudication report")
    rates_hdr = out.index("Primary rates (Wilson 95% CI)")
    over_erasure = out.index("Over-erasure")
    over_retention = out.index("Over-retention")
    mis_escalation = out.index("Mis-escalation")
    confusion = out.index("Confusion matrix")
    variance = out.index("Cross-sample variance")

    assert title < rates_hdr < over_erasure < over_retention < mis_escalation < confusion < variance
    assert "sample_rollups" not in out


def test_cli_gate_human_stdout_includes_required_sections() -> None:
    result = _run_cli("adversarial-gate")
    assert result.returncode == 0, result.stderr
    for marker in (
        "Adversarial gate report",
        "Overall rates",
        "Detection",
        "False-alarm",
    ):
        assert marker in result.stdout


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


def test_cli_cache_root_override_uses_custom_path(tmp_path: Path) -> None:
    empty_cache = tmp_path / "empty_cache"
    empty_cache.mkdir()
    result = _run_cli("t1", "--cache-root", str(empty_cache))
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "cache" in combined or "miss" in combined


def test_cli_export_dir_override_uses_custom_path(tmp_path: Path) -> None:
    bad_export = tmp_path / "bad_export"
    bad_export.mkdir()
    result = _run_cli("t1", "--export-dir", str(bad_export))
    assert result.returncode != 0
    combined = (result.stderr + result.stdout).lower()
    assert "export" in combined or "provenance" in combined or "manifest" in combined


def test_cli_explicit_paths_match_defaults() -> None:
    result = _run_cli(
        "t1",
        "--export-dir",
        str(REPO_ROOT / "export"),
        "--cache-root",
        str(REPO_ROOT / "cache"),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["tier"] == "t1"

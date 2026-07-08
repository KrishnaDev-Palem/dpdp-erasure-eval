"""Acceptance tests for the dpdp-eval CLI."""

from __future__ import annotations

import json
import os
import shutil
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


def _run_cli(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env.setdefault("CACHE_MODE", "offline")
    run_env.pop("MODEL_API_KEY", None)
    if env:
        run_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=run_env,
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


def test_cli_adjudication_human_stdout_uses_reader_facing_names() -> None:
    result = _run_cli("t1")
    assert result.returncode == 0, result.stderr
    out_lower = result.stdout.lower()
    assert "request-only" in out_lower
    assert " t1 " not in result.stdout and "— t1" not in result.stdout


@pytest.mark.parametrize(
    ("subcommand", "reader_name"),
    [
        ("t2", "records-augmented"),
        ("t3", "rule-augmented"),
        ("autonomous", "autonomous retrieval"),
    ],
)
def test_cli_reader_facing_names_per_subcommand(subcommand: str, reader_name: str) -> None:
    result = _run_cli(subcommand)
    assert result.returncode == 0, result.stderr
    assert reader_name in result.stdout.lower()


def test_cli_json_and_output_both_emit_json(tmp_path: Path) -> None:
    out_file = tmp_path / "report.json"
    result = _run_cli("t2", "--json", "--output", str(out_file))
    assert result.returncode == 0, result.stderr
    stdout_payload = json.loads(result.stdout)
    file_payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert stdout_payload["tier"] == "t2"


def test_cli_invalid_sample_index_rejected() -> None:
    result = _run_cli("t1", "--sample-index", "9")
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "sample" in combined.lower() or "0" in combined


def test_cli_report_reflects_env_model_id_and_cache_mode(tmp_path: Path) -> None:
    custom_cache = tmp_path / "cache"
    shutil.copytree(REPO_ROOT / "cache" / "primary", custom_cache / "custom-model")
    result = _run_cli(
        "t1",
        "--json",
        "--cache-root",
        str(custom_cache),
        env={"MODEL_ID": "custom-model", "CACHE_MODE": "offline"},
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["model_id"] == "custom-model"
    assert payload["cache_mode"] == "offline"


def test_cli_output_non_writable_parent_fails(tmp_path: Path) -> None:
    bad_path = tmp_path / "missing_parent" / "report.json"
    result = _run_cli("t1", "--output", str(bad_path))
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "missing_parent" in combined or str(bad_path) in combined


def test_cli_deterministic_replay() -> None:
    result1 = _run_cli("t1", "--json")
    result2 = _run_cli("t1", "--json")
    assert result1.returncode == 0, result1.stderr
    assert result2.returncode == 0, result2.stderr
    assert json.loads(result1.stdout) == json.loads(result2.stdout)

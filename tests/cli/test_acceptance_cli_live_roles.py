"""Acceptance tests for dpdp-eval CLI replay against committed live-role cache (Feature 007)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import LIVE_ROLE_SKIP_REASON, live_role_namespace_ready

REPO_ROOT = Path(__file__).resolve().parents[2]

PROVIDER_KEY_VARS = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MODEL_API_KEY")

ADJUDICATION_JSON_KEYS = {
    "tier",
    "runner_id",
    "model_id",
    "cache_mode",
    "sample_rollups",
    "primary_metrics",
}

GATE_JSON_KEYS = {
    "detection",
    "false_alarm",
    "per_family",
    "sample_index",
}

_CLAUDE_READY = live_role_namespace_ready("claude-sonnet-5", "t2") and live_role_namespace_ready(
    "claude-sonnet-5", "autonomous"
)
_GEMINI_READY = live_role_namespace_ready("gemini-3.5-flash", "adversarial_gate")


def _run_cli_live_role(
    *args: str,
    model_id: str,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    for key_var in PROVIDER_KEY_VARS:
        run_env.pop(key_var, None)
    run_env["MODEL_ID"] = model_id
    run_env["CACHE_MODE"] = "offline"
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=run_env,
    )


@pytest.mark.parametrize("subcommand", ["t2", "autonomous"])
def test_cli_claude_sonnet_5_subcommands_exit_zero_and_echo_role(subcommand: str) -> None:
    if not _CLAUDE_READY:
        pytest.skip(LIVE_ROLE_SKIP_REASON)
    result = _run_cli_live_role(subcommand, "--json", model_id="claude-sonnet-5")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= ADJUDICATION_JSON_KEYS
    assert payload["model_id"] == "claude-sonnet-5"
    assert payload["cache_mode"] == "offline"


def test_cli_gemini_flash_adversarial_gate_exits_zero() -> None:
    if not _GEMINI_READY:
        pytest.skip(LIVE_ROLE_SKIP_REASON)
    result = _run_cli_live_role("adversarial-gate", "--json", model_id="gemini-3.5-flash")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload.keys()) >= GATE_JSON_KEYS


@pytest.mark.parametrize(
    ("subcommand", "model_id"),
    [
        ("t2", "claude-sonnet-5"),
        ("autonomous", "claude-sonnet-5"),
        ("adversarial-gate", "gemini-3.5-flash"),
    ],
)
def test_cli_live_role_byte_identical_stdout_on_repeat(subcommand: str, model_id: str) -> None:
    if model_id == "claude-sonnet-5" and not _CLAUDE_READY:
        pytest.skip(LIVE_ROLE_SKIP_REASON)
    if model_id == "gemini-3.5-flash" and not _GEMINI_READY:
        pytest.skip(LIVE_ROLE_SKIP_REASON)
    first = _run_cli_live_role(subcommand, "--json", model_id=model_id)
    second = _run_cli_live_role(subcommand, "--json", model_id=model_id)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout

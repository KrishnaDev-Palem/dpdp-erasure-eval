"""Assert every committed results file embeds the pinned export agent SHA."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
PINNED_SHA_PATH = REPO_ROOT / "export" / "PINNED_AGENT_SHA"


@pytest.fixture(scope="module")
def pinned_agent_sha() -> str:
    return PINNED_SHA_PATH.read_text(encoding="utf-8").strip()


ADJUDICATION_RESULTS = sorted(
    path for path in RESULTS_DIR.glob("*.json") if not path.name.startswith("gate-")
)
GATE_RESULTS = sorted(RESULTS_DIR.glob("gate-*.json"))


@pytest.mark.parametrize(
    "results_file",
    ADJUDICATION_RESULTS,
    ids=lambda path: path.name,
)
def test_adjudication_results_embed_export_agent_sha(
    results_file: Path,
    pinned_agent_sha: str,
) -> None:
    payload = json.loads(results_file.read_text(encoding="utf-8"))
    assert payload["export_agent_sha"] == pinned_agent_sha


@pytest.mark.parametrize(
    "results_file",
    GATE_RESULTS,
    ids=lambda path: path.name,
)
def test_gate_results_embed_export_agent_sha(
    results_file: Path,
    pinned_agent_sha: str,
) -> None:
    payload = json.loads(results_file.read_text(encoding="utf-8"))
    assert payload["export_agent_sha"] == pinned_agent_sha

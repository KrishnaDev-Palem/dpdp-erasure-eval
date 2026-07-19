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


@pytest.mark.parametrize(
    "results_file",
    sorted(RESULTS_DIR.glob("*.json")),
    ids=lambda path: path.name,
)
def test_results_file_embeds_export_agent_sha(
    results_file: Path,
    pinned_agent_sha: str,
) -> None:
    payload = json.loads(results_file.read_text(encoding="utf-8"))
    assert payload["export_agent_sha"] == pinned_agent_sha

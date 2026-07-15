"""Repository-wide pytest helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "cache"

LIVE_ROLE_SKIP_REASON = "Committed live-role cache namespace is missing or empty."


@pytest.fixture(autouse=True)
def _default_primary_model_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep suite defaults on FakeModelSeam primary cache unless a test overrides."""
    monkeypatch.setenv("MODEL_ID", "primary")


def live_role_namespace_ready(*parts: str) -> bool:
    namespace = CACHE_DIR.joinpath(*parts)
    return namespace.is_dir() and any(namespace.rglob("*.json"))

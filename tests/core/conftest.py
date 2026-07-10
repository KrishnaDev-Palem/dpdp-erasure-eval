from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO_ROOT / "export"
CACHE_DIR = REPO_ROOT / "cache"

ENV_VARS = (
    "MODEL_ID",
    "CACHE_MODE",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MODEL_API_KEY",
)


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def export_dir() -> Path:
    return EXPORT_DIR


@pytest.fixture
def cache_dir() -> Path:
    return CACHE_DIR


@pytest.fixture
def model_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Clear model-related env vars for isolated factory/credential tests."""
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch

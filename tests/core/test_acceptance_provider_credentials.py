"""Acceptance tests for provider credential resolution."""

from __future__ import annotations

import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from core.exceptions import ConfigurationError
from core.model.credentials import resolve_provider_api_key


def test_anthropic_key_from_anthropic_api_key(model_env: pytest.MonkeyPatch) -> None:
    model_env.setenv("ANTHROPIC_API_KEY", "sk-anthropic")
    policy = resolve_provider_api_key(provider="anthropic")
    assert policy.api_key == "sk-anthropic"
    assert policy.source_env_var == "ANTHROPIC_API_KEY"
    assert policy.used_legacy_fallback is False


def test_gemini_key_from_gemini_api_key(model_env: pytest.MonkeyPatch) -> None:
    model_env.setenv("GEMINI_API_KEY", "gem-key")
    policy = resolve_provider_api_key(provider="google")
    assert policy.api_key == "gem-key"
    assert policy.source_env_var == "GEMINI_API_KEY"
    assert policy.used_legacy_fallback is False


def test_legacy_model_api_key_fallback_emits_deprecation_warning(
    model_env: pytest.MonkeyPatch,
) -> None:
    model_env.setenv("MODEL_API_KEY", "legacy-key")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        policy = resolve_provider_api_key(provider="anthropic")
    assert policy.api_key == "legacy-key"
    assert policy.used_legacy_fallback is True
    assert any(
        issubclass(item.category, DeprecationWarning) and "ANTHROPIC_API_KEY" in str(item.message)
        for item in caught
    )


def test_provider_specific_key_wins_when_both_set(model_env: pytest.MonkeyPatch) -> None:
    model_env.setenv("ANTHROPIC_API_KEY", "preferred")
    model_env.setenv("MODEL_API_KEY", "legacy")
    policy = resolve_provider_api_key(provider="anthropic")
    assert policy.api_key == "preferred"
    assert policy.used_legacy_fallback is False


def test_missing_credential_raises_configuration_error_naming_required_vars(
    model_env: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
        resolve_provider_api_key(provider="anthropic")
    with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
        resolve_provider_api_key(provider="google")


def test_env_example_documents_provider_keys_and_cache_mode(repo_root: Path) -> None:
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MODEL_ID", "CACHE_MODE"):
        assert var in env_example
    assert "MODEL_API_KEY" not in env_example
    for line in env_example.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            _, value = line.split("=", 1)
            assert value.strip() == "" or value.strip() in {"primary", "offline"}


def test_offline_pytest_never_requires_provider_keys(model_env: pytest.MonkeyPatch) -> None:
    for var in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "MODEL_API_KEY"):
        model_env.delenv(var, raising=False)
    from core.model import create_model_seam

    seam = create_model_seam()
    assert seam is not None


def test_default_pytest_excludes_live_marker(repo_root: Path) -> None:
    """Merge gate must not collect @pytest.mark.live tests (FR-010, FR-011)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/live", "--collect-only", "-q"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "deselected" in combined
    assert "no tests collected" in combined

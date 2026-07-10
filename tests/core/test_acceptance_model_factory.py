"""Acceptance tests for model seam factory resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.exceptions import ConfigurationError
from core.model import FakeModelSeam, create_model_seam, get_role_descriptor, list_role_descriptors
from core.model.anthropic_adapter import AnthropicModelSeam
from core.model.gemini_adapter import GeminiModelSeam


def test_role_registry_lists_primary_claude_and_gemini_roles() -> None:
    role_ids = {descriptor.role_id for descriptor in list_role_descriptors()}
    assert role_ids == {"primary", "claude-sonnet-5", "gemini-3.5-flash"}


def test_live_roles_have_pinned_provider_model_ids() -> None:
    claude = get_role_descriptor("claude-sonnet-5")
    gemini = get_role_descriptor("gemini-3.5-flash")
    assert claude.provider_model_id == "claude-sonnet-5"
    assert gemini.provider_model_id == "gemini-3.5-flash"
    assert get_role_descriptor("primary").provider_model_id is None


def test_offline_factory_returns_fake_model_seam(model_env: pytest.MonkeyPatch) -> None:
    model_env.setenv("CACHE_MODE", "offline")
    seam = create_model_seam()
    assert isinstance(seam, FakeModelSeam)


def test_offline_factory_returns_fake_even_when_api_keys_set(
    model_env: pytest.MonkeyPatch,
) -> None:
    model_env.setenv("CACHE_MODE", "offline")
    model_env.setenv("ANTHROPIC_API_KEY", "sk-test")
    model_env.setenv("GEMINI_API_KEY", "gem-test")
    seam = create_model_seam()
    assert isinstance(seam, FakeModelSeam)


@pytest.mark.parametrize("model_id", ["primary", "claude-sonnet-5", "gemini-3.5-flash"])
def test_offline_factory_respects_any_model_id(
    model_env: pytest.MonkeyPatch,
    model_id: str,
) -> None:
    model_env.setenv("CACHE_MODE", "offline")
    model_env.setenv("MODEL_ID", model_id)
    seam = create_model_seam()
    assert isinstance(seam, FakeModelSeam)


def test_refresh_returns_anthropic_adapter_for_claude_role(
    model_env: pytest.MonkeyPatch,
) -> None:
    model_env.setenv("CACHE_MODE", "refresh")
    model_env.setenv("MODEL_ID", "claude-sonnet-5")
    model_env.setenv("ANTHROPIC_API_KEY", "sk-test")
    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.return_value = MagicMock()
        seam = create_model_seam()
    assert isinstance(seam, AnthropicModelSeam)


def test_refresh_returns_gemini_adapter_for_gemini_role(
    model_env: pytest.MonkeyPatch,
) -> None:
    model_env.setenv("CACHE_MODE", "refresh")
    model_env.setenv("MODEL_ID", "gemini-3.5-flash")
    model_env.setenv("GEMINI_API_KEY", "gem-test")
    with patch("google.genai.Client") as mock_cls:
        mock_cls.return_value = MagicMock()
        seam = create_model_seam()
    assert isinstance(seam, GeminiModelSeam)


def test_refresh_primary_raises_configuration_error(model_env: pytest.MonkeyPatch) -> None:
    model_env.setenv("CACHE_MODE", "refresh")
    model_env.setenv("MODEL_ID", "primary")
    with pytest.raises(ConfigurationError, match="primary"):
        create_model_seam()


def test_refresh_unknown_model_id_raises_configuration_error(
    model_env: pytest.MonkeyPatch,
) -> None:
    model_env.setenv("CACHE_MODE", "refresh")
    model_env.setenv("MODEL_ID", "unknown-model")
    with pytest.raises(ConfigurationError, match="claude-sonnet-5"):
        create_model_seam()


@pytest.mark.parametrize(
    ("model_id", "expected_var"),
    [
        ("claude-sonnet-5", "ANTHROPIC_API_KEY"),
        ("gemini-3.5-flash", "GEMINI_API_KEY"),
    ],
)
def test_refresh_missing_credential_raises_before_network(
    model_env: pytest.MonkeyPatch,
    model_id: str,
    expected_var: str,
) -> None:
    model_env.setenv("CACHE_MODE", "refresh")
    model_env.setenv("MODEL_ID", model_id)
    with pytest.raises(ConfigurationError, match=expected_var):
        create_model_seam()


def test_factory_resolution_performs_no_network_io(model_env: pytest.MonkeyPatch) -> None:
    model_env.setenv("CACHE_MODE", "refresh")
    model_env.setenv("MODEL_ID", "claude-sonnet-5")
    model_env.setenv("ANTHROPIC_API_KEY", "sk-test")
    with (
        patch("anthropic.Anthropic") as anthropic_cls,
        patch("google.genai.Client") as gemini_cls,
    ):
        anthropic_cls.return_value = MagicMock()
        create_model_seam()
        anthropic_cls.return_value.messages.create.assert_not_called()
        gemini_cls.assert_not_called()


def test_runner_explicit_seam_injection_bypasses_factory(
    export_dir,
    cache_dir,
) -> None:
    from core.model import FakeModelSeam
    from runners.t2 import run_t2_sweep

    fake_seam = FakeModelSeam()
    with patch("core.model.factory.create_model_seam") as factory_mock:
        result = run_t2_sweep(seam=fake_seam, export_dir=export_dir, cache_root=cache_dir)
    factory_mock.assert_not_called()
    assert result.tier == "t2"

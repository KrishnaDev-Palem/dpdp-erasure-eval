"""Model seam factory — selects offline fake or live adapter by configuration."""

from __future__ import annotations

from core.exceptions import ConfigurationError
from core.model.credentials import resolve_provider_api_key
from core.model.fake import FakeModelSeam
from core.model.roles import LIVE_ROLE_IDS, get_role_descriptor
from core.model.seam import ModelConfig, ModelSeam, load_model_config


def create_model_seam(*, config: ModelConfig | None = None) -> ModelSeam:
    """Return the model seam for the current cache mode and model role."""
    resolved = config or load_model_config()

    if resolved.cache_mode == "offline":
        return FakeModelSeam()

    if resolved.cache_mode != "refresh":
        raise ConfigurationError(
            f"Invalid CACHE_MODE {resolved.cache_mode!r}. Expected 'offline' or 'refresh'."
        )

    if resolved.model_id == "primary":
        raise ConfigurationError(
            "MODEL_ID 'primary' has no live adapter. "
            f"Use a supported live role: {', '.join(sorted(LIVE_ROLE_IDS))}"
        )

    descriptor = get_role_descriptor(resolved.model_id)
    if descriptor.provider == "test" or descriptor.provider_model_id is None:
        raise ConfigurationError(
            f"MODEL_ID {resolved.model_id!r} is not a live role. "
            f"Supported live roles: {', '.join(sorted(LIVE_ROLE_IDS))}"
        )

    credential = resolve_provider_api_key(provider=descriptor.provider)

    if descriptor.provider == "anthropic":
        from core.model.anthropic_adapter import AnthropicModelSeam, LiveAdapterConfig

        return AnthropicModelSeam(
            LiveAdapterConfig(
                role_id=descriptor.role_id,
                provider_model_id=descriptor.provider_model_id,
                api_key=credential.api_key,
            )
        )

    if descriptor.provider == "google":
        from core.model.gemini_adapter import GeminiModelSeam, LiveAdapterConfig

        return GeminiModelSeam(
            LiveAdapterConfig(
                role_id=descriptor.role_id,
                provider_model_id=descriptor.provider_model_id,
                api_key=credential.api_key,
            )
        )

    raise ConfigurationError(f"Unsupported provider {descriptor.provider!r}")

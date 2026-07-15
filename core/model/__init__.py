"""Injectable model seam for adjudication and adversarial classification."""

from core.model.anthropic_adapter import AnthropicModelSeam
from core.model.anthropic_adapter import LiveAdapterConfig as AnthropicLiveAdapterConfig
from core.model.credentials import ProviderCredentialPolicy, resolve_provider_api_key
from core.model.factory import create_model_seam
from core.model.fake import FakeModelSeam
from core.model.gemini_adapter import GeminiModelSeam
from core.model.gemini_adapter import LiveAdapterConfig as GeminiLiveAdapterConfig
from core.model.roles import ModelRoleDescriptor, get_role_descriptor, list_role_descriptors
from core.model.seam import ModelSeam, load_model_config

__all__ = [
    "AnthropicLiveAdapterConfig",
    "AnthropicModelSeam",
    "FakeModelSeam",
    "GeminiLiveAdapterConfig",
    "GeminiModelSeam",
    "LiveAdapterConfig",
    "ModelRoleDescriptor",
    "ModelSeam",
    "ProviderCredentialPolicy",
    "create_model_seam",
    "get_role_descriptor",
    "list_role_descriptors",
    "load_model_config",
    "resolve_provider_api_key",
]

# Backward-compatible alias for either adapter config type.
LiveAdapterConfig = AnthropicLiveAdapterConfig

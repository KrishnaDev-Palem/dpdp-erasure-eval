"""Static registry mapping harness model roles to provider metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.exceptions import ConfigurationError

ProviderKind = Literal["anthropic", "google", "typesafe", "test"]


@dataclass(frozen=True)
class ModelRoleDescriptor:
    role_id: str
    provider: ProviderKind
    provider_model_id: str | None
    credential_env_vars: tuple[str, ...]


_ROLE_REGISTRY: dict[str, ModelRoleDescriptor] = {
    "primary": ModelRoleDescriptor(
        role_id="primary",
        provider="test",
        provider_model_id=None,
        credential_env_vars=(),
    ),
    "claude-sonnet-5": ModelRoleDescriptor(
        role_id="claude-sonnet-5",
        provider="anthropic",
        provider_model_id="claude-sonnet-5",
        credential_env_vars=("ANTHROPIC_API_KEY",),
    ),
    "gemini-3.5-flash": ModelRoleDescriptor(
        role_id="gemini-3.5-flash",
        provider="google",
        provider_model_id="gemini-3.5-flash",
        credential_env_vars=("GEMINI_API_KEY",),
    ),
    # A decision model, not a text model: it does not implement `ModelSeam` and runs only
    # through `scripts/decision_model_run.py`. See `briefs/decision-model-run.md`.
    "jev-1.13.0": ModelRoleDescriptor(
        role_id="jev-1.13.0",
        provider="typesafe",
        provider_model_id="jev-1.13.0",
        credential_env_vars=("TYPESAFE_API_KEY",),
    ),
}

# Roles the model seam can serve live. The TypeSafe role is registered but is not one of
# them, so no error message offers it as a value for MODEL_ID.
LIVE_ROLE_IDS: frozenset[str] = frozenset(
    role_id
    for role_id, descriptor in _ROLE_REGISTRY.items()
    if descriptor.provider not in {"test", "typesafe"}
)


def get_role_descriptor(role_id: str) -> ModelRoleDescriptor:
    descriptor = _ROLE_REGISTRY.get(role_id)
    if descriptor is None:
        supported = ", ".join(sorted(LIVE_ROLE_IDS))
        raise ConfigurationError(f"Unknown MODEL_ID {role_id!r}. Supported live roles: {supported}")
    return descriptor


def list_role_descriptors() -> list[ModelRoleDescriptor]:
    return list(_ROLE_REGISTRY.values())

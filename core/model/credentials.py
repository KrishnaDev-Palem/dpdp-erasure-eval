"""Provider API key resolution with precedence and deprecation policy."""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from typing import Literal

from core.exceptions import ConfigurationError

ProviderName = Literal["anthropic", "google"]

_LEGACY_ENV_VAR = "MODEL_API_KEY"

_PREFERRED_ENV_VARS: dict[ProviderName, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
}


@dataclass(frozen=True)
class ProviderCredentialPolicy:
    provider: ProviderName
    api_key: str
    source_env_var: str
    used_legacy_fallback: bool


def resolve_provider_api_key(*, provider: ProviderName) -> ProviderCredentialPolicy:
    preferred_var = _PREFERRED_ENV_VARS[provider]
    preferred_value = os.environ.get(preferred_var, "").strip()
    legacy_value = os.environ.get(_LEGACY_ENV_VAR, "").strip()

    if preferred_value:
        return ProviderCredentialPolicy(
            provider=provider,
            api_key=preferred_value,
            source_env_var=preferred_var,
            used_legacy_fallback=False,
        )

    if legacy_value:
        warnings.warn(
            f"Using deprecated {_LEGACY_ENV_VAR} for {provider} provider. "
            f"Set {preferred_var} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ProviderCredentialPolicy(
            provider=provider,
            api_key=legacy_value,
            source_env_var=_LEGACY_ENV_VAR,
            used_legacy_fallback=True,
        )

    raise ConfigurationError(
        f"Missing credential for {provider} provider. "
        f"Set {preferred_var} (preferred) or {_LEGACY_ENV_VAR} (deprecated fallback)."
    )

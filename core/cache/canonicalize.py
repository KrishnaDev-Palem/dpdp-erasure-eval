"""Canonical JSON serialization for stable prompt hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.types import ContextBundle


def _canonicalize_value(value: Any) -> Any:
    if isinstance(value, ContextBundle):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _canonicalize_value(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_canonicalize_value(item) for item in value]
    return value


def canonicalize(context: ContextBundle | dict[str, Any]) -> str:
    """Return compact JSON with sorted keys for stable hashing."""
    payload = _canonicalize_value(context)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def prompt_hash(context: ContextBundle | dict[str, Any]) -> str:
    """Return SHA-256 hex digest of canonical context JSON."""
    digest = hashlib.sha256(canonicalize(context).encode("utf-8"))
    return digest.hexdigest()

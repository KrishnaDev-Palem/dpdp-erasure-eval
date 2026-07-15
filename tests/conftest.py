"""Repository-wide pytest helpers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "cache"

LIVE_ROLE_SKIP_REASON = (
    "Live-role cache invalidated by Feature 008 export swap; "
    "re-seed deferred to Feature 007 follow-up."
)


def live_role_namespace_ready(*parts: str) -> bool:
    namespace = CACHE_DIR.joinpath(*parts)
    return namespace.is_dir() and any(namespace.rglob("*.json"))

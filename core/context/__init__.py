"""Tier-appropriate context assembly for model prompts."""

from core.context.tiers import build_t1, build_t2, build_t3

__all__ = ["build_t1", "build_t2", "build_t3"]

"""Adjudication and adversarial scoring primitives."""

from core.scoring.adjudication import score_adjudication, score_adjudication_grouped
from core.scoring.adversarial import score_adversarial

__all__ = ["score_adjudication", "score_adjudication_grouped", "score_adversarial"]

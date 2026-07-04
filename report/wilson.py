"""Wilson score confidence intervals for proportion rates."""

from __future__ import annotations

import math

from core.types import Rate
from report.types import WilsonInterval

DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_Z = 1.96


def wilson_interval(
    rate: Rate,
    *,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
    z: float = DEFAULT_Z,
) -> WilsonInterval:
    if rate.denominator == 0:
        return WilsonInterval(lower=None, upper=None, confidence_level=confidence_level)
    n = rate.denominator
    p_hat = rate.numerator / n
    z2 = z * z
    center = (p_hat + z2 / (2 * n)) / (1 + z2 / n)
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))) / (1 + z2 / n)
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return WilsonInterval(lower=lower, upper=upper, confidence_level=confidence_level)

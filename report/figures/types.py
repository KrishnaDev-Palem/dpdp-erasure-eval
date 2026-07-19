"""Input types for the report figures module."""

from __future__ import annotations

from dataclasses import dataclass, field

from report.adjudication_types import TierAdjudicationReportTables
from report.types import GateReportTables

CONTEXT_TIERS: tuple[str, ...] = ("t1", "t2", "t3")
TIER_DISPLAY: dict[str, str] = {
    "t1": "T1",
    "t2": "T2",
    "t3": "T3",
}

LANE_DISPLAY: dict[str, str] = {
    "erase": "erase",
    "retain": "retain-with-reason",
    "escalate": "escalate",
}

VERDICT_LANES_ORDERED: tuple[str, ...] = ("erase", "retain", "escalate")

FAMILY_DISPLAY: dict[str, str] = {
    "direct_override": "direct override",
    "authority_spoof": "authority spoof",
    "obfuscated_injection": "obfuscated injection",
    "scope_expansion": "scope expansion",
    "exfiltration": "exfiltration",
}

AGREEMENT_BUCKETS: tuple[str, ...] = ("5/5 unanimous", "4/5", "3/5", "split")


@dataclass(frozen=True)
class VerdictAgreementDistribution:
    """Per-tier share of cases at each sample-agreement bucket."""

    tier: str
    bucket_counts: dict[str, int]
    total_cases: int


@dataclass(frozen=True)
class AdjudicationFigureData:
    tier_reports: dict[str, TierAdjudicationReportTables]
    variance_by_tier: dict[str, VerdictAgreementDistribution]


@dataclass(frozen=True)
class GateFigureData:
    report: GateReportTables


@dataclass(frozen=True)
class FigureInputs:
    adjudication: AdjudicationFigureData | None = None
    gate: GateFigureData | None = None


@dataclass
class FigureGenerationResult:
    written: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

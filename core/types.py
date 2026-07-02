"""Shared domain types for the evaluation harness."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["erase", "retain", "escalate"]
Basis = Literal[
    "explicit_erasure_right",
    "purpose_fulfilled",
    "consent_withdrawn",
    "inactivity",
]
ClassifierOutcome = Literal["clean", "adversarial"]
SeedLabel = Literal["attack", "benign"]
Tier = Literal["t1", "t2", "t3"]

VERDICT_LANES: tuple[Verdict, Verdict, Verdict] = ("erase", "retain", "escalate")


class Rate(BaseModel):
    model_config = ConfigDict(frozen=True)

    numerator: int
    denominator: int
    value: float | None


class ErasureRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    subject_id: str
    type: str
    basis: Basis
    as_of: str


class ExpectedLabel(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    anchor_resolvable: bool
    verdict: Verdict
    cited_floors: list[str] = Field(default_factory=list)


class LabeledLocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    location_id: str
    entity: str
    expected: ExpectedLabel


class AdjudicationSubject(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_id: str
    tags: list[str] = Field(default_factory=list)
    request: ErasureRequest
    locations: list[LabeledLocation] = Field(default_factory=list)


class RetentionFloorRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    floor_id: str
    minimum_period: str
    statute_citation: str


class GovernanceMapEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    floors: list[str]
    anchor_selector: str


class AdversarialSeedCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    surface: str
    text: str
    label: SeedLabel
    family: str | None = None


class ModelVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    location_id: str
    verdict: Verdict
    detail: str | None = None


class ClassifierResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome: ClassifierOutcome
    detail: str | None = None


class ContextBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    tier: Tier
    request: ErasureRequest
    locations: list[dict[str, Any]] = Field(default_factory=list)
    retention_floors: list[RetentionFloorRule] = Field(default_factory=list)
    governance_map: list[GovernanceMapEntry] = Field(default_factory=list)


class CacheKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    runner_id: str
    case_id: str
    prompt_hash: str
    sample_index: int


class CacheEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: CacheKey
    raw_response: dict[str, Any]
    recorded_at: str
    tool_calls: list[Any] = Field(default_factory=list)


class ExportManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    export_version: str
    generated_at: str
    as_of: str
    agent_commit_sha: str
    agent_commit_url: str


class RulesCorpus(BaseModel):
    model_config = ConfigDict(frozen=True)

    retention_floors: list[RetentionFloorRule]
    governance_map: list[GovernanceMapEntry]


class AdjudicationScoringResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    confusion_matrix: dict[str, dict[str, int]]
    over_erasure_rate: Rate
    over_retention_rate: Rate
    mis_escalation_rate: Rate
    total_cases: int


class AdversarialScoringResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    detection_rate: Rate
    false_alarm_rate: Rate
    per_family: dict[str, Rate]

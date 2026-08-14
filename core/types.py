"""Shared domain types for the evaluation harness."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

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
EntityType = Literal["customers", "transactions", "marketing_consents", "kyc_documents"]
BoundaryFlag = Literal["none", "elapsed_by_1d", "unelapsed_by_1d"]
Split = Literal["train", "eval"]
CollisionArity = Literal[0, 1, 4]

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


class Strata(BaseModel):
    """Agent export-schema 1.0.0 `strata` object. Names are locked; do not rename."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: EntityType
    floor_set: list[str]
    collision_arity: CollisionArity
    anchor_computable: bool
    boundary_flag: BoundaryFlag
    trigger_shape: str
    re_engagement: bool
    split: Split


STRATA_GROUP_FIELDS: tuple[str, ...] = (
    "entity_type",
    "floor_set",
    "collision_arity",
    "anchor_computable",
    "boundary_flag",
    "trigger_shape",
    "re_engagement",
    "split",
)


class LabeledLocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    location_id: str
    entity: str
    expected: ExpectedLabel
    strata: Strata | None = None
    cell_id: str | None = None
    parent_customer: dict[str, Any] | None = None
    latest_txn_date: str | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_coverage_fields(self, handler: Any) -> dict[str, Any]:
        """Keep v1 location dumps byte-stable when coverage fields are unset."""
        data = handler(self)
        for key in ("strata", "cell_id", "parent_customer", "latest_txn_date"):
            if data.get(key) is None:
                data.pop(key, None)
        return data


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


class GroupedAdjudicationScoring(BaseModel):
    """`score_adjudication` applied to pairs grouped by cell_id and strata fields."""

    model_config = ConfigDict(frozen=True)

    by_cell: dict[str, AdjudicationScoringResult] = Field(default_factory=dict)
    by_stratum: dict[str, dict[str, AdjudicationScoringResult]] = Field(default_factory=dict)


RetrievalToolName = Literal[
    "get_location_records",
    "get_retention_floors",
    "get_governance_map",
]


class ToolCallTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    tool_name: RetrievalToolName
    arguments: dict[str, Any]
    result_summary: dict[str, Any]

    @model_validator(mode="after")
    def _validate_no_expected(self) -> ToolCallTrace:
        if self.sequence < 0:
            raise ValueError("sequence must be >= 0")
        if _payload_contains_expected_key(self.model_dump(mode="json")):
            raise ValueError("tool call trace must not contain expected")
        return self


def _payload_contains_expected_key(payload: object) -> bool:
    if isinstance(payload, dict):
        if "expected" in payload:
            return True
        return any(_payload_contains_expected_key(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_payload_contains_expected_key(item) for item in payload)
    return False


class AdjudicationSessionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdicts: list[ModelVerdict] = Field(default_factory=list)
    raw_verdicts: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[ToolCallTrace]


class AdversarialScoringResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    detection_rate: Rate
    false_alarm_rate: Rate
    per_family: dict[str, Rate]

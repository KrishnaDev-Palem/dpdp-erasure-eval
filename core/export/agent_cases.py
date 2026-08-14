"""Map agent export-schema 1.0.0 cases onto eval adjudication subjects."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from core.exceptions import ExportLoadError
from core.export.coverage import GENERATOR_AS_OF
from core.types import AdjudicationSubject, ExpectedLabel, LabeledLocation, Strata

# Same partition as agent `dpdp.rules.resolver.categorize`. Do not invent strings.
PAYMENT_INSTRUMENT_TYPES = frozenset({"upi", "card", "netbanking", "neft", "imps", "wallet"})
SECURITIES_INSTRUMENT_TYPES = frozenset({"equity", "mutual_fund", "bond", "etf"})


def categorize(record: Mapping[str, Any]) -> str:
    """Derive `expected.category` the same way the agent `categorize()` does."""
    try:
        entity = record["entity"]
    except KeyError as exc:
        raise ExportLoadError("Agent case record is missing entity") from exc
    if entity == "customers":
        return "customer"
    if entity == "marketing_consents":
        return "marketing_consent"
    if entity == "kyc_documents":
        return "kyc_document"
    if entity == "transactions":
        instrument = record.get("instrument_type")
        if instrument in PAYMENT_INSTRUMENT_TYPES:
            return "payment_transaction"
        if instrument in SECURITIES_INSTRUMENT_TYPES:
            return "securities_transaction"
        raise ExportLoadError(f"unknown instrument_type: {instrument}")
    raise ExportLoadError(f"unknown entity: {entity}")


def is_agent_case(item: object) -> bool:
    """True when the item is an unmapped agent case, not a v1/mapped subject."""
    return (
        isinstance(item, dict)
        and "case_id" in item
        and "record" in item
        and "oracle" in item
        and "locations" not in item
    )


def subjects_from_agent_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    as_of: str = GENERATOR_AS_OF,
) -> list[AdjudicationSubject]:
    """One generated case → one person, one scored location. `location_id` is `case_id`."""
    if not cases:
        raise ExportLoadError("Agent case list is empty")
    return [_subject_from_agent_case(case, as_of=as_of) for case in cases]


def load_agent_cases(path: Path, *, as_of: str = GENERATOR_AS_OF) -> list[AdjudicationSubject]:
    """Parse a JSON or YAML file of agent cases (or already-mapped subjects)."""
    if not path.is_file():
        raise ExportLoadError(f"Missing agent case file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            data: object = json.loads(text)
        else:
            data = yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ExportLoadError(f"Failed to read agent cases from {path}") from exc
    return parse_subject_items(_extract_case_list(data), as_of=as_of)


def parse_subject_items(
    items: Sequence[object],
    *,
    as_of: str = GENERATOR_AS_OF,
) -> list[AdjudicationSubject]:
    """Parse a mixed list of agent cases and already-mapped subjects."""
    if not items:
        raise ExportLoadError("Adjudication export contains no subjects")
    subjects: list[AdjudicationSubject] = []
    for item in items:
        if is_agent_case(item):
            subjects.append(_subject_from_agent_case(item, as_of=as_of))
            continue
        try:
            subjects.append(AdjudicationSubject.model_validate(item))
        except ValidationError as exc:
            raise ExportLoadError("Invalid adjudication subject in export") from exc
    return subjects


def _extract_case_list(data: object) -> list[object]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "subjects" in data:
            raw = data["subjects"]
        elif "cases" in data:
            raw = data["cases"]
        else:
            raise ExportLoadError(
                "Adjudication export must be a list or contain a subjects or cases key"
            )
        if not isinstance(raw, list):
            raise ExportLoadError("Adjudication export subjects/cases must be a list")
        return raw
    raise ExportLoadError("Adjudication export must be a list or a mapping")


def _subject_from_agent_case(case: Mapping[str, Any], *, as_of: str) -> AdjudicationSubject:
    try:
        case_id = case["case_id"]
        subject_id = case["subject_id"]
        record = case["record"]
        request = case["request"]
        oracle = case["oracle"]
    except KeyError as exc:
        raise ExportLoadError(f"Agent case missing required field: {exc.args[0]}") from exc

    if "strata" not in case or case["strata"] is None:
        raise ExportLoadError(f"Agent case {case_id!r} is missing strata")
    if not isinstance(record, Mapping):
        raise ExportLoadError(f"Agent case {case_id!r} record must be a mapping")
    if not isinstance(request, Mapping):
        raise ExportLoadError(f"Agent case {case_id!r} request must be a mapping")
    if not isinstance(oracle, Mapping):
        raise ExportLoadError(f"Agent case {case_id!r} oracle must be a mapping")

    try:
        strata = Strata.model_validate(case["strata"])
    except ValidationError as exc:
        raise ExportLoadError(f"Invalid strata on agent case {case_id!r}") from exc

    escalate_reason = oracle.get("escalate_reason")
    anchor_resolvable = escalate_reason != "uncomputable_anchor"
    if anchor_resolvable != strata.anchor_computable:
        raise ExportLoadError(
            f"Agent case {case_id!r} oracle escalate_reason does not match strata.anchor_computable"
        )

    try:
        verdict = oracle["verdict"]
    except KeyError as exc:
        raise ExportLoadError(f"Agent case {case_id!r} oracle is missing verdict") from exc

    cell_id = case.get("cell_id")
    location_payload: dict[str, Any] = {
        key: value for key, value in record.items() if key not in {"expected"}
    }
    location_payload["location_id"] = case_id
    location_payload["entity"] = record.get("entity")
    location_payload["expected"] = ExpectedLabel(
        category=categorize(record),
        anchor_resolvable=anchor_resolvable,
        verdict=verdict,
        cited_floors=list(oracle.get("cited_floors") or []),
    )
    location_payload["strata"] = strata
    if cell_id is not None:
        location_payload["cell_id"] = cell_id

    parent_customer = case.get("parent_customer")
    if parent_customer is not None:
        if not isinstance(parent_customer, Mapping):
            raise ExportLoadError(f"Agent case {case_id!r} parent_customer must be a mapping")
        location_payload["parent_customer"] = dict(parent_customer)

    context = case.get("context")
    if context is not None:
        if not isinstance(context, Mapping):
            raise ExportLoadError(f"Agent case {case_id!r} context must be a mapping")
        latest_txn_date = context.get("latest_txn_date")
        if latest_txn_date is not None:
            location_payload["latest_txn_date"] = latest_txn_date

    request_as_of = request.get("as_of") or as_of
    try:
        location = LabeledLocation.model_validate(location_payload)
        return AdjudicationSubject(
            subject_id=subject_id,
            tags=[cell_id] if isinstance(cell_id, str) and cell_id else [],
            request={
                "subject_id": subject_id,
                "type": request.get("type", "erasure"),
                "basis": request["basis"],
                "as_of": request_as_of,
            },
            locations=[location],
        )
    except (ValidationError, KeyError) as exc:
        raise ExportLoadError(f"Invalid agent case {case_id!r}") from exc

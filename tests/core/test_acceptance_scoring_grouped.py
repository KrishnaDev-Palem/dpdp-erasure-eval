"""Acceptance tests for per-cell and per-stratum adjudication grouping."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.export import load_agent_cases, load_export
from core.scoring import score_adjudication, score_adjudication_grouped
from core.scoring.adjudication import stratum_value_key
from core.types import STRATA_GROUP_FIELDS, LabeledLocation, ModelVerdict

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "agent_cases.yaml"


def _fixture_locations() -> dict[str, LabeledLocation]:
    subjects = load_agent_cases(FIXTURE_PATH)
    return {
        location.location_id: location for subject in subjects for location in subject.locations
    }


def _pairs_from_locations(
    locations: dict[str, LabeledLocation],
    *,
    predicted: dict[str, str] | None = None,
) -> list[tuple[ModelVerdict, object]]:
    overrides = predicted or {}
    pairs: list[tuple[ModelVerdict, object]] = []
    for location_id, location in locations.items():
        verdict = overrides.get(location_id, location.expected.verdict)
        pairs.append(
            (
                ModelVerdict(location_id=location_id, verdict=verdict),  # type: ignore[arg-type]
                location.expected,
            )
        )
    return pairs


def test_grouped_rates_match_hand_scored_partition() -> None:
    locations = _fixture_locations()
    # Flip two verdicts so groups are not all-correct.
    predicted = {
        "ordinary_erase_payment:00000": "retain",
        "uncomputable_customer:00000": "erase",
    }
    pairs = _pairs_from_locations(locations, predicted=predicted)
    grouped = score_adjudication_grouped(pairs, locations)

    by_cell: dict[str, list] = {}
    by_stratum: dict[str, dict[str, list]] = {field: {} for field in STRATA_GROUP_FIELDS}
    for pair in pairs:
        location = locations[pair[0].location_id]
        assert location.cell_id is not None
        by_cell.setdefault(location.cell_id, []).append(pair)
        assert location.strata is not None
        payload = location.strata.model_dump()
        for field in STRATA_GROUP_FIELDS:
            key = stratum_value_key(payload[field])
            by_stratum[field].setdefault(key, []).append(pair)

    for cell_id, cell_pairs in by_cell.items():
        assert grouped.by_cell[cell_id] == score_adjudication(cell_pairs)
    for field, groups in by_stratum.items():
        for key, field_pairs in groups.items():
            assert grouped.by_stratum[field][key] == score_adjudication(field_pairs)


def test_grouping_keys_cover_cell_id_and_every_strata_field() -> None:
    locations = _fixture_locations()
    pairs = _pairs_from_locations(locations)
    grouped = score_adjudication_grouped(pairs, locations)

    assert set(grouped.by_cell) == {location.cell_id for location in locations.values()}
    assert list(grouped.by_stratum) == list(STRATA_GROUP_FIELDS)
    for field in STRATA_GROUP_FIELDS:
        assert grouped.by_stratum[field]


def test_split_is_copied_from_the_case() -> None:
    locations = _fixture_locations()
    split_case = locations["split_not_rederived:00000"]
    assert split_case.strata is not None
    assert "sebi" not in split_case.strata.floor_set
    assert split_case.strata.split == "eval"

    pairs = _pairs_from_locations(locations)
    grouped = score_adjudication_grouped(pairs, locations)
    eval_group = grouped.by_stratum["split"]["eval"]
    assert eval_group.total_cases == 2
    assert "split_not_rederived" in grouped.by_cell


def test_v1_locations_without_strata_produce_empty_groups() -> None:
    export = load_export()
    locations = {
        location.location_id: location
        for subject in export.subjects
        for location in subject.locations
    }
    assert all(location.strata is None for location in locations.values())
    pairs = [
        (
            ModelVerdict(location_id=location.location_id, verdict=location.expected.verdict),
            location.expected,
        )
        for location in locations.values()
    ]
    grouped = score_adjudication_grouped(pairs, locations)
    assert grouped.by_cell == {}
    assert all(not groups for groups in grouped.by_stratum.values())
    aggregate = score_adjudication(pairs)
    assert aggregate.total_cases == len(pairs)


def test_missing_location_id_fails_closed() -> None:
    locations = _fixture_locations()
    pairs = _pairs_from_locations(locations)
    pairs.append(
        (
            ModelVerdict(location_id="missing-location", verdict="erase"),
            next(iter(locations.values())).expected,
        )
    )
    with pytest.raises(ValueError, match="missing-location"):
        score_adjudication_grouped(pairs, locations)

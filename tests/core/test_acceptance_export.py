"""Acceptance tests for frozen export loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.exceptions import ExportLoadError
from core.export import load_export

FROZEN_SEED_IDS = {"adv-erase-all", "adv-admin-claim", "benign-extra-ask"}
REQUIRED_FLOORS = {"pmla_kyc", "gst", "income_tax", "companies_act", "sebi"}
REQUIRED_TAGS = {
    "floor_inside",
    "floor_outside",
    "cross_floor",
    "mixed_fanout",
    "under_determined",
    "dormant",
}


def _subject_with_tag(bundle, tag: str):
    matches = [subject for subject in bundle.subjects if tag in subject.tags]
    assert len(matches) == 1, f"expected exactly one subject with tag {tag!r}, got {len(matches)}"
    return matches[0]


def test_load_export_parses_subjects(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    assert 10 <= len(bundle.subjects) <= 16


def test_labeled_location_count_in_range(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    location_count = sum(len(subject.locations) for subject in bundle.subjects)
    assert 30 <= location_count <= 50


def test_required_fixture_tags_present(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    tags_present = {tag for subject in bundle.subjects for tag in subject.tags}
    assert REQUIRED_TAGS.issubset(tags_present)


def test_mixed_fanout_spans_three_lanes(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    subject = _subject_with_tag(bundle, "mixed_fanout")
    verdicts = {location.expected.verdict for location in subject.locations}
    assert verdicts >= {"erase", "retain", "escalate"}


def test_expected_blocks_available(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    subject = _subject_with_tag(bundle, "mixed_fanout")
    assert subject.locations
    for location in subject.locations:
        assert location.expected.verdict in {"erase", "retain", "escalate"}


def test_retention_floors_present(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    floor_ids = {floor.floor_id for floor in bundle.rules.retention_floors}
    assert REQUIRED_FLOORS.issubset(floor_ids)


def test_income_tax_floor_is_seven_tax_years(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    income_tax = next(
        floor for floor in bundle.rules.retention_floors if floor.floor_id == "income_tax"
    )
    assert "7" in income_tax.minimum_period


def test_governance_map_present(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    assert bundle.rules.governance_map
    categories = {entry.category for entry in bundle.rules.governance_map}
    assert "securities_transaction" in categories


def test_frozen_seeds_unchanged(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    seed_ids = {seed.case_id for seed in bundle.seeds}
    assert seed_ids == FROZEN_SEED_IDS


def test_missing_export_raises_without_partial_data(tmp_path: Path) -> None:
    with pytest.raises(ExportLoadError):
        load_export(tmp_path / "missing-export")


def test_malformed_manifest_raises_without_partial_data(export_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "export"
    broken.mkdir()
    (broken / "PINNED_AGENT_SHA").write_text(
        (export_dir / "PINNED_AGENT_SHA").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (broken / "manifest.yaml").write_text("not: [valid", encoding="utf-8")
    with pytest.raises(ExportLoadError):
        load_export(broken)


def test_incomplete_rules_raise_without_partial_data(export_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "export"
    for rel in [
        "PINNED_AGENT_SHA",
        "manifest.yaml",
        "adjudication/subjects.yaml",
        "adversarial_seeds/seeds.yaml",
    ]:
        src = export_dir / rel
        dst = broken / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    rules_dir = broken / "rules"
    rules_dir.mkdir()
    (rules_dir / "retention_floors.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "floor_id": "pmla_kyc",
                    "minimum_period": "5 years",
                    "statute_citation": "PMLA",
                }
            ]
        ),
        encoding="utf-8",
    )
    (rules_dir / "governance_map.yaml").write_text("[]", encoding="utf-8")

    with pytest.raises(ExportLoadError):
        load_export(broken)

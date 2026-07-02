"""Load and validate the committed frozen export."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from core.exceptions import ExportLoadError, ProvenanceError
from core.export.provenance import verify_provenance
from core.types import (
    AdjudicationSubject,
    AdversarialSeedCase,
    ExportManifest,
    GovernanceMapEntry,
    RetentionFloorRule,
    RulesCorpus,
)

FROZEN_SEED_IDS = frozenset({"adv-erase-all", "adv-admin-claim", "benign-extra-ask"})
REQUIRED_FLOOR_IDS = frozenset({"pmla_kyc", "gst", "income_tax", "companies_act", "sebi"})


class ExportBundle:
    """Validated frozen export exposed after provenance verification."""

    def __init__(
        self,
        *,
        manifest: ExportManifest,
        subjects: list[AdjudicationSubject],
        rules: RulesCorpus,
        seeds: list[AdversarialSeedCase],
        export_dir: Path,
    ) -> None:
        self.manifest = manifest
        self.subjects = subjects
        self.rules = rules
        self.seeds = seeds
        self.export_dir = export_dir

    def verify_provenance(self) -> ExportManifest:
        return verify_provenance(self.export_dir)


def _raise_load_error(message: str, cause: Exception | None = None) -> None:
    if cause is None:
        raise ExportLoadError(message)
    raise ExportLoadError(message) from cause


def _load_yaml(path: Path) -> object:
    if not path.is_file():
        _raise_load_error(f"Missing export file: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        _raise_load_error(f"Malformed YAML in {path}", exc)


def _parse_subjects(export_dir: Path) -> list[AdjudicationSubject]:
    adjudication_dir = export_dir / "adjudication"
    subjects_path = adjudication_dir / "subjects.yaml"
    data = _load_yaml(subjects_path)

    raw_subjects: list[object]
    if isinstance(data, dict) and "subjects" in data:
        raw_subjects = data["subjects"]
    elif isinstance(data, list):
        raw_subjects = data
    else:
        _raise_load_error("Adjudication export must be a list or contain a subjects key")

    if not raw_subjects:
        _raise_load_error("Adjudication export contains no subjects")

    subjects: list[AdjudicationSubject] = []
    for item in raw_subjects:
        try:
            subjects.append(AdjudicationSubject.model_validate(item))
        except ValidationError as exc:
            _raise_load_error("Invalid adjudication subject in export", exc)
    return subjects


def _parse_rules(export_dir: Path) -> RulesCorpus:
    rules_dir = export_dir / "rules"
    floors_data = _load_yaml(rules_dir / "retention_floors.yaml")
    governance_data = _load_yaml(rules_dir / "governance_map.yaml")

    if not isinstance(floors_data, list) or not isinstance(governance_data, list):
        _raise_load_error("Rules export files must contain YAML lists")

    try:
        floors = [RetentionFloorRule.model_validate(item) for item in floors_data]
        governance = [GovernanceMapEntry.model_validate(item) for item in governance_data]
    except ValidationError as exc:
        _raise_load_error("Invalid rules corpus in export", exc)

    floor_ids = {floor.floor_id for floor in floors}
    if not REQUIRED_FLOOR_IDS.issubset(floor_ids):
        missing = sorted(REQUIRED_FLOOR_IDS - floor_ids)
        _raise_load_error(f"Export missing required retention floors: {', '.join(missing)}")

    return RulesCorpus(retention_floors=floors, governance_map=governance)


def _parse_seeds(export_dir: Path) -> list[AdversarialSeedCase]:
    seeds_path = export_dir / "adversarial_seeds" / "seeds.yaml"
    data = _load_yaml(seeds_path)
    if not isinstance(data, list):
        _raise_load_error("Adversarial seeds export must be a YAML list")

    seeds: list[AdversarialSeedCase] = []
    for item in data:
        try:
            seeds.append(AdversarialSeedCase.model_validate(item))
        except ValidationError as exc:
            _raise_load_error("Invalid adversarial seed in export", exc)

    seed_ids = {seed.case_id for seed in seeds}
    if seed_ids != FROZEN_SEED_IDS:
        _raise_load_error(
            "Adversarial seeds must contain exactly the frozen seed IDs: "
            + ", ".join(sorted(FROZEN_SEED_IDS))
        )
    return seeds


def load_export(export_dir: Path | None = None) -> ExportBundle:
    """Load export after provenance verification; fail closed on errors."""
    root = export_dir or Path("export")
    try:
        manifest = verify_provenance(root)
        subjects = _parse_subjects(root)
        rules = _parse_rules(root)
        seeds = _parse_seeds(root)
    except ProvenanceError as exc:
        message = str(exc)
        if "does not match" in message or "does not reference" in message:
            raise
        raise ExportLoadError(message) from exc
    except ExportLoadError:
        raise
    except Exception as exc:
        _raise_load_error("Failed to load export", exc)

    return ExportBundle(
        manifest=manifest,
        subjects=subjects,
        rules=rules,
        seeds=seeds,
        export_dir=root,
    )

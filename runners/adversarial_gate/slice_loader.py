"""Load and validate the extended adversarial slice fixture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from core.export.loader import load_export
from core.export.provenance import verify_provenance
from core.types import AdversarialSeedCase

FROZEN_SEED_IDS = frozenset({"adv-erase-all", "adv-admin-claim", "benign-extra-ask"})
ATTACK_FAMILIES = (
    "direct_override",
    "authority_spoof",
    "obfuscated_injection",
    "scope_expansion",
    "exfiltration",
)
DEFAULT_SLICE_PATH = Path("fixtures/adversarial_slice/cases.yaml")


class SeedMismatchError(Exception):
    """Raised when extended slice frozen seed content diverges from export."""


class SliceValidationError(Exception):
    """Raised when extended slice fixture fails coverage validation."""


@dataclass(frozen=True)
class ExtendedAdversarialSlice:
    cases: list[AdversarialSeedCase]
    source_path: Path
    seed_check_passed: bool


def _load_yaml_cases(path: Path) -> list[AdversarialSeedCase]:
    if not path.is_file():
        raise SliceValidationError(f"Missing adversarial slice fixture: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, list):
        raise SliceValidationError("Adversarial slice fixture must be a YAML list")
    cases: list[AdversarialSeedCase] = []
    for item in data:
        try:
            cases.append(AdversarialSeedCase.model_validate(item))
        except ValidationError as exc:
            raise SliceValidationError(f"Invalid slice case in {path}") from exc
    return cases


def _validate_coverage(cases: list[AdversarialSeedCase]) -> None:
    if not (80 <= len(cases) <= 100):
        raise SliceValidationError(f"Slice must contain 80-100 cases, got {len(cases)}")
    case_ids = [item.case_id for item in cases]
    if len(case_ids) != len(set(case_ids)):
        raise SliceValidationError("Duplicate case_id values in slice fixture")
    attacks = [item for item in cases if item.label == "attack"]
    benign = [item for item in cases if item.label == "benign"]
    if not (40 <= len(attacks) <= 50):
        raise SliceValidationError(f"Attack count must be 40-50, got {len(attacks)}")
    if not (40 <= len(benign) <= 50):
        raise SliceValidationError(f"Benign count must be 40-50, got {len(benign)}")
    for case in attacks:
        if case.family not in ATTACK_FAMILIES:
            raise SliceValidationError(
                f"Invalid attack family on {case.case_id!r}: {case.family!r}"
            )
    families = {item.family for item in attacks}
    if families != set(ATTACK_FAMILIES):
        missing = sorted(set(ATTACK_FAMILIES) - families)
        raise SliceValidationError(f"Missing attack families: {', '.join(missing)}")
    for family in ATTACK_FAMILIES:
        count = sum(1 for item in attacks if item.family == family)
        if not (8 <= count <= 10):
            raise SliceValidationError(
                f"Family {family!r} must have 8-10 attack cases, got {count}"
            )


def _cross_check_frozen_seeds(
    cases: list[AdversarialSeedCase],
    export_dir: Path,
) -> None:
    verify_provenance(export_dir)
    bundle = load_export(export_dir)
    export_by_id = {seed.case_id: seed for seed in bundle.seeds}
    slice_by_id = {case.case_id: case for case in cases}
    for seed_id in FROZEN_SEED_IDS:
        if seed_id not in slice_by_id:
            raise SliceValidationError(f"Missing frozen seed {seed_id!r} in extended slice")
        slice_case = slice_by_id[seed_id]
        export_case = export_by_id[seed_id]
        if slice_case.model_dump() != export_case.model_dump():
            raise SeedMismatchError(
                f"Frozen seed {seed_id!r} in extended slice does not match export"
            )


def load_extended_slice(
    path: Path | None = None,
    *,
    verify_seeds: bool = True,
    export_dir: Path | None = None,
) -> ExtendedAdversarialSlice:
    """Load extended adversarial slice in stable file order."""
    slice_path = path or DEFAULT_SLICE_PATH
    cases = _load_yaml_cases(slice_path)
    _validate_coverage(cases)
    seed_check_passed = False
    if verify_seeds:
        root = export_dir or Path("export")
        _cross_check_frozen_seeds(cases, root)
        seed_check_passed = True
    return ExtendedAdversarialSlice(
        cases=cases,
        source_path=slice_path,
        seed_check_passed=seed_check_passed,
    )

#!/usr/bin/env python3
"""Deliberate re-export from the pinned agent commit.

Clones or fetches https://github.com/KrishnaDev-Palem/dpdp-erasure-agent at the
pinned SHA, transforms block-1 fixtures into the harness export shape, and writes
provenance, rules, and adversarial seed files.

This script is for human-operated export regeneration only. It MUST NOT run in CI
or default workflows.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_REPO = "https://github.com/KrishnaDev-Palem/dpdp-erasure-agent.git"
EXPORT_VERSION = "1.0.0"

REQUIRED_TAGS = frozenset(
    {
        "floor_inside",
        "floor_outside",
        "cross_floor",
        "mixed_fanout",
        "under_determined",
        "dormant",
    }
)
REQUIRED_FLOOR_IDS = frozenset({"pmla_kyc", "gst", "income_tax", "companies_act", "sebi"})
FROZEN_SEED_IDS = ("adv-erase-all", "adv-admin-claim", "benign-extra-ask")
SEED_FAMILY_BY_ID = {
    "adv-erase-all": "direct_override",
    "adv-admin-claim": "authority_spoof",
    "benign-extra-ask": None,
}


class ExportRegenerationError(Exception):
    """Raised when agent fixtures cannot be transformed into a valid export."""


def _run_git(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ExportRegenerationError(
            f"git {' '.join(args)} failed in {cwd}:\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _clone_agent_repo(agent_repo: str, pinned_sha: str, work_dir: Path) -> Path:
    clone_dir = work_dir / "dpdp-erasure-agent"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    _run_git(["clone", agent_repo, str(clone_dir)], cwd=work_dir)
    _run_git(["checkout", "--quiet", pinned_sha], cwd=clone_dir)
    resolved = _run_git(["rev-parse", "HEAD"], cwd=clone_dir)
    if resolved.lower() != pinned_sha.lower():
        raise ExportRegenerationError(
            f"Checked out SHA {resolved!r} does not match requested pin {pinned_sha!r}"
        )
    return clone_dir


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _anchor_selector(value: Any) -> str:
    if value is None:
        return "none"
    return str(value)


def _transform_governance(agent_governance: dict[str, Any]) -> list[dict[str, Any]]:
    categories = agent_governance.get("categories")
    if not isinstance(categories, dict):
        raise ExportRegenerationError("Agent governance.yaml missing categories map")
    entries: list[dict[str, Any]] = []
    for category, payload in sorted(categories.items()):
        if not isinstance(payload, dict):
            raise ExportRegenerationError(f"Invalid governance entry for {category!r}")
        entries.append(
            {
                "category": category,
                "floors": list(payload.get("floors", [])),
                "anchor_selector": _anchor_selector(payload.get("anchor_selector")),
            }
        )
    return entries


def _transform_floors(agent_floors: dict[str, Any]) -> list[dict[str, Any]]:
    floors = agent_floors.get("floors")
    if not isinstance(floors, list):
        raise ExportRegenerationError("Agent floors.yaml missing floors list")
    transformed: list[dict[str, Any]] = []
    for item in floors:
        if not isinstance(item, dict):
            raise ExportRegenerationError("Invalid floor entry in agent floors.yaml")
        floor_id = item.get("floor_id")
        period = item.get("period")
        citation = item.get("statute_citation")
        if not floor_id or not period or not citation:
            raise ExportRegenerationError(f"Incomplete floor entry: {item!r}")
        transformed.append(
            {
                "floor_id": floor_id,
                "minimum_period": str(period),
                "statute_citation": str(citation),
            }
        )
    floor_ids = {item["floor_id"] for item in transformed}
    missing = sorted(REQUIRED_FLOOR_IDS - floor_ids)
    if missing:
        raise ExportRegenerationError(f"Agent floors missing required ids: {', '.join(missing)}")
    income_tax = next(item for item in transformed if item["floor_id"] == "income_tax")
    if "7" not in income_tax["minimum_period"]:
        raise ExportRegenerationError(
            "Income Tax floor at pinned SHA is not 7 tax years: "
            f"{income_tax['minimum_period']!r}"
        )
    return transformed


def _transform_subject(subject: dict[str, Any], as_of: str) -> dict[str, Any]:
    subject_id = subject["subject_id"]
    records = subject.get("records", [])
    expected_items = subject.get("expected", [])
    expected_by_id = {item["location_id"]: item for item in expected_items}
    locations: list[dict[str, Any]] = []
    for record in records:
        location_id = record["location_id"]
        expected = expected_by_id.get(location_id)
        if expected is None:
            raise ExportRegenerationError(
                f"Subject {subject_id!r} record {location_id!r} has no expected label"
            )
        location = {key: value for key, value in record.items()}
        location["expected"] = {
            "category": expected["category"],
            "anchor_resolvable": expected["anchor_resolvable"],
            "verdict": expected["verdict"],
            "cited_floors": list(expected.get("cited_floors", [])),
        }
        locations.append(location)
    request = dict(subject["request"])
    request["subject_id"] = subject_id
    request["as_of"] = as_of
    return {
        "subject_id": subject_id,
        "tags": list(subject.get("coverage_tags", [])),
        "request": request,
        "locations": locations,
    }


def _transform_subjects(block1: dict[str, Any]) -> list[dict[str, Any]]:
    as_of = str(block1.get("as_of", "2026-06-01"))
    raw_subjects = block1.get("subjects")
    if not isinstance(raw_subjects, list) or not raw_subjects:
        raise ExportRegenerationError("Agent block1.yaml contains no subjects")
    subjects = [_transform_subject(item, as_of) for item in raw_subjects]
    tags_present: set[str] = set()
    for subject in subjects:
        tags_present.update(subject["tags"])
    missing_tags = sorted(REQUIRED_TAGS - tags_present)
    if missing_tags:
        raise ExportRegenerationError(
            f"Agent block-1 fixtures missing required tags: {', '.join(missing_tags)}"
        )
    location_count = sum(len(subject["locations"]) for subject in subjects)
    if not (30 <= location_count <= 50):
        raise ExportRegenerationError(
            f"Agent block-1 yields {location_count} labeled locations; need 30-50"
        )
    mixed = next(item for item in subjects if "mixed_fanout" in item["tags"])
    verdicts = {loc["expected"]["verdict"] for loc in mixed["locations"]}
    if not {"erase", "retain", "escalate"} <= verdicts:
        raise ExportRegenerationError(
            "mixed_fanout subject must span erase, retain, and escalate lanes"
        )
    return subjects


def _transform_seeds(block3: dict[str, Any]) -> list[dict[str, Any]]:
    slice_cases = block3.get("adversarial_slice")
    if not isinstance(slice_cases, list):
        raise ExportRegenerationError("Agent block3.yaml missing adversarial_slice list")
    by_id = {item["case_id"]: item for item in slice_cases if "case_id" in item}
    seeds: list[dict[str, Any]] = []
    for seed_id in FROZEN_SEED_IDS:
        case = by_id.get(seed_id)
        if case is None:
            raise ExportRegenerationError(f"Agent block3 missing frozen seed {seed_id!r}")
        agent_label = case.get("label")
        if agent_label == "adversarial":
            label = "attack"
        elif agent_label == "clean":
            label = "benign"
        else:
            raise ExportRegenerationError(
                f"Unexpected adversarial label on {seed_id!r}: {agent_label!r}"
            )
        text = case.get("requester_note")
        if not text:
            raise ExportRegenerationError(f"Frozen seed {seed_id!r} missing requester_note text")
        seed: dict[str, Any] = {
            "case_id": seed_id,
            "surface": case.get("surface", "requester_note"),
            "text": text,
            "label": label,
        }
        family = SEED_FAMILY_BY_ID[seed_id]
        if family is not None:
            seed["family"] = family
        seeds.append(seed)
    return seeds


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def regenerate_export(
    *,
    output_dir: Path,
    pinned_sha: str,
    agent_repo: str = DEFAULT_AGENT_REPO,
    work_dir: Path | None = None,
) -> str:
    """Transform agent fixtures at pinned_sha into output_dir. Returns resolved SHA."""
    pinned_sha = pinned_sha.strip().lower()
    if len(pinned_sha) != 40 or any(ch not in "0123456789abcdef" for ch in pinned_sha):
        raise ExportRegenerationError("Pinned SHA must be a 40-character hex string")

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if work_dir is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="dpdp-export-regen-")
        work_dir = Path(temp_dir.name)

    agent_root = _clone_agent_repo(agent_repo, pinned_sha, work_dir)
    block1 = _load_yaml(agent_root / "fixtures" / "block1.yaml")
    block3 = _load_yaml(agent_root / "fixtures" / "block3.yaml")
    agent_floors = _load_yaml(agent_root / "src" / "dpdp" / "rules" / "floors.yaml")
    agent_governance = _load_yaml(agent_root / "src" / "dpdp" / "rules" / "governance.yaml")

    as_of = str(block1.get("as_of", "2026-06-01"))
    generated_at = date.today().isoformat()
    subjects = _transform_subjects(block1)
    floors = _transform_floors(agent_floors)
    governance = _transform_governance(agent_governance)
    seeds = _transform_seeds(block3)

    commit_url = (
        "https://github.com/KrishnaDev-Palem/dpdp-erasure-agent/commit/" f"{pinned_sha}"
    )
    manifest = {
        "export_version": EXPORT_VERSION,
        "generated_at": generated_at,
        "as_of": as_of,
        "agent_commit_sha": pinned_sha,
        "agent_commit_url": commit_url,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "PINNED_AGENT_SHA", pinned_sha + "\n")
    _write_yaml(output_dir / "manifest.yaml", manifest)
    _write_yaml(output_dir / "adjudication" / "subjects.yaml", {"subjects": subjects})
    _write_yaml(output_dir / "rules" / "retention_floors.yaml", floors)
    _write_yaml(output_dir / "rules" / "governance_map.yaml", governance)
    _write_yaml(output_dir / "adversarial_seeds" / "seeds.yaml", seeds)

    if temp_dir is not None:
        temp_dir.cleanup()
    return pinned_sha


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "export",
        help="Directory to write the frozen export (default: repo export/)",
    )
    parser.add_argument(
        "--pinned-sha",
        type=str,
        default=None,
        help="40-char agent commit SHA (default: read export/PINNED_AGENT_SHA if present)",
    )
    parser.add_argument(
        "--agent-repo",
        type=str,
        default=DEFAULT_AGENT_REPO,
        help="Agent git remote URL",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional directory for cloning the agent (default: temp dir)",
    )
    args = parser.parse_args(argv)

    pinned_sha = args.pinned_sha
    if pinned_sha is None:
        pin_path = REPO_ROOT / "export" / "PINNED_AGENT_SHA"
        if pin_path.is_file():
            pinned_sha = pin_path.read_text(encoding="utf-8").strip()
        else:
            parser.error("Provide --pinned-sha or commit export/PINNED_AGENT_SHA first")

    try:
        resolved = regenerate_export(
            output_dir=args.output_dir,
            pinned_sha=pinned_sha,
            agent_repo=args.agent_repo,
            work_dir=args.work_dir,
        )
    except ExportRegenerationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    location_count = sum(
        len(item["locations"])
        for item in _load_yaml(args.output_dir / "adjudication" / "subjects.yaml")["subjects"]
    )
    print(f"Wrote export to {args.output_dir}")
    print(f"Pinned agent SHA: {resolved}")
    print(f"Labeled locations: {location_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

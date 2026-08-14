#!/usr/bin/env python3
"""Deliberate re-export from a pinned agent commit or tag.

Clones or fetches https://github.com/KrishnaDev-Palem/dpdp-erasure-agent, checks
out the requested pin, generates the stratified pool, filters to
``export/frozen_slice_ids.json``, and writes the harness export shape.

Coverage pin (human-run, not CI)::

    python scripts/regenerate_export.py \\
        --pinned-tag export-v1.1.0 \\
        --output-dir /tmp/dpdp-coverage-export

That command verifies pool hash ``d681eeec…`` and membership hash ``b93646fb…``.
It refuses to overwrite the committed ``export/`` tree unless
``--overwrite-committed`` is passed. Do not use that flag until the later
archive + re-pin slice.

This script MUST NOT run in CI or default workflows.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.exceptions import ExportLoadError  # noqa: E402
from core.export.agent_cases import subjects_from_agent_cases  # noqa: E402
from core.export.coverage import (  # noqa: E402
    COVERAGE_AGENT_SHA,
    COVERAGE_AGENT_TAG,
    COVERAGE_MEMBERSHIP_HASH,
    COVERAGE_POOL_HASH,
    GENERATOR_AS_OF,
    load_frozen_slice_ids,
    select_coverage_cases,
)

DEFAULT_AGENT_REPO = "https://github.com/KrishnaDev-Palem/dpdp-erasure-agent.git"
EXPORT_VERSION = "1.0.0"
COMMITTED_EXPORT_DIR = REPO_ROOT / "export"

REQUIRED_FLOOR_IDS = frozenset({"pmla_kyc", "gst", "income_tax", "companies_act", "sebi"})
FROZEN_SEED_IDS = ("adv-erase-all", "adv-admin-claim", "benign-extra-ask")
SEED_FAMILY_BY_ID = {
    "adv-erase-all": "direct_override",
    "adv-admin-claim": "authority_spoof",
    "benign-extra-ask": None,
}

GeneratePoolFn = Callable[[Path], tuple[list[dict[str, Any]], str, str]]


class ExportRegenerationError(Exception):
    """Raised when the agent checkout cannot be transformed into a valid export."""


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


def _normalize_sha(value: str) -> str:
    sha = value.strip().lower()
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise ExportRegenerationError("Pinned SHA must be a 40-character hex string")
    return sha


def _clone_agent_repo(
    agent_repo: str,
    *,
    pinned_sha: str | None,
    pinned_tag: str | None,
    work_dir: Path,
) -> tuple[Path, str]:
    clone_dir = work_dir / "dpdp-erasure-agent"
    if clone_dir.exists():
        shutil.rmtree(clone_dir)
    _run_git(["clone", agent_repo, str(clone_dir)], cwd=work_dir)
    target = pinned_tag or pinned_sha
    if not target:
        raise ExportRegenerationError("Provide --pinned-sha or --pinned-tag")
    _run_git(["checkout", "--quiet", target], cwd=clone_dir)
    resolved = _run_git(["rev-parse", "HEAD"], cwd=clone_dir).lower()
    if pinned_sha and resolved != pinned_sha:
        raise ExportRegenerationError(
            f"Checked out SHA {resolved!r} does not match requested pin {pinned_sha!r}"
        )
    if pinned_tag == COVERAGE_AGENT_TAG and resolved != COVERAGE_AGENT_SHA:
        raise ExportRegenerationError(
            f"Tag {pinned_tag!r} resolved to {resolved!r}, expected {COVERAGE_AGENT_SHA}"
        )
    return clone_dir, resolved


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
            f"Income Tax floor at pinned SHA is not 7 tax years: {income_tax['minimum_period']!r}"
        )
    return transformed


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


def _generate_agent_pool(agent_root: Path) -> tuple[list[dict[str, Any]], str, str]:
    """Import the checkout's generator and build the full pool."""
    src = str(agent_root / "src")
    inserted = src not in sys.path
    if inserted:
        sys.path.insert(0, src)
    stale = [name for name in sys.modules if name == "dpdp" or name.startswith("dpdp.")]
    for name in stale:
        del sys.modules[name]
    try:
        from dpdp.generator.config import load_config
        from dpdp.generator.generate import generate_pool, manifest_hash
    except Exception as exc:
        raise ExportRegenerationError(
            f"Failed to import agent generator from {agent_root}: {exc}"
        ) from exc
    try:
        config = load_config()
        pool = generate_pool(config)
        digest = manifest_hash(pool.cases)
        as_of = config.as_of.isoformat()
        return list(pool.cases), digest, as_of
    except ExportRegenerationError:
        raise
    except Exception as exc:
        raise ExportRegenerationError(f"Failed to generate agent pool: {exc}") from exc
    finally:
        if inserted:
            with contextlib.suppress(ValueError):
                sys.path.remove(src)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def _assert_output_allowed(output_dir: Path, *, allow_overwrite_committed: bool) -> None:
    if output_dir.resolve() == COMMITTED_EXPORT_DIR.resolve() and not allow_overwrite_committed:
        raise ExportRegenerationError(
            "Refusing to overwrite committed export/. "
            "Pass --output-dir to a different path, or --overwrite-committed "
            "only when archiving v1 and re-pinning."
        )


def regenerate_export(
    *,
    output_dir: Path,
    pinned_sha: str | None = None,
    pinned_tag: str | None = None,
    agent_repo: str = DEFAULT_AGENT_REPO,
    work_dir: Path | None = None,
    agent_checkout: Path | None = None,
    allow_overwrite_committed: bool = False,
    generate_pool_fn: GeneratePoolFn | None = None,
    expected_pool_hash: str = COVERAGE_POOL_HASH,
    expected_membership_hash: str = COVERAGE_MEMBERSHIP_HASH,
) -> str:
    """Generate the coverage export at the pinned agent checkout. Returns resolved SHA."""
    _assert_output_allowed(output_dir, allow_overwrite_committed=allow_overwrite_committed)

    if pinned_sha is not None:
        pinned_sha = _normalize_sha(pinned_sha)
    if pinned_tag is None and pinned_sha is None:
        pinned_tag = COVERAGE_AGENT_TAG

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if agent_checkout is not None:
        agent_root = agent_checkout
        if (agent_root / ".git").exists():
            resolved = _run_git(["rev-parse", "HEAD"], cwd=agent_root).lower()
            if pinned_sha and resolved != pinned_sha:
                raise ExportRegenerationError(
                    f"agent-checkout HEAD {resolved!r} does not match {pinned_sha!r}"
                )
            if pinned_tag == COVERAGE_AGENT_TAG and resolved != COVERAGE_AGENT_SHA:
                raise ExportRegenerationError(
                    f"agent-checkout HEAD {resolved!r} is not {COVERAGE_AGENT_TAG} "
                    f"({COVERAGE_AGENT_SHA})"
                )
        else:
            resolved = pinned_sha or COVERAGE_AGENT_SHA
    else:
        if work_dir is None:
            temp_dir = tempfile.TemporaryDirectory(prefix="dpdp-export-regen-")
            work_dir = Path(temp_dir.name)
        agent_root, resolved = _clone_agent_repo(
            agent_repo,
            pinned_sha=pinned_sha,
            pinned_tag=pinned_tag,
            work_dir=work_dir,
        )

    block3_path = agent_root / "fixtures" / "block3.yaml"
    floors_path = agent_root / "src" / "dpdp" / "rules" / "floors.yaml"
    gov_path = agent_root / "src" / "dpdp" / "rules" / "governance.yaml"
    slice_path = agent_root / "export" / "frozen_slice_ids.json"
    for required in (block3_path, floors_path, gov_path, slice_path):
        if not required.is_file():
            raise ExportRegenerationError(f"Agent checkout missing {required}")

    block3 = _load_yaml(block3_path)
    agent_floors = _load_yaml(floors_path)
    agent_governance = _load_yaml(gov_path)

    generate = generate_pool_fn or _generate_agent_pool
    try:
        cases, pool_hash, as_of = generate(agent_root)
        slice_ids = load_frozen_slice_ids(slice_path)
        selected = select_coverage_cases(
            cases,
            slice_ids,
            pool_hash=pool_hash,
            expected_pool_hash=expected_pool_hash,
            expected_membership_hash=expected_membership_hash,
        )
        subjects = [
            subject.model_dump(mode="json")
            for subject in subjects_from_agent_cases(selected, as_of=as_of)
        ]
    except ExportLoadError as exc:
        raise ExportRegenerationError(str(exc)) from exc

    floors = _transform_floors(agent_floors)
    governance = _transform_governance(agent_governance)
    seeds = _transform_seeds(block3)

    commit_url = f"https://github.com/KrishnaDev-Palem/dpdp-erasure-agent/commit/{resolved}"
    manifest = {
        "export_version": EXPORT_VERSION,
        "generated_at": date.today().isoformat(),
        "as_of": as_of,
        "agent_commit_sha": resolved,
        "agent_commit_url": commit_url,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_text(output_dir / "PINNED_AGENT_SHA", resolved + "\n")
    _write_yaml(output_dir / "manifest.yaml", manifest)
    _write_yaml(output_dir / "adjudication" / "subjects.yaml", {"subjects": subjects})
    _write_yaml(output_dir / "rules" / "retention_floors.yaml", floors)
    _write_yaml(output_dir / "rules" / "governance_map.yaml", governance)
    _write_yaml(output_dir / "adversarial_seeds" / "seeds.yaml", seeds)

    if temp_dir is not None:
        temp_dir.cleanup()
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "export",
        help="Directory to write the export (default: repo export/; refused unless "
        "--overwrite-committed)",
    )
    parser.add_argument(
        "--pinned-sha",
        type=str,
        default=None,
        help="40-char agent commit SHA (optional if --pinned-tag is set)",
    )
    parser.add_argument(
        "--pinned-tag",
        type=str,
        default=None,
        help=f"Agent tag to check out (default: {COVERAGE_AGENT_TAG})",
    )
    parser.add_argument(
        "--agent-repo",
        type=str,
        default=DEFAULT_AGENT_REPO,
        help="Agent git remote URL",
    )
    parser.add_argument(
        "--agent-checkout",
        type=Path,
        default=None,
        help="Existing agent checkout at the requested pin (skip clone)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional directory for cloning the agent (default: temp dir)",
    )
    parser.add_argument(
        "--overwrite-committed",
        action="store_true",
        help="Allow writing to the committed export/ tree (archive + re-pin only)",
    )
    args = parser.parse_args(argv)

    try:
        resolved = regenerate_export(
            output_dir=args.output_dir,
            pinned_sha=args.pinned_sha,
            pinned_tag=args.pinned_tag,
            agent_repo=args.agent_repo,
            work_dir=args.work_dir,
            agent_checkout=args.agent_checkout,
            allow_overwrite_committed=args.overwrite_committed,
        )
    except ExportRegenerationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    subjects = _load_yaml(args.output_dir / "adjudication" / "subjects.yaml")["subjects"]
    location_count = sum(len(item["locations"]) for item in subjects)
    print(f"Wrote export to {args.output_dir}")
    print(f"Pinned agent SHA: {resolved}")
    print(f"as_of: {GENERATOR_AS_OF}")
    print(f"Subjects / locations: {len(subjects)} / {location_count}")
    print(f"Expected pool hash: {COVERAGE_POOL_HASH}")
    print(f"Expected membership hash: {COVERAGE_MEMBERSHIP_HASH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

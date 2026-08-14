"""Frozen coverage-slice identity (agent tag export-v1.1.0 / ADR-0008)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from core.exceptions import ExportLoadError

# Agent tag export-v1.1.0. Do not flip the committed PINNED_AGENT_SHA to this
# until the later archive + re-pin slice.
COVERAGE_AGENT_TAG = "export-v1.1.0"
COVERAGE_AGENT_SHA = "7b659e8e3ec87a9115a5d7709f20f1c1eb6fec22"
GENERATOR_AS_OF = "2026-02-15"
COVERAGE_POOL_HASH = "d681eeecb5e77054402eec9bd3de8f8424333126dcaf4dcfc072b597dd343d21"
COVERAGE_MEMBERSHIP_HASH = "b93646fb429571eb690060285c1fca32ad015388ee7c14eb99d30f855924e464"


def membership_hash(case_ids: Iterable[str]) -> str:
    """SHA-256 of sorted case ids, matching agent `dpdp.export.slice`."""
    payload = json.dumps(sorted(case_ids), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def verify_coverage_hashes(
    *,
    pool_hash: str,
    selected_ids: Sequence[str],
    expected_pool_hash: str = COVERAGE_POOL_HASH,
    expected_membership_hash: str = COVERAGE_MEMBERSHIP_HASH,
) -> None:
    """Fail closed when the generated pool or selected ids do not match the pin."""
    if pool_hash != expected_pool_hash:
        raise ExportLoadError(f"pool hash mismatch: got {pool_hash}, expected {expected_pool_hash}")
    actual = membership_hash(selected_ids)
    if actual != expected_membership_hash:
        raise ExportLoadError(
            f"membership hash mismatch: got {actual}, expected {expected_membership_hash}"
        )


def load_frozen_slice_ids(path: Path) -> list[str]:
    """Read `export/frozen_slice_ids.json` and check its self-hash."""
    if not path.is_file():
        raise ExportLoadError(f"Missing frozen slice membership file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExportLoadError(f"Malformed frozen slice JSON in {path}") from exc
    if not isinstance(data, dict) or "case_ids" not in data:
        raise ExportLoadError("frozen_slice_ids.json must be an object with case_ids")
    ids = data["case_ids"]
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise ExportLoadError("frozen_slice_ids.json case_ids must be a list of strings")
    computed = membership_hash(ids)
    file_hash = data.get("membership_hash")
    if file_hash is not None and file_hash != computed:
        raise ExportLoadError("frozen_slice_ids.json membership_hash does not match its case_ids")
    return list(ids)


def select_coverage_cases(
    cases: Sequence[dict[str, Any]],
    slice_ids: Sequence[str],
    *,
    pool_hash: str,
    expected_pool_hash: str = COVERAGE_POOL_HASH,
    expected_membership_hash: str = COVERAGE_MEMBERSHIP_HASH,
) -> list[dict[str, Any]]:
    """Filter a generated pool to the frozen membership. Do not re-select."""
    verify_coverage_hashes(
        pool_hash=pool_hash,
        selected_ids=slice_ids,
        expected_pool_hash=expected_pool_hash,
        expected_membership_hash=expected_membership_hash,
    )
    by_id = {case["case_id"]: case for case in cases}
    missing = [case_id for case_id in slice_ids if case_id not in by_id]
    if missing:
        preview = ", ".join(missing[:5])
        raise ExportLoadError(
            f"frozen slice has {len(missing)} ids missing from the generated pool (e.g. {preview})"
        )
    return [by_id[case_id] for case_id in slice_ids]

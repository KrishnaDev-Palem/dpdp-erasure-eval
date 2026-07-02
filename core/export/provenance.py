"""Export provenance verification."""

from __future__ import annotations

from pathlib import Path

import yaml

from core.exceptions import ProvenanceError
from core.types import ExportManifest

PINNED_SHA_FILENAME = "PINNED_AGENT_SHA"
MANIFEST_FILENAME = "manifest.yaml"


def _read_pinned_sha(export_dir: Path) -> str:
    pin_path = export_dir / PINNED_SHA_FILENAME
    if not pin_path.is_file():
        raise ProvenanceError(f"Missing pinned agent SHA file: {pin_path}")
    sha = pin_path.read_text(encoding="utf-8").strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha.lower()):
        raise ProvenanceError("Pinned agent SHA must be a 40-character hex string")
    return sha.lower()


def _load_manifest(export_dir: Path) -> ExportManifest:
    manifest_path = export_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ProvenanceError(f"Missing export manifest: {manifest_path}")
    with manifest_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ProvenanceError("Export manifest must be a YAML mapping")
    return ExportManifest.model_validate(data)


def verify_provenance(export_dir: Path | None = None) -> ExportManifest:
    """Verify pinned SHA matches manifest before exposing export data."""
    root = export_dir or Path("export")
    pinned_sha = _read_pinned_sha(root)
    manifest = _load_manifest(root)

    manifest_sha = manifest.agent_commit_sha.lower()
    if manifest_sha != pinned_sha:
        raise ProvenanceError(
            f"Manifest agent_commit_sha {manifest_sha!r} does not match pinned SHA {pinned_sha!r}"
        )

    expected_url_suffix = f"/commit/{manifest_sha}"
    if not manifest.agent_commit_url.rstrip("/").endswith(expected_url_suffix):
        raise ProvenanceError("Manifest agent_commit_url does not reference the pinned commit SHA")

    return manifest

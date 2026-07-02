"""Acceptance tests for export provenance verification."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.exceptions import ProvenanceError
from core.export import load_export, verify_provenance


def test_provenance_match_success(export_dir: Path) -> None:
    manifest = verify_provenance(export_dir)
    assert (
        manifest.agent_commit_sha
        == (export_dir / "PINNED_AGENT_SHA").read_text(encoding="utf-8").strip().lower()
    )


def test_load_export_verifies_provenance(export_dir: Path) -> None:
    bundle = load_export(export_dir)
    assert bundle.verify_provenance().export_version == "1.0.0"


def test_sha_mismatch_fails_closed(export_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "export"
    broken.mkdir()
    (broken / "PINNED_AGENT_SHA").write_text("a" * 40, encoding="utf-8")
    manifest = yaml.safe_load((export_dir / "manifest.yaml").read_text(encoding="utf-8"))
    (broken / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(ProvenanceError):
        verify_provenance(broken)

    with pytest.raises(ProvenanceError):
        load_export(broken)


def test_url_mismatch_fails_closed(export_dir: Path, tmp_path: Path) -> None:
    broken = tmp_path / "export"
    broken.mkdir()
    sha = (export_dir / "PINNED_AGENT_SHA").read_text(encoding="utf-8").strip()
    (broken / "PINNED_AGENT_SHA").write_text(sha, encoding="utf-8")
    manifest = yaml.safe_load((export_dir / "manifest.yaml").read_text(encoding="utf-8"))
    manifest["agent_commit_url"] = "https://example.com/wrong/commit/sha"
    (broken / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

    with pytest.raises(ProvenanceError):
        verify_provenance(broken)

    with pytest.raises(ProvenanceError):
        load_export(broken)

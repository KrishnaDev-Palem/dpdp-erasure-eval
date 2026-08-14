"""Lock the v1 archive to the committed default-path snapshot."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_V1 = REPO_ROOT / "archive" / "v1"
PINNED_AGENT_SHA = "3562059939cbaac3dc3500593f2940ef34c54c53"


def _file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_archive_export_pin_matches_published_agent_sha() -> None:
    pin = (ARCHIVE_V1 / "export" / "PINNED_AGENT_SHA").read_text(encoding="utf-8").strip()
    assert pin == PINNED_AGENT_SHA


def test_archive_export_is_byte_identical_to_default_export() -> None:
    assert _file_map(ARCHIVE_V1 / "export") == _file_map(REPO_ROOT / "export")


def test_archive_results_are_byte_identical_to_default_results() -> None:
    archived = _file_map(ARCHIVE_V1 / "results")
    default = _file_map(REPO_ROOT / "results")
    assert set(archived) == set(default)
    assert len(archived) == 12
    assert archived == default


def test_archive_writeup_is_byte_identical_to_default_writeup() -> None:
    assert (ARCHIVE_V1 / "docs" / "writeup.md").read_bytes() == (
        REPO_ROOT / "docs" / "writeup.md"
    ).read_bytes()


def test_archive_figures_are_byte_identical_to_default_figures() -> None:
    assert _file_map(ARCHIVE_V1 / "docs" / "figures") == _file_map(REPO_ROOT / "docs" / "figures")


def test_archive_readme_names_tag_pin_and_replay_command() -> None:
    text = (ARCHIVE_V1 / "README.md").read_text(encoding="utf-8")
    assert "eval-v1.0.0" in text
    assert PINNED_AGENT_SHA in text
    assert "git checkout eval-v1.0.0" in text


def test_archive_does_not_contain_cache() -> None:
    archive_root = REPO_ROOT / "archive"
    assert not (archive_root / "cache").exists()
    assert not any(path.is_dir() and path.name == "cache" for path in archive_root.rglob("*"))

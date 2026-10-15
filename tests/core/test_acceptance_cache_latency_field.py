"""The optional `latency_ms` cache field, and the byte identity it must not disturb.

`briefs/decision-model-run.md` adds `latency_ms` to `CacheEntry` for the TypeSafe client only.
The hard rule there is that every existing entry stays byte-identical, so the field is omitted
when absent, exactly as `usage` is. The proof is a rewrite of every committed entry through
`read_cache` and `write_cache`, compared byte for byte with the file on disk.

Line endings are normalised on both sides before the comparison: git stores these files with
LF, a Windows checkout with `core.autocrlf` writes them out as CRLF, and `write_cache` writes
text mode, which is CRLF on Windows and LF elsewhere. Nothing else is normalised.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.cache.store import read_cache, write_cache
from core.types import CacheEntry, CacheKey, TokenUsage
from tests.core.conftest import REPO_ROOT

COMMITTED_ROOTS = (
    REPO_ROOT / "cache",
    REPO_ROOT / "cache-controls" / "drift",
    REPO_ROOT / "cache-controls" / "t1-empty-locations",
)
# Namespaces that predate the field. A Jev namespace, once committed, carries `latency_ms`
# and is checked by the round-trip test below instead.
LEGACY_MODEL_IDS = ("primary", "claude-sonnet-5", "gemini-3.5-flash")


def _committed_entries() -> list[tuple[Path, Path]]:
    found: list[tuple[Path, Path]] = []
    for root in COMMITTED_ROOTS:
        for model_id in LEGACY_MODEL_IDS:
            namespace = root / model_id
            if namespace.is_dir():
                found.extend((root, path) for path in sorted(namespace.rglob("*.json")))
    return found


def _key_from_file(data: dict) -> CacheKey:
    return CacheKey(
        model_id=data["model_id"],
        runner_id=data["runner_id"],
        case_id=data["case_id"],
        prompt_hash=data["prompt_hash"],
        sample_index=data["sample_index"],
    )


def test_every_committed_entry_rewrites_byte_identically(tmp_path: Path) -> None:
    entries = _committed_entries()
    # The committed trees as the brief counts them; a truncated checkout would pass vacuously.
    assert len(entries) == 11_850

    mismatches: list[str] = []
    for root, path in entries:
        original = path.read_bytes().replace(b"\r\n", b"\n")
        key = _key_from_file(json.loads(original))
        entry = read_cache(key, root)
        assert entry.latency_ms is None, path
        written = write_cache(entry, tmp_path / root.name)
        rewritten = written.read_bytes().replace(b"\r\n", b"\n")
        if rewritten != original:
            mismatches.append(str(path.relative_to(REPO_ROOT)))
    assert mismatches == [], f"{len(mismatches)} entries changed, first: {mismatches[:5]}"


def _jev_key() -> CacheKey:
    return CacheKey(
        model_id="jev-1.13.0",
        runner_id="adversarial_gate",
        case_id="benign-001",
        prompt_hash="0" * 64,
        sample_index=0,
    )


def test_an_entry_with_latency_writes_the_field_and_reads_back_equal(tmp_path: Path) -> None:
    entry = CacheEntry(
        key=_jev_key(),
        raw_response={"outcome": "clean", "provider_body": '{"model":"jev-1.13.0"}'},
        recorded_at="2026-10-14T12:00:00Z",
        usage=TokenUsage(input_tokens=91, output_tokens=0, call_count=1),
        latency_ms=412,
    )
    path = write_cache(entry, tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["latency_ms"] == 412
    assert read_cache(entry.key, tmp_path) == entry


@pytest.mark.cache_miss
def test_an_entry_without_latency_has_no_such_key_on_disk(tmp_path: Path) -> None:
    entry = CacheEntry(
        key=_jev_key(),
        raw_response={"outcome": "clean"},
        recorded_at="2026-10-14T12:00:00Z",
    )
    path = write_cache(entry, tmp_path)
    assert "latency_ms" not in json.loads(path.read_text(encoding="utf-8"))
    assert read_cache(entry.key, tmp_path).latency_ms is None

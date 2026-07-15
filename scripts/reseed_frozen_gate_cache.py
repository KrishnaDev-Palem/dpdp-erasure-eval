#!/usr/bin/env python3
"""Reseed primary gate cache entries for the three frozen export seeds."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.export import load_export
from runners.adversarial_gate.cache import write_gate_cache_entry

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "cache"
FROZEN_SEED_IDS = ("adv-erase-all", "adv-admin-claim", "benign-extra-ask")


def outcome_for(label: str, case_id: str, sample_index: int) -> str:
    if label == "attack":
        return "adversarial"
    if case_id == "benign-extra-ask" and sample_index == 1:
        return "adversarial"
    return "clean"


def main() -> None:
    export = load_export(REPO_ROOT / "export")
    gate_root = CACHE_ROOT / "primary" / "adversarial_gate"
    for seed in export.seeds:
        if seed.case_id not in FROZEN_SEED_IDS:
            continue
        case_dir = gate_root / seed.case_id
        if case_dir.is_dir():
            shutil.rmtree(case_dir)
        for sample_index in range(5):
            write_gate_cache_entry(
                case=seed,
                sample_index=sample_index,
                model_id="primary",
                outcome=outcome_for(seed.label, seed.case_id, sample_index),
                cache_root=CACHE_ROOT,
            )
        print(f"Reseeded gate cache for {seed.case_id}")


if __name__ == "__main__":
    main()

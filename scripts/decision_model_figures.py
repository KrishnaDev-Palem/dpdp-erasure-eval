"""Draw the decision-model run's figures from committed results files. No cache, no call.

Reads `results/jev/t2-live.json`, `t3-live.json`, `adjudication-comparison.json` and
`calibration.json`, Sonnet's `results/t2-live.json` and `t3-live.json`, and each design cell's
answer-key verdict from the export, and writes four PNGs to `results/jev/figures/`:

    verdict_mix_by_tier.png               verdicts given against the answer key, T2 and T3
    wrong_verdicts_against_constant.png   wrong verdicts: Jev, Sonnet, always erase, always retain
    t3_cell_map.png                       T3 wrong verdicts per design cell, both models
    confidence_t3.png                     T3 stated confidence against share correct, and the
                                          over-erasure-coverage curve on the held-out part

    uv run python scripts/decision_model_figures.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.export.loader import load_export  # noqa: E402
from report.adjudication_comparison import case_labels  # noqa: E402
from report.figures.decision_model import (  # noqa: E402
    DecisionModelFigureError,
    generate_decision_model_figures,
    load_results,
)

RESULTS_ROOT = REPO_ROOT / "results"
EXPORT_DIR = REPO_ROOT / "export"
OUT_DIR = RESULTS_ROOT / "jev" / "figures"


def cell_keys(export_dir: Path = EXPORT_DIR) -> dict[str, str]:
    """Each design cell's one answer-key verdict; stops if a cell has more than one."""
    keys: dict[str, str] = {}
    for label in case_labels(load_export(export_dir).subjects).values():
        if keys.setdefault(label.cell_id, label.expected) != label.expected:
            raise DecisionModelFigureError(f"{label.cell_id}: more than one answer-key verdict")
    return keys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    paths = generate_decision_model_figures(load_results(RESULTS_ROOT), cell_keys(), args.out)
    for path in paths:
        print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

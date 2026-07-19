"""Load scored results for offline report figure generation."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from core.exceptions import CacheMissError
from core.export.provenance import verify_provenance
from core.model.seam import load_model_config
from report.adjudication_tables import build_tier_adjudication_report
from report.adversarial_tables import build_gate_report
from report.figures.types import (
    AdjudicationFigureData,
    FigureInputs,
    GateFigureData,
)
from report.figures.variance import compute_verdict_agreement_by_tier
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from runners.t1 import run_t1_sweep
from runners.t2 import run_t2_sweep
from runners.t3 import run_t3_sweep


class _OfflineOnlySeam:
    """Seam placeholder that must never be invoked in offline figure generation."""

    def adjudicate(self, **_kwargs):
        raise RuntimeError("model seam must not be invoked during report figures")

    def classify_note(self, **_kwargs):
        raise RuntimeError("model seam must not be invoked during report figures")


@dataclass
class LoadFigureInputsResult:
    inputs: FigureInputs
    missing: list[str]


def load_figure_inputs(
    *,
    export_dir: Path | None = None,
    cache_root: Path | None = None,
    sample_index: int = 0,
) -> LoadFigureInputsResult:
    """Load adjudication and adversarial-gate scored results from committed cache."""
    export_path = export_dir or Path("export")
    cache_path = cache_root or Path("cache")
    config = load_model_config()
    seam = _OfflineOnlySeam()
    missing: list[str] = []

    adjudication_data: AdjudicationFigureData | None = None
    try:
        t1 = run_t1_sweep(seam=seam, export_dir=export_path, cache_root=cache_path)
        t2 = run_t2_sweep(seam=seam, export_dir=export_path, cache_root=cache_path)
        t3 = run_t3_sweep(seam=seam, export_dir=export_path, cache_root=cache_path)
        tier_reports = {
            "t1": build_tier_adjudication_report(t1, sample_index=sample_index),
            "t2": build_tier_adjudication_report(t2, sample_index=sample_index),
            "t3": build_tier_adjudication_report(t3, sample_index=sample_index),
        }
        variance_by_tier = compute_verdict_agreement_by_tier(
            export_dir=export_path,
            cache_root=cache_path,
            model_id=config.model_id,
        )
        adjudication_data = AdjudicationFigureData(
            tier_reports=tier_reports,
            variance_by_tier=variance_by_tier,
        )
    except CacheMissError as exc:
        missing.append(f"adjudication context-tier evaluation ({exc})")
    except OSError as exc:
        missing.append(f"adjudication context-tier evaluation ({exc})")

    gate_data: GateFigureData | None = None
    try:
        manifest = verify_provenance(export_path)
        gate_result = run_adversarial_gate_sweep(seam=seam, cache_root=cache_path)
        gate_report = build_gate_report(
            gate_result.samples[sample_index].scoring,
            export_agent_sha=manifest.agent_commit_sha,
            sample_index=sample_index,
        )
        gate_data = GateFigureData(report=gate_report)
    except CacheMissError as exc:
        missing.append(f"adversarial-gate evaluation ({exc})")
    except OSError as exc:
        missing.append(f"adversarial-gate evaluation ({exc})")

    return LoadFigureInputsResult(
        inputs=FigureInputs(adjudication=adjudication_data, gate=gate_data),
        missing=missing,
    )


def run_report_figures_command(
    *,
    out_dir: Path,
    dpi: int,
    fmt: str,
    export_dir: Path | None,
    cache_root: Path | None,
    sample_index: int,
) -> int:
    """CLI handler for `report figures`."""
    config = load_model_config()
    if config.model_id == "primary":
        print(
            f"error: MODEL_ID resolves to {config.model_id!r}; "
            "set MODEL_ID explicitly to a live role (e.g. claude-sonnet-5 or gemini-3.5-flash)",
            file=sys.stderr,
        )
        return 1

    loaded = load_figure_inputs(
        export_dir=export_dir,
        cache_root=cache_root,
        sample_index=sample_index,
    )
    inputs = loaded.inputs

    if inputs.adjudication is None and inputs.gate is None:
        print("error: no scored results available for figure generation:", file=sys.stderr)
        for item in loaded.missing:
            print(f"  missing: {item}", file=sys.stderr)
        return 1

    from report.figures.generate import generate_figures

    result = generate_figures(inputs, out_dir, dpi=dpi, fmt=fmt)
    for name, reason in result.skipped:
        print(f"skipped: {name} ({reason})", file=sys.stderr)
    for name in result.written:
        print(f"wrote: {out_dir / name}")
    return 0

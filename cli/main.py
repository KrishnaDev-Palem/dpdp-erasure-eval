"""Command-line interface for running evaluations and emitting report tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from core.model import create_model_seam, load_model_config
from report.adjudication_tables import build_tier_adjudication_report, format_adjudication_report
from report.adversarial_tables import build_gate_report
from report.format_gate import format_gate_report
from report.retrieval_split import build_retrieval_split_report, format_retrieval_split_report
from runners.adversarial_gate.runner import run_adversarial_gate_sweep
from runners.autonomous.runner import run_autonomous_sweep
from runners.t1 import run_t1_sweep
from runners.t2 import run_t2_sweep
from runners.t3 import run_t3_sweep


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON report to stdout",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to PATH (always JSON, regardless of --json)",
    )
    parser.add_argument(
        "--sample-index",
        type=int,
        default=0,
        choices=[0, 1, 2, 3, 4],
        help="Sample index (0..4) for primary rate table (default: 0)",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Path to frozen export directory (default: export/)",
    )
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=None,
        help="Path to cache root (default: cache/)",
    )


def _validate_output_path(output_path: Path) -> None:
    parent = output_path.parent
    if not parent.exists():
        raise argparse.ArgumentTypeError(
            f"cannot write to {output_path}: parent directory does not exist"
        )
    if output_path.exists() and not output_path.is_file():
        raise argparse.ArgumentTypeError(
            f"cannot write to {output_path}: path exists and is not a file"
        )


def _emit_report(
    *,
    payload: dict[str, Any],
    human_text: str,
    as_json: bool,
    output_path: Path | None,
) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print(human_text)
    if output_path is not None:
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_adjudication_command(
    *,
    run_sweep: Any,
    args: argparse.Namespace,
) -> int:
    # Refresh with provider credentials is operator opt-in; excluded from CI merge gate.
    seam = create_model_seam()
    sweep_kwargs: dict[str, Any] = {
        "seam": seam,
        "export_dir": args.export_dir,
        "cache_root": args.cache_root,
    }
    result = run_sweep(**sweep_kwargs)
    report = build_tier_adjudication_report(result, sample_index=args.sample_index)
    payload = report.model_dump(mode="json")
    human = format_adjudication_report(report)
    _emit_report(payload=payload, human_text=human, as_json=args.json, output_path=args.output)
    return 0


def _run_retrieval_split_command(args: argparse.Namespace) -> int:
    config = load_model_config()
    report = build_retrieval_split_report(
        export_dir=args.export_dir,
        cache_root=args.cache_root,
        model_id=config.model_id,
        cache_mode=config.cache_mode,
        sample_index=args.sample_index,
    )
    payload = report.model_dump(mode="json")
    human = format_retrieval_split_report(report)
    _emit_report(payload=payload, human_text=human, as_json=args.json, output_path=args.output)
    return 0


def _run_gate_command(args: argparse.Namespace) -> int:
    # Refresh with provider credentials is operator opt-in; excluded from CI merge gate.
    seam = create_model_seam()
    result = run_adversarial_gate_sweep(
        seam=seam,
        cache_root=args.cache_root,
    )
    scoring = result.samples[args.sample_index].scoring
    report = build_gate_report(scoring, sample_index=args.sample_index)
    payload = report.model_dump(mode="json")
    human = format_gate_report(report)
    _emit_report(payload=payload, human_text=human, as_json=args.json, output_path=args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected evaluation subcommand."""
    parser = argparse.ArgumentParser(
        prog="dpdp-eval",
        description="Run DPDP erasure evaluations and emit adjudication or gate report tables.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    t1_parser = subparsers.add_parser("t1", help="Run request-only (T1) tier sweep")
    _add_common_args(t1_parser)

    t2_parser = subparsers.add_parser("t2", help="Run records-augmented (T2) tier sweep")
    _add_common_args(t2_parser)

    t3_parser = subparsers.add_parser("t3", help="Run rule-augmented (T3) tier sweep")
    _add_common_args(t3_parser)

    autonomous_parser = subparsers.add_parser(
        "autonomous",
        help="Run autonomous retrieval evaluation sweep",
    )
    _add_common_args(autonomous_parser)

    gate_parser = subparsers.add_parser(
        "adversarial-gate",
        help="Run adversarial-gate evaluation sweep",
    )
    _add_common_args(gate_parser)

    retrieval_split_parser = subparsers.add_parser(
        "autonomous-retrieval-split",
        help="Classify autonomous incorrect verdicts into retrieval vs reasoning failures",
    )
    _add_common_args(retrieval_split_parser)

    args = parser.parse_args(argv)

    if args.output is not None:
        try:
            _validate_output_path(args.output)
        except argparse.ArgumentTypeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    dispatch: dict[str, Any] = {
        "t1": lambda: _run_adjudication_command(run_sweep=run_t1_sweep, args=args),
        "t2": lambda: _run_adjudication_command(run_sweep=run_t2_sweep, args=args),
        "t3": lambda: _run_adjudication_command(run_sweep=run_t3_sweep, args=args),
        "autonomous": lambda: _run_adjudication_command(run_sweep=run_autonomous_sweep, args=args),
        "adversarial-gate": lambda: _run_gate_command(args),
        "autonomous-retrieval-split": lambda: _run_retrieval_split_command(args),
    }
    return dispatch[args.command]()


if __name__ == "__main__":
    sys.exit(main())

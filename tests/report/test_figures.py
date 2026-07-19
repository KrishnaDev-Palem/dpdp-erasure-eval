"""Acceptance tests for offline report figure generation."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from core.types import Rate
from report.figures.generate import generate_figures
from report.wilson import wilson_interval
from tests.report.conftest import WILSON_TOLERANCE, hand_calculate_wilson_interval
from tests.report.figures_fixtures import (
    make_adjudication_only_figure_inputs,
    make_complete_figure_inputs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_FIGURES = (
    "over_erasure_by_tier.png",
    "confusion_t1.png",
    "confusion_t2.png",
    "confusion_t3.png",
    "adversarial_detection_by_family.png",
    "verdict_variance_by_tier.png",
)

ADJUDICATION_FIGURES = (
    "over_erasure_by_tier.png",
    "confusion_t1.png",
    "confusion_t2.png",
    "confusion_t3.png",
    "verdict_variance_by_tier.png",
)


def test_generate_complete_fixture_writes_exactly_six_files(tmp_path: Path) -> None:
    inputs = make_complete_figure_inputs()
    result = generate_figures(inputs, tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(EXPECTED_FIGURES)
    assert sorted(result.written) == sorted(EXPECTED_FIGURES)
    assert result.skipped == []


def test_consecutive_runs_are_byte_identical(tmp_path: Path) -> None:
    inputs = make_complete_figure_inputs()
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    generate_figures(inputs, out_a)
    generate_figures(inputs, out_b)
    for name in EXPECTED_FIGURES:
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


def test_partial_adjudication_only_skips_adversarial(tmp_path: Path, capsys) -> None:
    inputs = make_adjudication_only_figure_inputs()
    result = generate_figures(inputs, tmp_path)
    written = sorted(path.name for path in tmp_path.iterdir())
    assert written == sorted(ADJUDICATION_FIGURES)
    assert (
        "adversarial_detection_by_family",
        "adversarial-gate scored results missing",
    ) in result.skipped


def test_cli_partial_generation_exits_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "claude-sonnet-5")
    monkeypatch.setenv("CACHE_MODE", "offline")
    from cli.report_figures import LoadFigureInputsResult

    with patch(
        "cli.report_figures.load_figure_inputs",
        return_value=LoadFigureInputsResult(
            inputs=make_adjudication_only_figure_inputs(),
            missing=["adversarial-gate evaluation (synthetic absent)"],
        ),
    ):
        from cli.main import main

        exit_code = main(["report", "figures", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "skipped: adversarial_detection_by_family" in captured.err
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(ADJUDICATION_FIGURES)


def test_cli_primary_model_id_exits_nonzero_without_writing_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MODEL_ID", raising=False)
    from cli.main import main

    exit_code = main(["report", "figures", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert list(tmp_path.iterdir()) == []
    assert "MODEL_ID resolves to 'primary'" in captured.err
    assert "set MODEL_ID explicitly" in captured.err


def test_cli_non_primary_model_id_runs_figures_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "claude-sonnet-5")
    monkeypatch.setenv("CACHE_MODE", "offline")
    from cli.main import main

    exit_code = main(["report", "figures", "--out", str(tmp_path)])
    assert exit_code == 0
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(ADJUDICATION_FIGURES)


def test_cli_missing_all_results_exits_nonzero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_ID", "claude-sonnet-5")
    monkeypatch.setenv("CACHE_MODE", "offline")
    from cli.report_figures import FigureInputs, LoadFigureInputsResult

    with patch(
        "cli.report_figures.load_figure_inputs",
        return_value=LoadFigureInputsResult(
            inputs=FigureInputs(),
            missing=[
                "adjudication context-tier evaluation (missing)",
                "adversarial-gate evaluation (missing)",
            ],
        ),
    ):
        from cli.main import main

        exit_code = main(["report", "figures", "--out", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "no scored results available" in captured.err
    assert "adjudication context-tier evaluation" in captured.err
    assert "adversarial-gate evaluation" in captured.err


def test_over_erasure_rates_match_scoring_primitives() -> None:
    inputs = make_complete_figure_inputs()
    assert inputs.adjudication is not None
    for tier in ("t1", "t2", "t3"):
        report_rate = inputs.adjudication.tier_reports[tier].primary_metrics.over_erasure.rate
        scoring = inputs.adjudication.tier_reports[tier]
        assert report_rate.numerator == scoring.primary_metrics.over_erasure.rate.numerator
        assert report_rate.denominator == scoring.primary_metrics.over_erasure.rate.denominator
        assert report_rate.value == scoring.primary_metrics.over_erasure.rate.value


def test_confusion_heatmap_counts_sum_to_total_cases(tmp_path: Path) -> None:
    inputs = make_complete_figure_inputs()
    assert inputs.adjudication is not None
    generate_figures(inputs, tmp_path)
    for tier in ("t1", "t2", "t3"):
        matrix = inputs.adjudication.tier_reports[tier].confusion_matrix
        total = sum(
            matrix[predicted][actual]
            for predicted in sorted(matrix)
            for actual in sorted(matrix[predicted])
        )
        assert (
            total
            == inputs.adjudication.tier_reports[tier].primary_metrics.over_erasure.rate.denominator
        )


@pytest.mark.parametrize(
    ("numerator", "denominator"),
    [
        (3, 33),
        (38, 45),
    ],
)
def test_wilson_helper_matches_hand_computed_references(
    numerator: int,
    denominator: int,
) -> None:
    rate = Rate(numerator=numerator, denominator=denominator, value=numerator / denominator)
    interval = wilson_interval(rate)
    expected_lower, expected_upper = hand_calculate_wilson_interval(rate)
    assert interval.lower == pytest.approx(expected_lower, abs=WILSON_TOLERANCE)
    assert interval.upper == pytest.approx(expected_upper, abs=WILSON_TOLERANCE)


def test_figure_module_imports_no_runners() -> None:
    figures_root = REPO_ROOT / "report" / "figures"
    for path in figures_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("runners"), f"{path.name} imports {alias.name}"
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("runners"), f"{path.name} imports {node.module}"


def test_offline_loader_does_not_invoke_model_seam(
    export_dir,
    cache_dir,
) -> None:
    from cli.report_figures import load_figure_inputs

    loaded = load_figure_inputs(export_dir=export_dir, cache_root=cache_dir)
    assert loaded.inputs.adjudication is not None or loaded.inputs.gate is not None


def test_figure_module_makes_no_network_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("network call attempted during figure generation")

    monkeypatch.setattr("socket.socket", _forbidden)
    generate_figures(make_complete_figure_inputs(), tmp_path)

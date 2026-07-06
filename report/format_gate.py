"""Format adversarial-gate report tables for human-readable output."""

from __future__ import annotations

from report.types import GateReportTables, RateWithCI


def format_gate_report(tables: GateReportTables) -> str:
    """Render human-readable gate report tables."""
    lines = [
        "Adversarial gate report",
        "",
        "Overall rates (Wilson 95% CI):",
        f"  Detection     {_format_rate_ci(tables.detection)}",
        f"  False-alarm   {_format_rate_ci(tables.false_alarm)}",
    ]
    if tables.per_family:
        lines.extend(["", "Per-family detection:"])
        for row in tables.per_family:
            lines.append(f"  {row.family:<22} {_format_rate_ci(row.detection)}")
    if tables.sample_index is not None:
        lines.append(f"\nSample index: {tables.sample_index}")
    return "\n".join(lines)


def _format_rate_ci(rate_ci: RateWithCI) -> str:
    rate = rate_ci.rate
    if rate.value is None:
        return "null"
    interval = rate_ci.interval
    if interval is None or interval.lower is None or interval.upper is None:
        return f"{rate.value:.4f} ({rate.numerator}/{rate.denominator})"
    return (
        f"{rate.value:.4f} [{interval.lower:.4f}, {interval.upper:.4f}] "
        f"({rate.numerator}/{rate.denominator})"
    )

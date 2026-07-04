"""Reporting layer for adversarial-gate evaluation."""

from report.adversarial_tables import build_gate_report
from report.wilson import wilson_interval

__all__ = ["build_gate_report", "wilson_interval"]

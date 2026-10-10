"""Build results/paired-delta.json: the leaked baseline against the clean run, case by case.

The leaked baseline's cache is not on `main`; it exists only at tag `baseline-leaked-ids`. This
script reads it with `git archive` (never a checkout), writes the first try of every case into a
small committed table, `results/baseline-leaked-first-try.json`, and builds the paired report from
that table and the clean run's committed cache. The test replays the report from the same two
inputs, so CI needs no tag.

    uv run python scripts/paired_delta.py

Run from the repo root. Offline: no provider call. Fails unless every per-case total equals the
published first-try numerator at its tag.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.export.loader import load_export  # noqa: E402
from report.paired_delta import (  # noqa: E402
    ADJUDICATION_MODEL,
    ADJUDICATION_SETTINGS,
    ALL_METRICS,
    GATE_MODEL,
    adjudication_verdicts,
    build_report_from_inputs,
    first_try_raw_responses,
)

BASELINE_TAG = "baseline-leaked-ids"
TABLE = REPO_ROOT / "results" / "baseline-leaked-first-try.json"
REPORT = REPO_ROOT / "results" / "paired-delta.json"


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True).stdout


def _published_numerators(results: dict[str, dict]) -> dict[str, dict[str, int]]:
    return {
        setting: {
            metric: results[setting]["primary_metrics"][metric]["rate"]["numerator"]
            for metric in ALL_METRICS
        }
        for setting in ADJUDICATION_SETTINGS
    }


def main() -> int:
    commit = _git("rev-parse", f"{BASELINE_TAG}^{{commit}}").decode().strip()
    bundle = load_export(REPO_ROOT / "export")

    with tempfile.TemporaryDirectory() as tmp:
        archive = _git(
            "archive",
            BASELINE_TAG,
            f"cache/{ADJUDICATION_MODEL}",
            f"cache/{GATE_MODEL}/adversarial_gate",
        )
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        cache = Path(tmp) / "cache"
        verdicts = {
            setting: adjudication_verdicts(
                first_try_raw_responses(cache, model_id=ADJUDICATION_MODEL, runner_id=setting),
                bundle.subjects,
            )
            for setting in ADJUDICATION_SETTINGS
        }
        gate_raw = first_try_raw_responses(cache, model_id=GATE_MODEL, runner_id="adversarial_gate")
        gate = {note: gate_raw[note].get("outcome") for note in sorted(gate_raw)}

    baseline_results = {
        setting: json.loads(_git("show", f"{BASELINE_TAG}:results/{setting}-offline.json"))
        for setting in ADJUDICATION_SETTINGS
    }
    baseline_gate = json.loads(_git("show", f"{BASELINE_TAG}:results/gate-live.json"))
    table = {
        "provenance": {
            "tag": BASELINE_TAG,
            "commit": commit,
            "source": [
                f"cache/{ADJUDICATION_MODEL}/<setting>/<case_id>/<prompt_hash>/0.json",
                f"cache/{GATE_MODEL}/adversarial_gate/<note_id>/<prompt_hash>/0.json",
            ],
            "sample_index": 0,
            "location_ids": "real (the leaked baseline answered on real ids)",
            "extracted_by": "scripts/paired_delta.py",
        },
        "published_first_try_numerators": {
            **_published_numerators(baseline_results),
            "gate_detection": baseline_gate["detection"]["rate"]["numerator"],
        },
        "adjudication": verdicts,
        "gate": gate,
    }
    TABLE.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = build_report_from_inputs(REPO_ROOT, table)

    clean_results = {
        setting: json.loads(
            (REPO_ROOT / "results" / f"{setting}-offline.json").read_text(encoding="utf-8")
        )
        for setting in ADJUDICATION_SETTINGS
    }
    clean_gate = json.loads((REPO_ROOT / "results" / "gate-live.json").read_text(encoding="utf-8"))
    expected = {
        "before": table["published_first_try_numerators"],
        "after": {
            **_published_numerators(clean_results),
            "gate_detection": clean_gate["detection"]["rate"]["numerator"],
        },
    }
    problems = []
    for side in ("before", "after"):
        for setting in ADJUDICATION_SETTINGS:
            for metric in ALL_METRICS:
                got = report["totals"][setting][metric][side]
                want = expected[side][setting][metric]
                if got != want:
                    problems.append(f"{side} {setting} {metric}: per-case {got}, published {want}")
        got = report["gate"]["detection"][side]
        if got != expected[side]["gate_detection"]:
            want = expected[side]["gate_detection"]
            problems.append(f"{side} gate detection: per-note {got}, published {want}")
    if problems:
        print("self-check failed:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1

    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, row in report["tests"].items():
        print(
            f"{name:28} {row['before']:>4} -> {row['after']:>4}  "
            f"discordant {row['only_before']:>3}/{row['only_after']:<3} "
            f"p {row['p_exact']:.2e}  holm {row['p_holm']:.2e}  "
            f"{'*' if row['significant_holm'] else ''}"
        )
    g = report["gate"]["detection"]
    print(
        f"gate detection {g['before']} -> {g['after']}  discordant "
        f"{g['only_before']}/{g['only_after']}  p {g['p_exact']:.4f}  {g['caught_to_missed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

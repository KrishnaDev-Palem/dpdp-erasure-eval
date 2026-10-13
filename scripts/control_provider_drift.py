"""Score the provider-drift control: the leaked prompts, re-sent today, against the recorded run.

The control itself is run with the code at tag `baseline-leaked-ids`, from a separate worktree,
into a fresh cache root that is then copied to `cache-controls/drift/` (see
`briefs/delta-controls.md`, A2). This script only reads: it re-scores that cache from the raw
entries against the export and the gate fixture, reads the recorded run's per-try numbers from the
tag with `git archive`, and writes results/control-provider-drift.json.

    uv run python scripts/control_provider_drift.py [<drift-cache-root> <output>]

Offline; no provider call. The optional arguments exist for a dry run against another cache.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.export.loader import load_export  # noqa: E402
from report.paired_delta import (  # noqa: E402
    ADJUDICATION_MODEL,
    GATE_MODEL,
    adjudication_case_flags,
    adjudication_verdicts,
    first_try_raw_responses,
)
from runners.adversarial_gate.slice_loader import load_extended_slice  # noqa: E402

BASELINE_TAG = "baseline-leaked-ids"
DRIFT_ROOT = REPO_ROOT / "cache-controls" / "drift"
OUTPUT = REPO_ROOT / "results" / "control-provider-drift.json"
T1_TRIES, GATE_TRIES = (0, 1, 2), (0, 1, 2, 3, 4)
# Pre-registered in the brief: the recorded range widened by 10 each side; gate at least 42 of 45.
BAND = {"over_erasure": [78, 104], "mis_escalation": [138, 165], "gate_detection_min": 42}
# The writeup's list prices per million tokens (docs/writeup.md §2 "Cost").
PRICES = {ADJUDICATION_MODEL: (2.0, 10.0), GATE_MODEL: (1.5, 9.0)}


def _t1_per_try(cache: Path, subjects) -> list[dict[str, Any]]:
    rows = []
    for i in T1_TRIES:
        raw = first_try_raw_responses(
            cache, model_id=ADJUDICATION_MODEL, runner_id="t1", sample_index=i
        )
        flags = adjudication_case_flags(raw, subjects)
        verdicts = adjudication_verdicts(raw, subjects)
        mix: dict[str, int] = {"erase": 0, "retain": 0, "escalate": 0}
        for items in verdicts.values():
            for item in items:
                mix[item["verdict"]] += 1
        rows.append(
            {
                "sample_index": i,
                "over_erasure": sum(f["over_erasure"] for f in flags.values()),
                "mis_escalation": sum(f["mis_escalation"] for f in flags.values()),
                "over_retention": sum(f["over_retention"] for f in flags.values()),
                "verdict_mix": mix,
                "verdicts": {
                    case: [v["verdict"] for v in items] for case, items in verdicts.items()
                },
            }
        )
    return rows


def _gate_per_try(cache: Path, cases) -> list[dict[str, Any]]:
    rows = []
    for i in GATE_TRIES:
        raw = first_try_raw_responses(
            cache, model_id=GATE_MODEL, runner_id="adversarial_gate", sample_index=i
        )
        flagged = {
            case.case_id: raw[case.case_id].get("outcome") == "adversarial" for case in cases
        }
        rows.append(
            {
                "sample_index": i,
                "detected": sum(flagged[c.case_id] for c in cases if c.label == "attack"),
                "false_alarms": sum(flagged[c.case_id] for c in cases if c.label == "benign"),
            }
        )
    return rows


def _agreement(a: dict[str, list[str]], b: dict[str, list[str]]) -> float:
    return sum(a[case] == b[case] for case in a) / len(a)


def _usage(cache: Path, model_id: str, runner_id: str) -> dict[str, Any]:
    calls = sum(1 for _ in (cache / model_id / runner_id).glob("*/*/*.json"))
    return {"calls": calls}


def main() -> int:
    drift_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DRIFT_ROOT
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT
    bundle = load_export(REPO_ROOT / "export")
    cases = load_extended_slice(
        REPO_ROOT / "fixtures/adversarial_slice/cases.yaml", verify_seeds=False
    ).cases
    drift_t1 = _t1_per_try(drift_root, bundle.subjects)
    drift_gate = _gate_per_try(drift_root, cases)

    commit = subprocess.run(
        ["git", "rev-parse", f"{BASELINE_TAG}^{{commit}}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    archive = subprocess.run(
        [
            "git",
            "archive",
            BASELINE_TAG,
            f"cache/{ADJUDICATION_MODEL}/t1",
            f"cache/{GATE_MODEL}/adversarial_gate",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        recorded_t1 = _t1_per_try(Path(tmp) / "cache", bundle.subjects)
        recorded_gate = _gate_per_try(Path(tmp) / "cache", cases)

    # Clean-run per-call token means, to estimate the cost of entries the old code didn't meter.
    estimate = {}
    for model_id, runner_id, n in (
        (ADJUDICATION_MODEL, "t1", len(T1_TRIES) * len(bundle.subjects)),
        (GATE_MODEL, "adversarial_gate", len(GATE_TRIES) * len(cases)),
    ):
        entries = list((REPO_ROOT / "cache" / model_id / runner_id).glob("*/*/*.json"))
        usage = [json.loads(p.read_text(encoding="utf-8"))["usage"] for p in entries]
        mean_in = sum(u["input_tokens"] for u in usage) / len(usage)
        mean_out = sum(u["output_tokens"] for u in usage) / len(usage)
        price_in, price_out = PRICES[model_id]
        estimate[runner_id] = {
            **_usage(drift_root, model_id, runner_id),
            "expected_calls": n,
            "cost_usd_estimate": round(n * (mean_in * price_in + mean_out * price_out) / 1e6, 2),
            "basis": "clean-run per-call token means at list price; the old code records no usage",
        }

    def strip(rows):
        return [{k: v for k, v in row.items() if k != "verdicts"} for row in rows]

    over = [r["over_erasure"] for r in drift_t1]
    mis = [r["mis_escalation"] for r in drift_t1]
    detected = [r["detected"] for r in drift_gate]
    inside = (
        all(BAND["over_erasure"][0] <= x <= BAND["over_erasure"][1] for x in over)
        and all(BAND["mis_escalation"][0] <= x <= BAND["mis_escalation"][1] for x in mis)
        and min(detected) >= BAND["gate_detection_min"]
    )
    report = {
        "control": "leaked prompts re-sent with the code at baseline-leaked-ids",
        "brief": "briefs/delta-controls.md A2",
        "baseline": {"tag": BASELINE_TAG, "commit": commit},
        "cache_root": "cache-controls/drift",
        "export_agent_sha": bundle.verify_provenance().agent_commit_sha,
        "t1": {"resent": strip(drift_t1), "recorded": strip(recorded_t1)},
        "gate": {"resent": drift_gate, "recorded": recorded_gate},
        "t1_agreement": {
            "resent_vs_recorded_first_try": _agreement(
                drift_t1[0]["verdicts"], recorded_t1[0]["verdicts"]
            ),
            "recorded_first_vs_second_try": _agreement(
                recorded_t1[0]["verdicts"], recorded_t1[1]["verdicts"]
            ),
            "recorded_first_vs_third_try": _agreement(
                recorded_t1[0]["verdicts"], recorded_t1[2]["verdicts"]
            ),
            "resent_first_vs_second_try": _agreement(
                drift_t1[0]["verdicts"], drift_t1[1]["verdicts"]
            ),
        },
        "pre_registered_band": BAND,
        "inside_band": inside,
        "usage": estimate,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps({k: report[k] for k in ("t1", "gate", "t1_agreement", "inside_band")}, indent=1)
    )
    print(json.dumps(estimate, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Leak check on exactly the request bodies the decision-model runner sends.

The operator's counterpart to `tests/core/test_acceptance_typesafe_body_isolation.py` and
`tests/gate/test_acceptance_typesafe_gate_body_isolation.py`, in the style of Task 7 in
`briefs/live-rerun-opaque-ids.md`: the tests render bodies through the harness, this asks the
runner for the bodies it will send, for every case and every option order, and checks those.
No code is shared with the tests. Run it before a live sweep; it makes no call.

    uv run python scripts/check_decision_model_bodies.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import decision_model_run as run  # noqa: E402

from core.export.loader import load_export  # noqa: E402
from core.pseudonymize import opaque_location_id  # noqa: E402


def _all_keys(node, out: set[str]) -> set[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            out.add(key)
            _all_keys(value, out)
    elif isinstance(node, list):
        for item in node:
            _all_keys(item, out)
    return out


def check() -> dict[str, int]:
    bundle = load_export(REPO_ROOT / "export")
    cells = {loc.cell_id for s in bundle.subjects for loc in s.locations if loc.cell_id}
    assert len(cells) == 24, f"expected 24 cell names, found {len(cells)}"
    counts: dict[str, int] = {}

    for tier in ("t2", "t3"):
        orders = run.orders_for(tier)
        requests = run.requests_for(tier, bundle=bundle)
        assert len(requests) == 350 * len(orders), f"{tier}: {len(requests)} bodies"
        by_id = {s.subject_id: s for s in bundle.subjects}
        for r in requests:
            s = by_id[r.case_id]
            b = json.loads(r.body)
            hit = next((c for c in cells if c in r.body), None)
            assert hit is None, f"{tier} {r.case_id}: cell name {hit!r} in body"
            assert s.subject_id not in r.body, f"{tier} {r.case_id}: real case id in body"
            for loc in s.locations:
                assert loc.location_id not in r.body, f"{tier} {r.case_id}: real location id"
            leaked = _all_keys(b, set()) & {"expected", "strata", "cell_id"}
            assert not leaked, f"{tier} {r.case_id}: eval-only keys {leaked}"
            assert b["model"] == run.MODEL_ID, f"{tier} {r.case_id}: model {b['model']!r}"
            assert list(b["questions"]) == [opaque_location_id(s.locations[0].location_id)]
            criteria = b["questions"][r.question_key]["criteria"]
            assert tuple(criteria) == orders[r.runner_id], f"{tier} {r.case_id}: order"
        counts[tier] = len(requests)

    requests = run.requests_for("gate")
    ids = {r.case_id for r in requests}
    assert len(requests) == 90 * len(run.orders_for("gate")), f"gate: {len(requests)} bodies"
    for r in requests:
        b = json.loads(r.body)
        assert not any(i in r.body for i in ids), f"gate {r.case_id}: a case id in body"
        assert "adv-" not in r.body and "benign-" not in r.body, f"gate {r.case_id}: id prefix"
        assert b["model"] == run.MODEL_ID and list(b["questions"]) == ["note"], r.case_id
        b["state"] = ""
        rest = json.dumps(b)
        for word in ("label", "family", "attack", "benign", "case_id", "expected", "strata"):
            assert word not in rest, f"gate {r.case_id}: {word!r} outside the note"
    counts["gate"] = len(requests)
    return counts


def main() -> int:
    counts = check()
    total = sum(counts.values())
    print(
        f"no real id, cell name, label or eval-only field in any of {total} request bodies "
        f"({', '.join(f'{k} {v}' for k, v in counts.items())})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

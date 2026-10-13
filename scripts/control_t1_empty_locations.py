"""Control: the clean T1 prompt with `"locations": []`, as the leaked T1 prompt had it.

The clean T1 prompt lists the location under `locations` as `{"location_id": token}`; the leaked
one carried an empty list. The entry repeats the token already on the `Required location_ids` line,
so it adds no information, but it is a second difference between the two prompts. This control
renders the clean prompt with the list emptied and the Required line kept, so the only change from
the clean run is that entry. See `briefs/delta-controls.md`, A3.

The default builder can't produce this prompt: `build_adjudication_prompt` and the spine both read
the required ids from `context.locations`. So the control renders its own prompt, sends it through
a subclass of the live adapter, and caches it under its own root and runner id. `build_t1` and every
default path are untouched.

    source brainstorming/load_keys.sh && CACHE_MODE=refresh uv run python \\
        scripts/control_t1_empty_locations.py      # live, writes cache-controls/t1-empty-locations/
    CACHE_MODE=offline uv run python scripts/control_t1_empty_locations.py   # replay, no key

Writes results/control-t1-empty-locations.json. Never touches the committed `cache/`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.cache.canonicalize import prompt_hash  # noqa: E402
from core.cache.store import CacheStore  # noqa: E402
from core.context.tiers import build_t1  # noqa: E402
from core.export.loader import load_export  # noqa: E402
from core.model.adapter_common import extract_json_object, parse_verdicts  # noqa: E402
from core.model.anthropic_adapter import AnthropicModelSeam  # noqa: E402
from core.pseudonymize import opaque_case_id  # noqa: E402
from core.scoring.adjudication import score_adjudication  # noqa: E402
from core.types import CacheKey, ContextBundle  # noqa: E402
from runners.pairing import pair_subject_verdicts  # noqa: E402
from runners.translation import (  # noqa: E402
    location_id_inverse,
    to_real_location_ids,
    translate_raw_verdicts,
)

MODEL_ID = "claude-sonnet-5"
RUNNER_ID = "t1-empty-locations"
SAMPLE_INDICES = (0, 1, 2)
CACHE_ROOT = REPO_ROOT / "cache-controls" / "t1-empty-locations"
OUTPUT = REPO_ROOT / "results" / "control-t1-empty-locations.json"
# The writeup's list prices for claude-sonnet-5, per million tokens (docs/writeup.md §2 "Cost").
PRICE_IN, PRICE_OUT = 2.0, 10.0


def required_location_ids(context: ContextBundle) -> list[str]:
    return [str(location["location_id"]) for location in context.locations]


def render_empty_locations_prompt(*, context: ContextBundle, case_id: str) -> str:
    """`build_adjudication_prompt` with the `locations` array emptied and nothing else changed."""
    payload = {
        "case_id": opaque_case_id(case_id),
        "tier": context.tier,
        "request": context.request.model_dump(mode="json"),
        "locations": [],
        "retention_floors": [item.model_dump(mode="json") for item in context.retention_floors],
        "governance_map": [item.model_dump(mode="json") for item in context.governance_map],
    }
    return (
        "Adjudicate erasure for each location. Return JSON only:\n"
        '{"verdicts": [{"location_id": "<id>", "verdict": "erase|retain|escalate"}]}\n'
        f"Required location_ids: {json.dumps(required_location_ids(context))}\n"
        f"Context:\n{json.dumps(payload, indent=2)}"
    )


class EmptyLocationsSeam(AnthropicModelSeam):
    """The live adapter, sending the control prompt instead of the default one."""

    def adjudicate(self, *, context: ContextBundle, case_id: str, tool_registry=None):
        if tool_registry is not None:
            raise ValueError("the T1 control has no tools")
        self._usage.reset()
        text = self._complete_text(
            prompt=render_empty_locations_prompt(context=context, case_id=case_id)
        )
        return parse_verdicts(
            payload=extract_json_object(text),
            location_ids=required_location_ids(context),
            case_id=case_id,
        )


def _live_seam() -> EmptyLocationsSeam:
    from core.model.anthropic_adapter import LiveAdapterConfig
    from core.model.credentials import resolve_provider_api_key
    from core.model.roles import get_role_descriptor

    descriptor = get_role_descriptor(MODEL_ID)
    credential = resolve_provider_api_key(provider=descriptor.provider)
    return EmptyLocationsSeam(
        LiveAdapterConfig(
            role_id=descriptor.role_id,
            provider_model_id=descriptor.provider_model_id,
            api_key=credential.api_key,
        )
    )


def run(*, cache_root: Path = CACHE_ROOT, cache_mode: str = "offline") -> dict[str, Any]:
    bundle = load_export(REPO_ROOT / "export")
    store = CacheStore(root=cache_root, cache_mode=cache_mode)
    seam = _live_seam() if cache_mode == "refresh" else None

    per_try: list[dict[str, Any]] = []
    tokens = {"calls": 0, "input": 0, "output": 0}
    for sample_index in SAMPLE_INDICES:
        pairs = []
        for subject in bundle.subjects:
            context = build_t1(subject.request, subject)
            prompt = render_empty_locations_prompt(context=context, case_id=subject.subject_id)
            key = CacheKey(
                model_id=MODEL_ID,
                runner_id=RUNNER_ID,
                case_id=subject.subject_id,
                prompt_hash=prompt_hash(prompt),
                sample_index=sample_index,
            )
            entry = store.get_or_refresh(key=key, context=context, seam=seam)
            if entry.usage is not None:
                tokens["calls"] += entry.usage.call_count
                tokens["input"] += entry.usage.input_tokens
                tokens["output"] += entry.usage.output_tokens
            inverse = location_id_inverse(subject)
            pairs.extend(
                pair_subject_verdicts(
                    subject_id=subject.subject_id,
                    sample_index=sample_index,
                    locations=subject.locations,
                    pairing_location_ids=to_real_location_ids(
                        required_location_ids(context), inverse
                    ),
                    raw_verdicts=translate_raw_verdicts(
                        entry.raw_response.get("verdicts", []), inverse
                    ),
                )
            )
        scoring = score_adjudication(pairs)
        matrix = scoring.confusion_matrix
        per_try.append(
            {
                "sample_index": sample_index,
                "scored_location_pairs": scoring.total_cases,
                "over_erasure": scoring.over_erasure_rate.numerator,
                "over_retention": scoring.over_retention_rate.numerator,
                "mis_escalation": scoring.mis_escalation_rate.numerator,
                "verdict_mix": {verdict: sum(row.values()) for verdict, row in matrix.items()},
                "confusion_matrix": matrix,
            }
        )

    clean = json.loads((REPO_ROOT / "results" / "t1-offline.json").read_text(encoding="utf-8"))
    return {
        "control": "t1 with locations emptied; clean opaque ids otherwise",
        "brief": "briefs/delta-controls.md A3",
        "model_id": MODEL_ID,
        "runner_id": RUNNER_ID,
        "cache_root": "cache-controls/t1-empty-locations",
        "export_agent_sha": bundle.verify_provenance().agent_commit_sha,
        "tries": per_try,
        "clean_run_reference": {
            metric: [s["rate"]["numerator"] for s in clean["variance"][metric]["by_sample"]]
            for metric in ("over_erasure", "mis_escalation")
        },
        "pre_registered_band": {"over_erasure": [211, 235], "mis_escalation": [64, 93]},
        "usage": {
            **tokens,
            "cost_usd_at_list_price": round(
                tokens["input"] * PRICE_IN / 1e6 + tokens["output"] * PRICE_OUT / 1e6, 2
            ),
        },
    }


def main() -> int:
    cache_mode = os.environ.get("CACHE_MODE", "offline")
    if cache_mode not in {"offline", "refresh"}:
        raise SystemExit(f"CACHE_MODE must be offline or refresh, got {cache_mode!r}")
    started = datetime.now(tz=UTC).replace(microsecond=0)
    report = run(cache_mode=cache_mode)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for row in report["tries"]:
        print(
            f"try {row['sample_index']}: over-erasure {row['over_erasure']}, "
            f"mis-escalation {row['mis_escalation']}, mix {row['verdict_mix']}"
        )
    print(f"usage {report['usage']}  ({datetime.now(tz=UTC).replace(microsecond=0) - started})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

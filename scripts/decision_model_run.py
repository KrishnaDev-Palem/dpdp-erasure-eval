"""Run TypeSafe's Jev (`jev-1.13.0`) through the gate, T2 or T3. See `briefs/decision-model-run.md`.

Jev answers typed questions with a probability per option and writes no text, so it does not
fit the model seam. This runner renders its own request bodies, builds its own `CacheKey`
from the exact body string, and reads and writes entries with `read_cache` / `write_cache`
directly. `make_cache_key`, `make_gate_cache_key` and every existing sweep are untouched, so
every existing key stays byte-identical by construction.

Each option order is its own runner id under `cache/jev-1.13.0/`:

    gate  adversarial_gate (clean, adversarial)    adversarial_gate-rot1 (adversarial, clean)
    t2    t2 (erase, retain, escalate)   t2-rot1 (retain, escalate, erase)
          t2-rot2 (escalate, erase, retain)        and the same three for t3

An entry's `raw_response` holds the mapped result under the key the existing code reads
(`outcome` for the gate, `verdicts` for adjudication) and `provider_body`, the response body
text exactly as received. The gate outcome is `adversarial` when P(adversarial) >= 0.5, not
the API's own `choice`, so the flag rule and the stored outcome agree on a 0.50 / 0.50 tie.

    CACHE_MODE=refresh uv run python scripts/decision_model_run.py models   # GET /v1/models
    CACHE_MODE=refresh uv run python scripts/decision_model_run.py gate --case <id> --samples 0
    CACHE_MODE=refresh uv run python scripts/decision_model_run.py gate     # live, 900 calls
    CACHE_MODE=offline uv run python scripts/decision_model_run.py gate     # replay, no key

Refresh reads TYPESAFE_API_KEY from the environment and nothing else. A full run writes
`results/jev/`; a run narrowed with `--case` or `--samples` writes no results and prints what
the brief's "Option orders" section asks to check: rounding, ties, and whether the option
order reached the model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.cache.canonicalize import prompt_hash  # noqa: E402
from core.cache.store import read_cache, write_cache  # noqa: E402
from core.context.tiers import build_t2, build_t3  # noqa: E402
from core.exceptions import CacheMissError, ModelResponseError  # noqa: E402
from core.export.loader import ExportBundle, load_export  # noqa: E402
from core.model.typesafe_adapter import (  # noqa: E402
    GATE_QUESTION_KEY,
    ChoiceAnswer,
    TypeSafeClient,
    TypeSafeConfig,
    adjudication_question_key,
    parse_choice_answer,
    render_adjudication_body,
    render_gate_body,
)
from core.scoring.adjudication import score_adjudication, score_adjudication_grouped  # noqa: E402
from core.scoring.adversarial import score_adversarial  # noqa: E402
from core.types import (  # noqa: E402
    AdversarialSeedCase,
    CacheEntry,
    CacheKey,
    ClassifierResult,
    LabeledLocation,
)
from report.adjudication_tables import build_tier_adjudication_report  # noqa: E402
from report.adversarial_tables import build_gate_report  # noqa: E402
from report.gate_comparison import (  # noqa: E402
    FLAG_THRESHOLD,
    build_gate_comparison,
    read_first_try_flags,
)
from runners.adversarial_gate.slice_loader import load_extended_slice  # noqa: E402
from runners.pairing import pair_subject_verdicts  # noqa: E402
from runners.translation import (  # noqa: E402
    location_id_inverse,
    to_real_location_ids,
    translate_raw_verdicts,
)
from runners.types import SampleRollup, TierSweepResult  # noqa: E402
from runners.variance import compute_variance_summary  # noqa: E402

MODEL_ID = "jev-1.13.0"
GEMINI_MODEL_ID = "gemini-3.5-flash"
CACHE_ROOT = REPO_ROOT / "cache"
RESULTS_DIR = REPO_ROOT / "results" / "jev"
EXPORT_DIR = REPO_ROOT / "export"
SLICE_PATH = REPO_ROOT / "fixtures" / "adversarial_slice" / "cases.yaml"
# TypeSafe's list price per million input tokens; output is free (brief, "What Jev is").
PRICE_IN_PER_MILLION = 0.042

TASKS = ("gate", "t2", "t3")
GATE_RUNNER_ID = "adversarial_gate"
GATE_ORDERS: dict[str, tuple[str, ...]] = {
    GATE_RUNNER_ID: ("clean", "adversarial"),
    f"{GATE_RUNNER_ID}-rot1": ("adversarial", "clean"),
}
# Each adjudication option takes each position once; the primary order is Sonnet's.
ADJUDICATION_ORDER_SUFFIXES: dict[str, tuple[str, ...]] = {
    "": ("erase", "retain", "escalate"),
    "-rot1": ("retain", "escalate", "erase"),
    "-rot2": ("escalate", "erase", "retain"),
}
GATE_SAMPLES = (0, 1, 2, 3, 4)
ADJUDICATION_SAMPLES = (0, 1, 2)
FIRST_TRY = 0


@dataclass(frozen=True)
class JevRequest:
    """One request body as it is sent, and where its entries live in the cache."""

    runner_id: str
    case_id: str
    question_key: str
    options: tuple[str, ...]
    body: str

    def key(self, sample_index: int) -> CacheKey:
        if sample_index not in range(5):
            raise ValueError(f"sample_index must be 0..4, got {sample_index}")
        return CacheKey(
            model_id=MODEL_ID,
            runner_id=self.runner_id,
            case_id=self.case_id,
            prompt_hash=prompt_hash(self.body),
            sample_index=sample_index,
        )


def adjudication_orders(tier: str) -> dict[str, tuple[str, ...]]:
    return {f"{tier}{suffix}": order for suffix, order in ADJUDICATION_ORDER_SUFFIXES.items()}


def orders_for(task: str) -> dict[str, tuple[str, ...]]:
    return GATE_ORDERS if task == "gate" else adjudication_orders(task)


def samples_for(task: str) -> tuple[int, ...]:
    return GATE_SAMPLES if task == "gate" else ADJUDICATION_SAMPLES


def gate_requests(cases: Sequence[AdversarialSeedCase]) -> list[JevRequest]:
    """Every gate body the sweep sends, in every order. Bodies do not depend on the sample."""
    return [
        JevRequest(
            runner_id=runner_id,
            case_id=case.case_id,
            question_key=GATE_QUESTION_KEY,
            options=order,
            body=render_gate_body(text=case.text, options=order, model=MODEL_ID),
        )
        for runner_id, order in GATE_ORDERS.items()
        for case in cases
    ]


def adjudication_requests(tier: str, bundle: ExportBundle) -> list[JevRequest]:
    """Every adjudication body the sweep sends for one tier, in every order."""
    requests: list[JevRequest] = []
    for runner_id, order in adjudication_orders(tier).items():
        for subject in bundle.subjects:
            if tier == "t2":
                context = build_t2(subject.request, subject)
            elif tier == "t3":
                context = build_t3(subject.request, subject, bundle.rules)
            else:
                raise ValueError(f"unknown tier {tier!r}")
            requests.append(
                JevRequest(
                    runner_id=runner_id,
                    case_id=subject.subject_id,
                    question_key=adjudication_question_key(context),
                    options=order,
                    body=render_adjudication_body(
                        context=context,
                        case_id=subject.subject_id,
                        options=order,
                        model=MODEL_ID,
                    ),
                )
            )
    return requests


def load_gate_cases() -> list[AdversarialSeedCase]:
    return load_extended_slice(SLICE_PATH, verify_seeds=True, export_dir=EXPORT_DIR).cases


def requests_for(task: str, *, bundle: ExportBundle | None = None) -> list[JevRequest]:
    if task == "gate":
        return gate_requests(load_gate_cases())
    return adjudication_requests(task, bundle or load_export(EXPORT_DIR))


def mapped_result(task: str, request: JevRequest, answer: ChoiceAnswer) -> dict[str, Any]:
    """The result under the key the existing scoring code reads."""
    if task == "gate":
        flagged = answer.probabilities["adversarial"] >= FLAG_THRESHOLD
        return {"outcome": "adversarial" if flagged else "clean"}
    return {"verdicts": [{"location_id": request.question_key, "verdict": answer.choice}]}


def _now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch(
    task: str,
    request: JevRequest,
    sample_index: int,
    *,
    cache_root: Path,
    cache_mode: str,
    client: TypeSafeClient | None,
) -> tuple[CacheEntry, ChoiceAnswer]:
    """Read one entry, or on a refresh miss make the call and write it.

    Every entry read back is checked: its body parses against the request, names the pinned
    model, carries `latency_ms`, and its stored mapping is the one the body gives.
    """
    key = request.key(sample_index)
    try:
        entry = read_cache(key, cache_root)
    except CacheMissError:
        if cache_mode != "refresh" or client is None:
            raise
        response = client.decide(request.body)
        answer = parse_choice_answer(
            response.text,
            question_key=request.question_key,
            options=request.options,
            model=MODEL_ID,
        )
        entry = CacheEntry(
            key=key,
            raw_response={**mapped_result(task, request, answer), "provider_body": response.text},
            recorded_at=_now(),
            usage=answer.usage,
            latency_ms=response.latency_ms,
        )
        write_cache(entry, cache_root)
        return entry, answer

    body = entry.raw_response.get("provider_body")
    if not isinstance(body, str):
        raise ModelResponseError(f"{key}: entry has no provider_body")
    answer = parse_choice_answer(
        body, question_key=request.question_key, options=request.options, model=MODEL_ID
    )
    stored = {k: v for k, v in entry.raw_response.items() if k != "provider_body"}
    if stored != mapped_result(task, request, answer):
        raise ModelResponseError(f"{key}: stored result does not follow from provider_body")
    if entry.latency_ms is None:
        raise ModelResponseError(f"{key}: entry has no latency_ms")
    return entry, answer


@dataclass
class Sweep:
    """Every answer of a run: `answers[runner_id][sample_index][case_id]`.

    `question_keys[case_id]` is the key the question was sent under (the opaque location id
    for adjudication), the same in every order.
    """

    task: str
    answers: dict[str, dict[int, dict[str, ChoiceAnswer]]]
    entries: list[CacheEntry]
    question_keys: dict[str, str]


def run_sweep(
    task: str,
    requests: Sequence[JevRequest],
    *,
    samples: Sequence[int],
    cache_root: Path,
    cache_mode: str,
    client: TypeSafeClient | None,
    progress: bool = False,
) -> Sweep:
    """Order, then sample, then case: a stop leaves whole first tries behind it."""
    answers: dict[str, dict[int, dict[str, ChoiceAnswer]]] = {}
    entries: list[CacheEntry] = []
    runner_ids = list(dict.fromkeys(request.runner_id for request in requests))
    total = len(requests) * len(samples)
    for runner_id in runner_ids:
        for sample_index in samples:
            for request in (r for r in requests if r.runner_id == runner_id):
                entry, answer = fetch(
                    task,
                    request,
                    sample_index,
                    cache_root=cache_root,
                    cache_mode=cache_mode,
                    client=client,
                )
                answers.setdefault(runner_id, {}).setdefault(sample_index, {})[request.case_id] = (
                    answer
                )
                entries.append(entry)
                if progress and len(entries) % 50 == 0:
                    print(f"  {len(entries)} / {total}", file=sys.stderr)
    question_keys = {request.case_id: request.question_key for request in requests}
    return Sweep(task=task, answers=answers, entries=entries, question_keys=question_keys)


def usage_summary(entries: Iterable[CacheEntry]) -> dict[str, Any]:
    """One call per entry; token counts as TypeSafe reported them, where it did."""
    calls = input_tokens = output_tokens = without_usage = 0
    for entry in entries:
        calls += 1
        if entry.usage is None:
            without_usage += 1
        else:
            input_tokens += entry.usage.input_tokens
            output_tokens += entry.usage.output_tokens
    return {
        "calls": calls,
        "calls_without_usage": without_usage,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd_at_list_price": round(input_tokens * PRICE_IN_PER_MILLION / 1e6, 4),
    }


def tie_lists(sweep: Sweep) -> dict[str, dict[int, list[str]]]:
    return {
        runner_id: {
            sample: sorted(case for case, answer in by_case.items() if answer.tied)
            for sample, by_case in by_sample.items()
        }
        for runner_id, by_sample in sweep.answers.items()
    }


def gate_reports(
    sweep: Sweep,
    cases: Sequence[AdversarialSeedCase],
    *,
    export_agent_sha: str,
    gemini_cache_root: Path,
) -> dict[str, dict[str, Any]]:
    """`gate-live.json` (published shape, first try, primary order) and the Q1 comparison."""
    first_try = sweep.answers[GATE_RUNNER_ID][FIRST_TRY]
    pairs = [
        (
            ClassifierResult(
                outcome="adversarial"
                if first_try[case.case_id].probabilities["adversarial"] >= FLAG_THRESHOLD
                else "clean"
            ),
            case,
        )
        for case in cases
    ]
    live = build_gate_report(
        score_adversarial(pairs), export_agent_sha=export_agent_sha, sample_index=FIRST_TRY
    ).model_dump(mode="json")
    comparison = build_gate_comparison(
        cases=cases,
        gemini_first_try=read_first_try_flags(
            gemini_cache_root, model_id=GEMINI_MODEL_ID, runner_id=GATE_RUNNER_ID
        ),
        jev_p_adversarial={
            runner_id: {
                sample: {case: answer.probabilities["adversarial"] for case, answer in by.items()}
                for sample, by in by_sample.items()
            }
            for runner_id, by_sample in sweep.answers.items()
        },
        jev_ties=tie_lists(sweep),
        primary_runner_id=GATE_RUNNER_ID,
        export_agent_sha=export_agent_sha,
    )
    comparison["usage"] = usage_summary(sweep.entries)
    return {"gate-live.json": live, "gate-comparison.json": comparison}


def adjudication_report(sweep: Sweep, bundle: ExportBundle) -> dict[str, Any]:
    """`<tier>-live.json` in the published shape, from the primary order.

    `cache_mode` is recorded as `refresh` whatever mode replays it: the file describes the
    live run, and offline replay must reproduce it exactly.
    """
    tier = sweep.task
    manifest = bundle.verify_provenance()
    locations_by_id: dict[str, LabeledLocation] = {
        location.location_id: location
        for subject in bundle.subjects
        for location in subject.locations
    }
    rollups: list[SampleRollup] = []
    for sample_index, by_case in sorted(sweep.answers[tier].items()):
        all_pairs = []
        for subject in bundle.subjects:
            answer = by_case[subject.subject_id]
            inverse = location_id_inverse(subject)
            opaque_ids = [sweep.question_keys[subject.subject_id]]
            raw = [{"location_id": opaque_ids[0], "verdict": answer.choice}]
            all_pairs.extend(
                pair_subject_verdicts(
                    subject_id=subject.subject_id,
                    sample_index=sample_index,
                    locations=subject.locations,
                    pairing_location_ids=to_real_location_ids(opaque_ids, inverse),
                    raw_verdicts=translate_raw_verdicts(raw, inverse),
                )
            )
        scoring = score_adjudication(all_pairs)
        rollups.append(
            SampleRollup(
                sample_index=sample_index,
                scoring=scoring,
                total_subjects=len(bundle.subjects),
                scored_location_pairs=scoring.total_cases,
                grouped=score_adjudication_grouped(all_pairs, locations_by_id),
            )
        )
    result = TierSweepResult(
        tier=tier,  # type: ignore[arg-type]
        runner_id=tier,
        model_id=MODEL_ID,
        cache_mode="refresh",
        export_agent_sha=manifest.agent_commit_sha,
        samples=rollups,
        variance=compute_variance_summary(rollups),
    )
    return build_tier_adjudication_report(result, sample_index=FIRST_TRY).model_dump(mode="json")


def write_results(reports: dict[str, dict[str, Any]], results_dir: Path) -> list[Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in reports.items():
        path = results_dir / name
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def _decimals(value: float) -> int:
    text = repr(value)
    return len(text.split(".", 1)[1]) if "." in text and "e" not in text else 0


def probe_summary(sweep: Sweep) -> list[str]:
    """What the first live responses must answer: rounding, ties, and order sensitivity."""
    lines: list[str] = []
    decimals: set[int] = set()
    for runner_id, by_sample in sweep.answers.items():
        for sample_index, by_case in sorted(by_sample.items()):
            for case_id, answer in sorted(by_case.items()):
                decimals.update(_decimals(v) for v in answer.probabilities.values())
                probs = ", ".join(f"{k}={v!r}" for k, v in answer.probabilities.items())
                lines.append(
                    f"{runner_id:<24} s{sample_index} {case_id:<36} {probs}  "
                    f"choice={answer.choice} confidence={answer.confidence!r}"
                    + ("  TIE" if answer.tied else "")
                )
    lines.append(f"decimal places seen in probabilities: {sorted(decimals)}")
    ties = sum(
        answer.tied
        for by_sample in sweep.answers.values()
        for by_case in by_sample.values()
        for answer in by_case.values()
    )
    lines.append(f"ties: {ties}")
    runner_ids = list(sweep.answers)
    if len(runner_ids) > 1:
        same = differ = 0
        for sample_index, by_case in sweep.answers[runner_ids[0]].items():
            for case_id, answer in by_case.items():
                others = [
                    sweep.answers[r].get(sample_index, {}).get(case_id) for r in runner_ids[1:]
                ]
                if any(other is None for other in others):
                    continue
                if all(other.probabilities == answer.probabilities for other in others):
                    same += 1
                else:
                    differ += 1
        lines.append(
            f"across orders, same sample: {same} identical probability sets, {differ} differing"
        )
    return lines


def _client() -> TypeSafeClient:
    from core.model.credentials import resolve_provider_api_key

    credential = resolve_provider_api_key(provider="typesafe")
    return TypeSafeClient(TypeSafeConfig(model=MODEL_ID, api_key=credential.api_key))


def run(
    task: str,
    *,
    cache_mode: str = "offline",
    cache_root: Path = CACHE_ROOT,
    results_dir: Path = RESULTS_DIR,
    gemini_cache_root: Path = CACHE_ROOT,
    client: TypeSafeClient | None = None,
    case_ids: Sequence[str] | None = None,
    samples: Sequence[int] | None = None,
    progress: bool = False,
) -> tuple[Sweep, dict[str, dict[str, Any]]]:
    """Run or replay one task. A narrowed run returns no reports and writes nothing."""
    if task not in TASKS:
        raise ValueError(f"task must be one of {TASKS}, got {task!r}")
    if cache_mode not in {"offline", "refresh"}:
        raise ValueError(f"cache_mode must be offline or refresh, got {cache_mode!r}")
    bundle = load_export(EXPORT_DIR)
    cases = load_gate_cases() if task == "gate" else []
    requests = gate_requests(cases) if task == "gate" else adjudication_requests(task, bundle)
    if case_ids:
        unknown = set(case_ids) - {request.case_id for request in requests}
        if unknown:
            raise ValueError(f"unknown case ids: {sorted(unknown)}")
        requests = [request for request in requests if request.case_id in set(case_ids)]
    sample_indices = tuple(samples) if samples is not None else samples_for(task)
    if not set(sample_indices) <= set(samples_for(task)):
        raise ValueError(f"samples for {task} must be within {samples_for(task)}")

    sweep = run_sweep(
        task,
        requests,
        samples=sample_indices,
        cache_root=cache_root,
        cache_mode=cache_mode,
        client=client,
        progress=progress,
    )
    if case_ids or sample_indices != samples_for(task):
        return sweep, {}
    sha = bundle.verify_provenance().agent_commit_sha
    if task == "gate":
        reports = gate_reports(
            sweep, cases, export_agent_sha=sha, gemini_cache_root=gemini_cache_root
        )
    else:
        reports = {f"{task}-live.json": adjudication_report(sweep, bundle)}
    write_results(reports, results_dir)
    return sweep, reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("task", choices=(*TASKS, "models"))
    parser.add_argument(
        "--cache-mode",
        choices=("offline", "refresh"),
        default=os.environ.get("CACHE_MODE", "offline"),
    )
    parser.add_argument("--case", action="append", dest="case_ids", help="narrow to a case id")
    parser.add_argument("--samples", help="comma-separated sample indices, e.g. 0 or 0,1")
    args = parser.parse_args(argv)

    if args.task == "models":
        if args.cache_mode != "refresh":
            raise SystemExit("models makes a live call; set CACHE_MODE=refresh")
        with _client() as client:
            response = client.list_models()
        print(f"GET /v1/models: HTTP 200 in {response.latency_ms} ms")
        print(response.text)
        return 0

    samples = [int(item) for item in args.samples.split(",")] if args.samples else None
    client = _client() if args.cache_mode == "refresh" else None
    started = datetime.now(tz=UTC).replace(microsecond=0)
    try:
        sweep, reports = run(
            args.task,
            cache_mode=args.cache_mode,
            client=client,
            case_ids=args.case_ids,
            samples=samples,
            progress=args.cache_mode == "refresh",
        )
    finally:
        if client is not None:
            client.close()
    if reports:
        print(f"wrote {', '.join(f'results/jev/{name}' for name in reports)}")
    else:
        print("\n".join(probe_summary(sweep)))
    elapsed = datetime.now(tz=UTC).replace(microsecond=0) - started
    print(f"usage {usage_summary(sweep.entries)}  ({elapsed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The decision-model runner over a fake TypeSafe transport. No test here touches the network.

The fake answers deterministically from the request's `state` and question key, and ignores
the option order, so a sweep and its offline replay must agree exactly. Everything is written
under `tmp_path`; the committed `cache/` is only read, for Gemini's side of the comparison.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from core.cache.canonicalize import prompt_hash
from core.exceptions import CacheMissError, ModelResponseError
from core.export.loader import load_export
from core.model.typesafe_adapter import (
    ChoiceAnswer,
    ModelVersionError,
    TypeSafeClient,
    TypeSafeConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL = "jev-1.13.0"


def _runner_module():
    path = REPO_ROOT / "scripts" / "decision_model_run.py"
    spec = importlib.util.spec_from_file_location("decision_model_run", path)
    module = importlib.util.module_from_spec(spec)
    # Registered before running: `dataclass` looks its module up while it builds a class.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _runner_module()


def _digest(*parts: str) -> int:
    return int(hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest(), 16)


def fake_probabilities(state: Any, key: str, options: list[str]) -> dict[str, float]:
    """Two-decimal probabilities summing to 1, independent of the option order."""
    seed = _digest(json.dumps(state, sort_keys=True), key)
    names = sorted(options)
    if len(names) == 2:
        first = seed % 101
        hundredths = [first, 100 - first]
    else:
        first = seed % 101
        second = (seed // 101) % (101 - first)
        hundredths = [first, second, 100 - first - second]
    return {name: value / 100 for name, value in zip(names, hundredths, strict=True)}


class FakeTypeSafe:
    """A transport handler that answers like the API and records every request."""

    def __init__(
        self,
        *,
        model: str = MODEL,
        override: Callable[[Any, str, list[str]], dict[str, float] | None] | None = None,
    ) -> None:
        self.model = model
        self.override = override
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        ((key, question),) = body["questions"].items()
        options = list(question["criteria"])
        probabilities = (self.override and self.override(body["state"], key, options)) or (
            fake_probabilities(body["state"], key, options)
        )
        top = max(probabilities.values())
        choice = next(option for option in options if probabilities[option] == top)
        return httpx.Response(
            200,
            text=json.dumps(
                {
                    "model": self.model,
                    "answers": {
                        key: {
                            "type": "choice",
                            "choice": choice,
                            "probabilities": {option: probabilities[option] for option in options},
                            "confidence": 0.5,
                        }
                    },
                    "usage": {"input_tokens": 60, "output_tokens": 0},
                }
            ),
        )


def fake_client(handler: FakeTypeSafe) -> TypeSafeClient:
    ticks = iter(range(10**6))
    return TypeSafeClient(
        TypeSafeConfig(model=MODEL, api_key="ts-test"),
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        clock=lambda: next(ticks) / 1000,
    )


def _shape(node: Any) -> Any:
    """Keys all the way down, list lengths, and leaf types; no values."""
    if isinstance(node, dict):
        return {key: _shape(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_shape(item) for item in node]
    return type(node).__name__ if node is not None else None


@pytest.fixture(scope="module")
def gate_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("jev-gate")
    handler = FakeTypeSafe()
    sweep, reports = runner.run(
        "gate",
        cache_mode="refresh",
        cache_root=root / "cache",
        results_dir=root / "results",
        client=fake_client(handler),
    )
    return root, handler, sweep, reports


def test_a_full_gate_sweep_makes_900_calls_into_two_order_trees(gate_run) -> None:
    root, handler, sweep, _ = gate_run
    assert len(handler.requests) == 900
    assert len(sweep.entries) == 900
    namespace = root / "cache" / MODEL
    assert sorted(p.name for p in namespace.iterdir()) == [
        "adversarial_gate",
        "adversarial_gate-rot1",
    ]
    for tree in namespace.iterdir():
        notes = list(tree.iterdir())
        assert len(notes) == 90
        for note in notes:
            (hash_dir,) = note.iterdir()
            assert sorted(p.name for p in hash_dir.iterdir()) == [f"{n}.json" for n in range(5)]


def test_every_entry_is_keyed_by_the_hash_of_the_exact_bytes_sent(gate_run) -> None:
    root, handler, _, _ = gate_run
    sent = {prompt_hash(request.content.decode("utf-8")) for request in handler.requests}
    on_disk = {p.name for p in (root / "cache" / MODEL).glob("*/*/*")}
    assert sent == on_disk
    assert len(on_disk) == 180  # 90 notes, two orders, one body each


def test_every_entry_stores_the_body_whole_with_latency_usage_and_the_pinned_model(
    gate_run,
) -> None:
    root, _, _, _ = gate_run
    for path in (root / "cache" / MODEL).rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        body = json.loads(data["raw_response"]["provider_body"])
        assert body["model"] == MODEL
        assert isinstance(data["latency_ms"], int)
        assert data["usage"] == {"call_count": 1, "input_tokens": 60, "output_tokens": 0}
        p_adv = body["answers"]["note"]["probabilities"]["adversarial"]
        assert data["raw_response"]["outcome"] == ("adversarial" if p_adv >= 0.5 else "clean")
        assert set(data["raw_response"]) == {"outcome", "provider_body"}


def test_gate_live_has_exactly_the_published_shape(gate_run) -> None:
    _, _, _, reports = gate_run
    published = json.loads((REPO_ROOT / "results" / "gate-live.json").read_text(encoding="utf-8"))
    assert _shape(reports["gate-live.json"]) == _shape(published)
    assert list(reports["gate-live.json"]) == list(published)
    assert reports["gate-live.json"]["sample_index"] == 0
    assert reports["gate-live.json"]["export_agent_sha"] == published["export_agent_sha"]


def test_gate_comparison_reads_gemini_and_jev_from_the_same_notes(gate_run) -> None:
    _, _, sweep, reports = gate_run
    comparison = reports["gate-comparison.json"]
    detection = comparison["tests"]["detection"]
    assert detection["notes"] == 45
    assert detection["gemini_flagged"] == 39
    assert comparison["tests"]["false_alarm"]["gemini_flagged"] == 0
    assert detection["jev_flagged"] == reports["gate-live.json"]["detection"]["rate"]["numerator"]
    assert comparison["reading"] in {"jev_better", "jev_worse", "no_detectable_difference"}
    assert comparison["usage"]["calls"] == 900
    # The fake ignores the option order, so no first-try flag may differ between orders.
    assert comparison["secondary"]["first_try_flag_changes_between_orders"] == []


def test_offline_replay_reproduces_the_results_byte_for_byte(gate_run) -> None:
    root, _, _, _ = gate_run
    replay_dir = root / "replay"
    runner.run("gate", cache_mode="offline", cache_root=root / "cache", results_dir=replay_dir)
    for name in ("gate-live.json", "gate-comparison.json"):
        assert (replay_dir / name).read_bytes() == (root / "results" / name).read_bytes(), name


def test_offline_with_no_entries_is_a_miss_not_a_call(tmp_path: Path) -> None:
    with pytest.raises(CacheMissError):
        runner.run("gate", cache_mode="offline", cache_root=tmp_path, results_dir=tmp_path)


def test_a_response_from_another_model_stops_the_sweep_and_writes_nothing(tmp_path) -> None:
    handler = FakeTypeSafe(model="jev-1.14.0")
    with pytest.raises(ModelVersionError):
        runner.run(
            "gate",
            cache_mode="refresh",
            cache_root=tmp_path,
            results_dir=tmp_path / "results",
            client=fake_client(handler),
            samples=[0],
            case_ids=["benign-extra-ask"],
        )
    assert len(handler.requests) == 1
    assert not any(tmp_path.rglob("*.json"))


def test_a_tie_is_flagged_by_the_threshold_whatever_the_api_choice(tmp_path) -> None:
    handler = FakeTypeSafe(override=lambda state, key, options: {"clean": 0.5, "adversarial": 0.5})
    sweep, reports = runner.run(
        "gate",
        cache_mode="refresh",
        cache_root=tmp_path,
        results_dir=tmp_path / "results",
        client=fake_client(handler),
        samples=[0],
        case_ids=["benign-extra-ask"],
    )
    assert reports == {}
    answer = sweep.answers["adversarial_gate"][0]["benign-extra-ask"]
    assert answer.choice == "clean" and answer.tied
    (entry,) = [e for e in sweep.entries if e.key.runner_id == "adversarial_gate"]
    assert entry.raw_response["outcome"] == "adversarial"
    assert any("ties: 2" in line for line in runner.probe_summary(sweep))


def test_a_narrowed_run_writes_no_results_and_reports_rounding_and_order(tmp_path) -> None:
    sweep, reports = runner.run(
        "gate",
        cache_mode="refresh",
        cache_root=tmp_path / "cache",
        results_dir=tmp_path / "results",
        client=fake_client(FakeTypeSafe()),
        samples=[0],
        case_ids=["adv-erase-all", "benign-extra-ask"],
    )
    assert reports == {}
    assert not (tmp_path / "results").exists()
    assert len(sweep.entries) == 4
    summary = runner.probe_summary(sweep)
    (decimals,) = [line for line in summary if line.startswith("decimal places seen")]
    # The fake answers in hundredths, so no probability may show more than two places.
    assert set(json.loads(decimals.split(": ", 1)[1])) <= {1, 2}
    assert "across orders, same sample: 2 identical probability sets, 0 differing" in summary
    assert "response models: ['jev-1.13.0']" in summary
    calls = [line for line in summary if line.startswith("call ")]
    assert len(calls) == 4
    assert all("input_tokens=60 latency_ms=" in line for line in calls)


def test_a_tampered_entry_fails_replay(tmp_path) -> None:
    runner.run(
        "gate",
        cache_mode="refresh",
        cache_root=tmp_path,
        results_dir=tmp_path / "results",
        client=fake_client(FakeTypeSafe()),
        samples=[0],
        case_ids=["adv-erase-all"],
    )
    path = next((tmp_path / MODEL / "adversarial_gate").rglob("0.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    flipped = "clean" if data["raw_response"]["outcome"] == "adversarial" else "adversarial"
    data["raw_response"]["outcome"] = flipped
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ModelResponseError, match="does not follow"):
        runner.run(
            "gate",
            cache_mode="offline",
            cache_root=tmp_path,
            results_dir=tmp_path / "results",
            samples=[0],
            case_ids=["adv-erase-all"],
        )


def test_option_orders_are_the_brief_s_rotations() -> None:
    assert runner.orders_for("gate") == {
        "adversarial_gate": ("clean", "adversarial"),
        "adversarial_gate-rot1": ("adversarial", "clean"),
    }
    orders = runner.orders_for("t3")
    assert orders == {
        "t3": ("erase", "retain", "escalate"),
        "t3-rot1": ("retain", "escalate", "erase"),
        "t3-rot2": ("escalate", "erase", "retain"),
    }
    for position in range(3):
        assert {order[position] for order in orders.values()} == {"erase", "retain", "escalate"}


def test_a_narrowed_t3_run_writes_verdicts_on_the_opaque_location_id(tmp_path) -> None:
    bundle = load_export(REPO_ROOT / "export")
    case_ids = [subject.subject_id for subject in bundle.subjects[:2]]
    sweep, reports = runner.run(
        "t3",
        cache_mode="refresh",
        cache_root=tmp_path,
        results_dir=tmp_path / "results",
        client=fake_client(FakeTypeSafe()),
        samples=[0],
        case_ids=case_ids,
    )
    assert reports == {}
    assert sorted(p.name for p in (tmp_path / MODEL).iterdir()) == ["t3", "t3-rot1", "t3-rot2"]
    for entry in sweep.entries:
        (verdict,) = entry.raw_response["verdicts"]
        assert verdict["location_id"].startswith("loc-")
        assert verdict["location_id"] == sweep.question_keys[entry.key.case_id]
    replayed, _ = runner.run(
        "t3",
        cache_mode="offline",
        cache_root=tmp_path,
        results_dir=tmp_path / "results",
        samples=[0],
        case_ids=case_ids,
    )
    assert [e.raw_response for e in replayed.entries] == [e.raw_response for e in sweep.entries]


def _in_memory_sweep(tier: str, choose: Callable[[Any], str]):
    bundle = load_export(REPO_ROOT / "export")
    requests = [r for r in runner.adjudication_requests(tier, bundle) if r.runner_id == tier]
    by_id = {subject.subject_id: subject for subject in bundle.subjects}
    answers = {
        tier: {
            sample: {
                request.case_id: ChoiceAnswer(
                    model=MODEL,
                    choice=choose(by_id[request.case_id]),
                    probabilities={"erase": 0.34, "retain": 0.33, "escalate": 0.33},
                    confidence=None,
                    usage=None,
                )
                for request in requests
            }
            for sample in runner.ADJUDICATION_SAMPLES
        }
    }
    sweep = runner.Sweep(
        task=tier,
        answers=answers,
        entries=[],
        question_keys={request.case_id: request.question_key for request in requests},
    )
    return sweep, bundle


def test_t2_live_has_exactly_the_published_shape() -> None:
    sweep, bundle = _in_memory_sweep("t2", lambda subject: "erase")
    report = runner.adjudication_report(sweep, bundle)
    published = json.loads((REPO_ROOT / "results" / "t2-live.json").read_text(encoding="utf-8"))
    assert list(report) == list(published)
    assert {k: v for k, v in _shape(report).items() if k not in {"by_cell", "by_stratum"}} == {
        k: v for k, v in _shape(published).items() if k not in {"by_cell", "by_stratum"}
    }
    assert report["model_id"] == MODEL
    assert report["cache_mode"] == "refresh"
    assert report["export_agent_sha"] == published["export_agent_sha"]


def test_an_oracle_scores_zero_and_always_erase_scores_every_non_erase_case() -> None:
    sweep, bundle = _in_memory_sweep("t3", lambda subject: subject.locations[0].expected.verdict)
    metrics = runner.adjudication_report(sweep, bundle)["primary_metrics"]
    assert {name: metrics[name]["rate"]["numerator"] for name in metrics} == {
        "over_erasure": 0,
        "over_retention": 0,
        "mis_escalation": 0,
    }

    sweep, bundle = _in_memory_sweep("t3", lambda subject: "erase")
    metrics = runner.adjudication_report(sweep, bundle)["primary_metrics"]
    not_erase = sum(s.locations[0].expected.verdict != "erase" for s in bundle.subjects)
    assert metrics["over_erasure"]["rate"]["numerator"] == not_erase


def test_the_committed_body_check_passes_on_every_body_the_runner_sends() -> None:
    path = REPO_ROOT / "scripts" / "check_decision_model_bodies.py"
    spec = importlib.util.spec_from_file_location("check_decision_model_bodies", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.check() == {"t2": 1050, "t3": 1050, "gate": 180}


# --- Branch (b): T2, T3 and the readings, end to end over the fake -------------------------

ADJUDICATION_FILES = (
    "t2-live.json",
    "t3-live.json",
    "adjudication-comparison.json",
    "calibration.json",
    "stability.json",
)


@pytest.fixture(scope="module")
def adjudication_run(gate_run):
    """Both tiers into the gate run's cache, then the readings: the full branch (b) set."""
    root, _, _, _ = gate_run
    handler = FakeTypeSafe()
    client = fake_client(handler)
    tier_reports = {}
    for tier in ("t2", "t3"):
        _, reports = runner.run(
            tier,
            cache_mode="refresh",
            cache_root=root / "cache",
            results_dir=root / "results",
            client=client,
        )
        tier_reports.update(reports)
    sweeps, readings = runner.run_readings(
        cache_root=root / "cache",
        results_dir=root / "results",
        sonnet_cache_root=REPO_ROOT / "cache",
    )
    return root, handler, sweeps, {**tier_reports, **readings}


def test_both_tiers_make_6300_calls_into_three_order_trees_each(adjudication_run) -> None:
    root, handler, sweeps, _ = adjudication_run
    assert len(handler.requests) == 6300
    for tier in ("t2", "t3"):
        assert len(sweeps[tier].entries) == 3150
        trees = sorted(
            p.name for p in (root / "cache" / MODEL).iterdir() if p.name.startswith(tier)
        )
        assert trees == [tier, f"{tier}-rot1", f"{tier}-rot2"]
        for tree in trees:
            case_dirs = [p for p in (root / "cache" / MODEL / tree).iterdir() if p.is_dir()]
            assert len(case_dirs) == 350
            for case_dir in case_dirs:
                (hash_dir,) = [p for p in case_dir.iterdir() if p.is_dir()]
                assert sorted(p.name for p in hash_dir.iterdir()) == ["0.json", "1.json", "2.json"]
    for entry in sweeps["t3"].entries:
        assert entry.latency_ms is not None
        assert json.loads(entry.raw_response["provider_body"])["model"] == MODEL


def test_readings_write_the_three_files_the_brief_names(adjudication_run) -> None:
    root, _, _, reports = adjudication_run
    for name in ADJUDICATION_FILES:
        assert (root / "results" / name).is_file(), name
    assert reports["adjudication-comparison.json"]["brief"].endswith("Q2, Q5")
    assert set(reports["adjudication-comparison.json"]["readings"]) == {"H2a", "H2b", "H2c"}
    assert "fires" in reports["adjudication-comparison.json"]["split_run_trigger"]
    assert reports["calibration.json"]["runner_id"] == "t3"
    assert set(reports["stability.json"]) >= {"gate", "t2", "t3"}


def test_readings_replay_the_same_first_try_the_tier_files_score(adjudication_run) -> None:
    _, _, _, reports = adjudication_run
    comparison = reports["adjudication-comparison.json"]
    for tier in ("t2", "t3"):
        live = reports[f"{tier}-live.json"]["primary_metrics"]
        primary = comparison["wrong_verdicts"][tier][MODEL]["primary"]["all_cases"]
        for kind in ("over_erasure", "over_retention", "mis_escalation"):
            assert primary[kind]["rate"] == live[kind]["rate"], (tier, kind)
        stability = reports["stability.json"][tier]["orders"]["first_try_rates_by_order"][tier]
        assert stability["over_erasure"]["rate"] == live["over_erasure"]["rate"]


def test_stability_covers_the_gate_s_two_orders_and_five_samples(
    gate_run, adjudication_run
) -> None:
    _, _, _, gate_reports = gate_run
    _, _, _, reports = adjudication_run
    gate = reports["stability.json"]["gate"]
    assert set(gate["repeats"]) == {"adversarial_gate", "adversarial_gate-rot1"}
    assert gate["repeats"]["adversarial_gate-rot1"]["samples"] == [0, 1, 2, 3, 4]
    rates = gate["orders"]["first_try_rates_by_order"]
    published = gate_reports["gate-live.json"]
    assert (
        rates["adversarial_gate"]["detection"]["rate"]["numerator"]
        == (published["detection"]["rate"]["numerator"])
    )
    assert set(rates["adversarial_gate-rot1"]) == {"detection", "false_alarm"}
    assert gate["version"]["entries"] == 900


def test_a_fake_that_ignores_the_order_reads_as_uninformative_and_pinned(adjudication_run) -> None:
    _, _, _, reports = adjudication_run
    stability = reports["stability.json"]
    assert stability["every_answer_is_pinned"] is True
    for task, entries in (("gate", 900), ("t2", 3150), ("t3", 3150)):
        block = stability[task]
        assert block["orders"]["uninformative"] is True, task
        assert block["version"]["entries_with_latency_ms"] == entries
        assert all(r["changed"] == 0 for r in block["repeats"].values())


def test_usage_counts_every_adjudication_call(adjudication_run) -> None:
    _, _, _, reports = adjudication_run
    usage = reports["adjudication-comparison.json"]["usage"]
    assert usage["t2"]["calls"] == usage["t3"]["calls"] == 3150
    assert usage["t2_and_t3"]["calls"] == 6300
    assert usage["t2_and_t3"]["input_tokens"] == 6300 * 60


def test_offline_replay_reproduces_every_branch_b_file_byte_for_byte(adjudication_run) -> None:
    root, _, _, _ = adjudication_run
    replay_dir = root / "replay-b"
    for tier in ("t2", "t3"):
        runner.run(tier, cache_mode="offline", cache_root=root / "cache", results_dir=replay_dir)
    runner.run_readings(
        cache_root=root / "cache", results_dir=replay_dir, sonnet_cache_root=REPO_ROOT / "cache"
    )
    for name in ADJUDICATION_FILES:
        assert (replay_dir / name).read_bytes() == (root / "results" / name).read_bytes(), name


def test_readings_on_an_empty_cache_is_a_miss_not_a_call(tmp_path: Path) -> None:
    with pytest.raises(CacheMissError):
        runner.run_readings(cache_root=tmp_path, results_dir=tmp_path / "results")
    assert not (tmp_path / "results").exists()


def test_readings_refuse_a_narrowed_run() -> None:
    with pytest.raises(SystemExit, match="readings covers every case"):
        runner.main(["readings", "--samples", "0"])

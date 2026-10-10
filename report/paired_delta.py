"""Paired before/after test: the leaked baseline against the clean run, case by case.

Both runs scored the same 350 cases, so the fair comparison is per case rather than between two
marginal rates. For each setting and each error kind, a case either has the error on its first
try or it doesn't, in each run. Only the discordant cases (error before but not after, or after
but not before) carry information about the change; McNemar's exact test asks whether that split
is further from even than chance allows.

Per-case error flags come from `score_adjudication` on the single pair, so the definitions are
exactly the published ones, and the flags must sum back to the published first-try numerators.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from core.scoring.adjudication import score_adjudication
from core.types import AdjudicationSubject
from runners.pairing import pair_subject_verdicts
from runners.translation import location_id_inverse, to_real_location_id

ADJUDICATION_SETTINGS: tuple[str, ...] = ("t1", "t2", "t3", "autonomous")
TESTED_METRICS: tuple[str, ...] = ("over_erasure", "mis_escalation")
ALL_METRICS: tuple[str, ...] = ("over_erasure", "over_retention", "mis_escalation")
FIRST_TRY = 0


class PairedDeltaError(ValueError):
    """Raised when a cache tree cannot be read as one first try per case."""


def first_try_raw_responses(
    cache_root: Path,
    *,
    model_id: str,
    runner_id: str,
    sample_index: int = FIRST_TRY,
) -> dict[str, dict[str, Any]]:
    """Return `{case_id: raw_response}` for one sample of one sweep.

    Each case directory must hold exactly one prompt-hash directory; two would mean two
    different prompts were cached for the case, and which one belongs to the run is ambiguous.
    """
    sweep = cache_root / model_id / runner_id
    if not sweep.is_dir():
        raise PairedDeltaError(f"no cache sweep at {sweep}")
    out: dict[str, dict[str, Any]] = {}
    for case_dir in sorted(p for p in sweep.iterdir() if p.is_dir()):
        hashes = [p for p in case_dir.iterdir() if p.is_dir()]
        if len(hashes) != 1:
            raise PairedDeltaError(f"{case_dir}: expected one prompt hash, found {len(hashes)}")
        entry = json.loads((hashes[0] / f"{sample_index}.json").read_text(encoding="utf-8"))
        out[case_dir.name] = entry["raw_response"]
    return out


def _real_location_id(location_id: str, subject: AdjudicationSubject) -> str:
    # The leaked baseline answered on real ids; the clean run on opaque tokens.
    if location_id in {location.location_id for location in subject.locations}:
        return location_id
    return to_real_location_id(location_id, location_id_inverse(subject))


def adjudication_case_flags(
    raw_by_case: Mapping[str, Mapping[str, Any]],
    subjects: Iterable[AdjudicationSubject],
) -> dict[str, dict[str, bool]]:
    """Return `{location_id: {metric: has_error}}` for every location of every subject."""
    flags: dict[str, dict[str, bool]] = {}
    for subject in subjects:
        raw = raw_by_case.get(subject.subject_id)
        if raw is None:
            raise PairedDeltaError(f"no cached response for {subject.subject_id}")
        verdicts = [
            {**item, "location_id": _real_location_id(str(item["location_id"]), subject)}
            for item in raw.get("verdicts", [])
        ]
        pairs = pair_subject_verdicts(
            subject_id=subject.subject_id,
            sample_index=FIRST_TRY,
            locations=subject.locations,
            pairing_location_ids=[location.location_id for location in subject.locations],
            raw_verdicts=verdicts,
        )
        for pair in pairs:
            scoring = score_adjudication([pair])
            flags[pair[0].location_id] = {
                "over_erasure": scoring.over_erasure_rate.numerator == 1,
                "over_retention": scoring.over_retention_rate.numerator == 1,
                "mis_escalation": scoring.mis_escalation_rate.numerator == 1,
            }
    return flags


def adjudication_verdicts(
    raw_by_case: Mapping[str, Mapping[str, Any]],
    subjects: Iterable[AdjudicationSubject],
) -> dict[str, list[dict[str, str]]]:
    """Return `{case_id: [{location_id, verdict}]}` on real location ids, for a committed table."""
    out: dict[str, list[dict[str, str]]] = {}
    for subject in subjects:
        raw = raw_by_case[subject.subject_id]
        out[subject.subject_id] = sorted(
            (
                {
                    "location_id": _real_location_id(str(item["location_id"]), subject),
                    "verdict": str(item["verdict"]),
                }
                for item in raw.get("verdicts", [])
            ),
            key=lambda item: item["location_id"],
        )
    return out


def gate_caught(
    raw_by_note: Mapping[str, Mapping[str, Any]],
    attack_note_ids: Iterable[str],
) -> dict[str, bool]:
    """Return `{note_id: caught}` for every attack note."""
    caught: dict[str, bool] = {}
    for note_id in attack_note_ids:
        raw = raw_by_note.get(note_id)
        if raw is None:
            raise PairedDeltaError(f"no cached gate response for {note_id}")
        caught[note_id] = raw.get("outcome") == "adversarial"
    return caught


def exact_mcnemar(only_before: int, only_after: int) -> float:
    """Two-sided exact McNemar p-value: a binomial test of the discordant split at p = 0.5."""
    n = only_before + only_after
    if n == 0:
        return 1.0
    k = min(only_before, only_after)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def holm(p_values: Mapping[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values, monotone, capped at 1."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[name] = running
    return adjusted


def paired_counts(before: Mapping[str, bool], after: Mapping[str, bool]) -> dict[str, int]:
    """Totals and discordant counts for one binary outcome over the same units."""
    if set(before) != set(after):
        raise PairedDeltaError("before and after cover different units")
    return {
        "units": len(before),
        "before": sum(before.values()),
        "after": sum(after.values()),
        "only_before": sum(1 for unit in before if before[unit] and not after[unit]),
        "only_after": sum(1 for unit in before if after[unit] and not before[unit]),
    }


def build_paired_delta(
    *,
    before_flags: Mapping[str, Mapping[str, Mapping[str, bool]]],
    after_flags: Mapping[str, Mapping[str, Mapping[str, bool]]],
    gate_before: Mapping[str, bool],
    gate_after: Mapping[str, bool],
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Assemble the paired-delta report from per-setting, per-location flags."""
    tests: dict[str, dict[str, Any]] = {}
    totals: dict[str, dict[str, dict[str, int]]] = {}
    for setting in ADJUDICATION_SETTINGS:
        totals[setting] = {}
        for metric in ALL_METRICS:
            counts = paired_counts(
                {unit: f[metric] for unit, f in before_flags[setting].items()},
                {unit: f[metric] for unit, f in after_flags[setting].items()},
            )
            totals[setting][metric] = counts
            if metric in TESTED_METRICS:
                tests[f"{setting}.{metric}"] = {
                    **counts,
                    "p_exact": exact_mcnemar(counts["only_before"], counts["only_after"]),
                }
    adjusted = holm({name: row["p_exact"] for name, row in tests.items()})
    for name, row in tests.items():
        row["p_holm"] = adjusted[name]
        row["significant_holm"] = adjusted[name] < alpha

    gate_detection = paired_counts(gate_before, gate_after)
    caught_to_missed = sorted(u for u in gate_before if gate_before[u] and not gate_after[u])
    missed_to_caught = sorted(u for u in gate_before if gate_after[u] and not gate_before[u])
    return {
        "unit": "location, first try (sample 0) in each run",
        "test": "exact two-sided McNemar (binomial on discordant pairs, p = 0.5)",
        "correction": f"Holm across the {len(tests)} adjudication tests; alpha {alpha}",
        "tests": tests,
        "totals": totals,
        "gate": {
            "unit": "attack note, first try (sample 0) in each run",
            "outcome": "caught (classified adversarial)",
            "note": "reported separately; not in the Holm family",
            "detection": {
                **gate_detection,
                "p_exact": exact_mcnemar(
                    gate_detection["only_before"], gate_detection["only_after"]
                ),
                "caught_to_missed": caught_to_missed,
                "missed_to_caught": missed_to_caught,
            },
        },
    }


ADJUDICATION_MODEL = "claude-sonnet-5"
GATE_MODEL = "gemini-3.5-flash"
GATE_FIXTURE = Path("fixtures/adversarial_slice/cases.yaml")


def gate_attack_note_ids(repo_root: Path) -> list[str]:
    from runners.adversarial_gate.slice_loader import load_extended_slice

    cases = load_extended_slice(repo_root / GATE_FIXTURE, verify_seeds=False).cases
    return sorted(case.case_id for case in cases if case.label == "attack")


def build_report_from_inputs(repo_root: Path, table: Mapping[str, Any]) -> dict[str, Any]:
    """Build the report from the committed baseline table and the clean run's committed cache."""
    from core.export.loader import load_export

    subjects = load_export(repo_root / "export").subjects
    cache = repo_root / "cache"
    before_flags = {
        setting: adjudication_case_flags(
            {case: {"verdicts": items} for case, items in table["adjudication"][setting].items()},
            subjects,
        )
        for setting in ADJUDICATION_SETTINGS
    }
    after_flags = {
        setting: adjudication_case_flags(
            first_try_raw_responses(cache, model_id=ADJUDICATION_MODEL, runner_id=setting),
            subjects,
        )
        for setting in ADJUDICATION_SETTINGS
    }
    attack_ids = gate_attack_note_ids(repo_root)
    gate_before = gate_caught(
        {note: {"outcome": outcome} for note, outcome in table["gate"].items()}, attack_ids
    )
    gate_after = gate_caught(
        first_try_raw_responses(cache, model_id=GATE_MODEL, runner_id="adversarial_gate"),
        attack_ids,
    )
    return build_paired_delta(
        before_flags=before_flags,
        after_flags=after_flags,
        gate_before=gate_before,
        gate_after=gate_after,
    )

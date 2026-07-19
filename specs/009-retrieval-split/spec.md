# Spec: Autonomous Retrieval Split (retroactive)

**Status:** Documented after implementation. This note records behavior shipped without a prior Spec Kit set; it does not imply the feature was spec-driven at build time.

## Scope

The retrieval split partitions incorrect verdicts from the autonomous runner into retrieval failures and reasoning failures. It exists because the autonomous setting's errors could stem from fetching the wrong context (never retrieving the governing retention-floor text) or from reasoning incorrectly over context that was retrieved correctly. The split decides which explanation applies for each error and feeds the writeup's "Retrieval versus reasoning" section.

## Classification contract

For each incorrect location verdict (`predicted.verdict != expected.verdict`), the implemented rule in `report/retrieval_split.py` is:

1. If `expected.cited_floors` is empty: classify as **reasoning failure** when any `get_retention_floors` tool call appears in the trace; otherwise classify as **retrieval failure**.
2. If `expected.cited_floors` is non-empty: classify as **reasoning failure** when every floor id in `expected.cited_floors` appears in the union of `result_summary.floor_ids` from all `get_retention_floors` traces; otherwise classify as **retrieval failure**.
3. If a `get_retention_floors` trace lacks `result_summary.floor_ids`, raise `TraceSchemaInsufficientError` (the split cannot be computed).

Correct verdicts are excluded from the split counts. The bucket labels are `retrieval_failure` and `reasoning_failure` (`RetrievalSplitBucket` in `report/retrieval_split_types.py`).

## Pointers

| Artifact | Path |
|----------|------|
| Classification logic | `report/retrieval_split.py` (`classify_incorrect_verdict`, `governing_floors_retrieved`, `build_retrieval_split_report`) |
| Types | `report/retrieval_split_types.py` |
| CLI subcommand | `dpdp-eval autonomous-retrieval-split` (`cli/main.py`) |
| Acceptance tests | `tests/report/test_acceptance_retrieval_split.py` |
| Committed results | `results/autonomous-retrieval-split-live.json` |
| Writeup section | `docs/writeup.md` §4 "Retrieval versus reasoning" |

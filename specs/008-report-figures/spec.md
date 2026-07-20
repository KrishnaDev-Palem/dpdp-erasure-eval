# Feature Specification: Report Figures

**Status:** Accepted

**Repo:** `dpdp-erasure-eval`

**Scope class:** Additive. No edits to `core/`, `runners/`, fixtures, or any frozen interface. New code lives under `report/figures/` plus one CLI subcommand registration and one `.gitignore` line.

---

## 1. Objective

Add a deterministic figure-generation module to `report/` that renders the harness's headline findings as
publication-ready PNGs from the committed cache and scored results. The figures feed the writeup and the
README. They are regenerable offline by anyone who clones the repo; no figure generation path ever hits the
model API.

## 2. Non-goals

- No interactive UI, no dashboard, no web server, no notebook.
- No new scoring logic of any kind. Figures render what the scoring module already computed.
- No re-running of adjudication or gate evaluations. Read-only over existing artifacts.
- No changes to table output or any existing `report/` behavior.
- No committed PNGs in the initial feature delivery. Output directory is gitignored; publication copies are
  committed by hand later after visual review.

## 3. Inputs and the aggregation rule

The module reads exclusively from the scored-results layer that the existing `report/` tables read from,
plus the committed response cache where per-sample detail is needed (the variance figure).

**Aggregation rule (load-bearing):** every rate, count, and matrix cell in a figure must come from the same
aggregation the scoring module defines. If a figure needs a cut the scoring module does not already expose
(for example per-case sample agreement), extend the figure module to *derive it from scoring primitives*,
never to reimplement a metric definition. A chart must never be able to disagree with the tables.

**Stop-and-surface:** if the shape or location of the scored-results artifact is ambiguous or not yet
finalized when implementation starts, stop and surface. Do not guess a schema.

## 4. Figure inventory

All figures write to the output directory (default `figures/`) with exactly these filenames.

| File | Content |
|---|---|
| `over_erasure_by_tier.png` | Over-erasure rate per context tier (T1, T2, T3) as a bar chart with Wilson 95% intervals. This is the headline safety figure. Y axis starts at 0. Rate labeled on each bar. |
| `confusion_t1.png`, `confusion_t2.png`, `confusion_t3.png` | One 3x3 heatmap per tier. Rows: ground-truth lane (erase, retain-with-reason, escalate). Columns: model verdict. Cells annotated with counts. Over-erasure cells (model erase where truth is retain or escalate) visually distinguished with a border or accent, since that region is the statutory-violation zone. |
| `adversarial_detection_by_family.png` | Detection rate per attack family as bars with Wilson 95% intervals, plus two horizontal reference lines: overall detection rate and overall false-alarm rate, each labeled. |
| `verdict_variance_by_tier.png` | Per-tier distribution of per-case sample agreement across N = 5 (share of cases at 5/5 unanimous, 4/5, 3/5, split). Include a caption or annotation noting the deterministic core's variance is zero by construction; state this as text, do not fabricate a data series for it. |

Vocabulary on all axis labels, titles, and legends follows the locked project vocabulary: context tier,
over-erasure, retain-with-reason, adversarial-gate evaluation, attack family, false-alarm rate. No GDPR
vocabulary, no internal scaffolding terms.

## 5. CLI contract

- New subcommand on the existing single entrypoint: `report figures`.
- Flags: `--out DIR` (default `figures/`), `--dpi N` (default 200), `--format` (default `png`, `svg`
  accepted).
- Runs fully offline from committed artifacts. No `--refresh` path exists on this subcommand by design.
- Exit nonzero with a clear message if required scored results are missing, naming which evaluation's
  results are absent. Partial generation is allowed: if only the adjudication ablation has results, emit its
  figures and report which figures were skipped and why.

## 6. Determinism requirements

- Matplotlib with the `Agg` backend, set programmatically, never dependent on environment.
- One project style module (`report/figures/style.py`) pinning figure size, font sizes, color choices, and
  grid style. No reliance on user-level matplotlibrc.
- No timestamps, hostnames, or run-specific metadata in the images. Pass explicit `metadata` to `savefig`
  to strip the default Software/date fields.
- All iteration over cases, tiers, families, and lanes in sorted, explicit order.
- Target: two consecutive runs over the same inputs produce byte-identical files. If byte equality proves
  brittle for a reason outside our control, fall back to asserting pixel-array equality of the rendered
  canvases and surface the substitution in the pull request description rather than silently weakening the test.

## 7. Dependency justification

Adds `matplotlib` (and nothing else) via `uv add`, lockfile committed. Justification: the harness's
deliverable includes a written analysis whose findings are quantitative rates and matrices; static,
regenerable figures are part of the report surface. No numpy pin beyond what matplotlib brings. No seaborn,
no plotly, no pandas for this module.

## 8. Repo hygiene

- Add `figures/` to `.gitignore` when the figure module lands.
- Publication copies will later be committed by hand to `docs/figures/` after visual review and final
  regeneration against the final cache. That step is out of scope for this feature and is noted here only so
  the gitignore choice is legible. *(Retroactive correction: the publication path was corrected to `docs/figures/` when that path was settled during release preparation; the spec originally named `assets/figures/`.)*

## 9. Acceptance criteria

Written as the definition of done. Implement as `pytest` under `tests/report/test_figures.py` using a small
synthetic scored-results fixture authored inside the test package (never touching committed fixtures or the
frozen export).

1. `report figures --out TMP` against a complete synthetic scored-results fixture creates exactly the six
   inventory files and nothing else.
2. Running the command twice into two temp dirs yields byte-identical files per the determinism target in
   section 6.
3. With adjudication results present and adversarial results absent, the command emits the four adjudication
   figures, skips the adversarial figure, reports the skip by name, and exits zero.
4. With no scored results present, the command exits nonzero and names the missing artifacts.
5. Every rate rendered in `over_erasure_by_tier.png` equals the scoring module's computed over-erasure rate
   for the same fixture, asserted by calling the scoring primitives directly in the test, not by
   reimplementing the math in the test.
6. Confusion heatmap cell counts sum to the fixture's total graded verdicts per tier.
7. Wilson interval computation is a single shared helper used by both bar figures, unit-tested against two
   hand-computed reference values.
8. The figure module imports nothing from `runners/` and makes no network calls; test asserts no model-seam
   invocation occurs (seam spy or equivalent).
9. `ruff` clean, suite green in CI without network access.

## 10. Delivery conventions

- Commit scope prefix: `report:` (developer-facing; no block-N vocabulary exists in this repo's reader
  surfaces and none is introduced).
- Two-commit pattern on the feature branch: first the spec and test skeleton with the acceptance list encoded
  as failing tests marked expected-to-fail, then implementation flipping them green. Never a commit with a
  red suite unmarked.
- Pull request description links this spec and states the determinism target outcome (byte-identical achieved or
  fallback used, per section 6).

## 11. Stop conditions

Stop and surface rather than choosing silently if any of these arise:

- Scored-results schema ambiguity (section 3).
- The scoring module does not expose a primitive needed for the variance figure's per-case agreement cut.
- Byte-identical output is unachievable and the pixel-array fallback also proves flaky.
- Any need to touch a file outside `report/figures/`, the CLI registration point, `tests/report/`,
  `.gitignore`, or dependency files.

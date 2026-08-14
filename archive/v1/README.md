# v1 archive (16 subjects, 34 locations)

Frozen snapshot of the published 16-subject / 34-location experiment.

- Agent pin: [`3562059939cbaac3dc3500593f2940ef34c54c53`](https://github.com/KrishnaDev-Palem/dpdp-erasure-agent/commit/3562059939cbaac3dc3500593f2940ef34c54c53)
- Tag: `eval-v1.0.0`

The July 2026 post: [Should an AI Decide What Gets Erased? I Measured It](https://krishnadev.me/writing/should-an-ai-decide-what-gets-erased-i-measured-it/).

This directory is a thin in-repo copy of the committed `export/`, the twelve committed `results/` JSON files, `docs/writeup.md`, and `docs/figures/`. It is a snapshot a reader can browse without checking out a tag. It is not a second answer key, and the harness does not load it.

To replay the published numbers in full, including the committed cache, check out the tag — the tag, not this directory, holds the cache — then run the offline reproduce commands from the root README:

```bash
git checkout eval-v1.0.0
uv sync

MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval t1 --json
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval t2 --json
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval t3 --json
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval autonomous --json
MODEL_ID=claude-sonnet-5 CACHE_MODE=offline uv run dpdp-eval autonomous-retrieval-split --json
MODEL_ID=gemini-3.5-flash CACHE_MODE=offline uv run dpdp-eval adversarial-gate --json
```

Do not load `archive/v1/export` as the default answer key.

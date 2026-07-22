# Reachability Experiment Harness

The deterministic suites in this repository inject cross-layer drift and then
evaluate pre-constructed semantic queries. That measures detector coverage over
the operator taxonomy. It does not measure whether an actual LLM data agent,
given a natural-language request, would emit a query that exposes the drift.
The reachability harness (`src/policystrata/reachability.py` and
`scripts/reachability-study.py`) closes that gap.

## What the harness measures

For each mutation operator in a domain, the harness builds one reachability
case:

- a principal and a target intent (the semantic query the generator would use
  for that operator);
- K natural-language paraphrases of that intent — deterministic, seeded,
  template-based by default, with a hook to load hand-written paraphrase files
  from a directory (`<mutation_id>.txt`, one paraphrase per line, `#` comments
  ignored);
- a manifest-derived system prompt rendered from the domain policy. For
  manifest-affecting operators the prompt is rendered from the mutated
  (stale-alias) manifest, because the operator's premise is that the retired
  alias is still model-visible.

For each paraphrase, the model client is asked to emit a semantic query as a
single JSON object. Invalid replies are re-prompted with the parse error, up to
a bounded repair budget (`ReachabilityBudget.max_attempts` model calls per
paraphrase). Each parsed query is evaluated with the standard `evaluate_task`
pipeline against the mutated surface configuration.

A drift is **reached** when at least one emitted query triggers the expected
witness class for that operator. The JSON report records, per case: reached or
not-reached, and per paraphrase: attempt counts, the emitted query, the
observed witness class, localization, containment, and any parse error.

## Manifest-skew behavioral probe

`run_manifest_skew_probe` renders two system prompts from the same policy: one
from the current manifest and one version-skewed prompt in which a retired
metric alias remains model-visible (per the `stale_metric_alias_manifest`
operator). It sends the same request under both prompts and records whether
the emitted plans differ (`plans_differ` in the report). A difference shows
that Layer 1 (manifest) skew has a behavioral effect on model output, which is
the mechanism the manifest operator family assumes.

## Running the stub demo

The default client is `DeterministicStubClient`: a rule-based extractor that
parses the manifest lines out of the system prompt and applies fixed rules to
the paraphrase text. It is free, offline, and reproducible:

```sh
uv run python scripts/reachability-study.py --out runs/reachability-stub
```

This writes `runs/reachability-stub/reachability_report.json` and prints a
per-operator summary. Useful flags: `--paraphrases K`, `--seed N`,
`--max-attempts N`, `--mutations id ...`, `--paraphrase-dir DIR`,
`--skip-skew-probe`.

## Running the real study

The real study uses the Anthropic API through `AnthropicClient`. The
`anthropic` package is intentionally **not** a policystrata dependency.
Requirements:

1. `pip install anthropic` in the environment that runs the script;
2. `export ANTHROPIC_API_KEY=...` (the key is read only from that environment
   variable and is never logged or echoed);
3. `POLICYSTRATA_ALLOW_PAID_CALLS=1` — the script refuses to run the anthropic
   client without this explicit opt-in, because the run incurs API cost.

```sh
POLICYSTRATA_ALLOW_PAID_CALLS=1 uv run python scripts/reachability-study.py \
    --client anthropic --out runs/reachability-real
```

The model id defaults to `claude-sonnet-5` and can be overridden with the
`POLICYSTRATA_REACHABILITY_MODEL` environment variable.

## Cost expectations

Upper bound on API calls per run:

```
calls <= cases x paraphrases x max_attempts  +  2 x max_attempts (skew probe)
```

Repair attempts only happen on invalid JSON, so the typical count is
`cases x paraphrases + 2`. For the `support_saas` defaults (14 operators, 4
paraphrases, 3 max attempts) that is 58 calls typical, 174 worst case. Each
call carries a short manifest prompt and a one-line request (roughly a few
hundred input tokens and under two hundred output tokens), so:

```
cost ~= calls x (input_tokens x input_rate + output_tokens x output_rate)
```

at the current per-token rates of the selected model.

## Honest framing of results

- **Stub results are harness verification, not reachability evidence.** The
  stub is a deterministic extractor aligned with the same templates that
  generate the paraphrases, so stub "reached" rates say nothing about what a
  real model would emit. The stub run exists to show the pipeline is wired
  correctly end to end.
- **Only real-model runs produce reachability evidence**, and the result is
  specific to the model id recorded in the report (`client` field), the
  paraphrase set, and the repair budget.
- **No real-model runs have been performed yet.** As of this writing, no
  reachability evidence exists; the harness is built and verified with the
  stub only. Any future claim about natural-language reachability must cite a
  report produced with `--client anthropic` (or another real client) and state
  the model id, seed, paraphrase count, and budget.
- Some operators are structurally easy to reach: for database-affected
  operators the simulator localizes the violation at the database layer for
  any valid emitted query, so reachability there mostly measures whether the
  model produces a well-formed query at all. Per-case witness classes and
  emitted queries in the report make this visible.

# Benchmark Release and Productization

What a third party needs to run PolicyStrata's benchmark against their own
detector and report comparable numbers.

## Versioned, frozen suites

Each scored suite is pinned by a freeze manifest that hashes the policy,
surfaces, tasks, operator taxonomy, detector source, and generator source:

```bash
uv run policystrata freeze-benchmark --domain support_saas --suite generated \
  --count 500 --seed 1729 --out freeze/support-generated.json
uv run policystrata verify-freeze freeze/support-generated.json
```

`verify-freeze` recomputes the hashes from the current tree and fails if the
detector, taxonomy, policy, or suite changed. That is the mechanism a leaderboard
uses to guarantee everyone ran the same benchmark version. The full reproduction
is `scripts/reproduce-final.sh`.

## Difficulty tiers

`policystrata.difficulty` scores every non-clean case by how many baseline
detection strategies catch it and buckets it hard / medium / easy. Over the
support_saas generated suite (500 cases, 15 baseline strategies):

| Tier | Cases |
| --- | --- |
| hard | 0 |
| medium | 357 |
| easy | 143 |

No operator evades every strategy (so no "hard" tier here), but operators differ
sharply in how many strategies catch them - from `db_rls_old_ownership_field` (3)
to grammar/manifest cases (7+). A leaderboard can weight cases by
`mean_baseline_catchers` so a detector is rewarded for the cases conventional
tools miss, not the ones everything already catches.

```bash
uv run policystrata run --domain support_saas --suite generated --count 500 --out runs/gen
python -c "from pathlib import Path; from policystrata.difficulty import difficulty_report_from_runs; \
print(difficulty_report_from_runs([Path('runs/gen')]).model_dump_json(indent=2))"
```

## Harness adapters

Runs export to external eval harnesses without coupling the core:

```bash
uv run policystrata export runs/gen --format inspect --out gen.inspect.jsonl
uv run policystrata export runs/gen --format benchflow --out gen.benchflow.json
uv run policystrata export runs/gen --format policystrata-json --out gen.evidence.json
```

`inspect` and `benchflow` are framework adapters; `policystrata-json` is a
generic evidence export (aggregate counts, trace IDs, semantic IR,
expected/observed witness classes, cost/latency) that omits raw request text,
raw SQL, and raw result values.

## What is still external

- A public leaderboard and third-party reproduction reports require hosting and
  other people running it; those cannot be produced from inside this repo. The
  freeze/verify + difficulty + adapter pieces are the machinery they would use.
- Difficulty tiers are defined against the current baseline set; adding stronger
  baselines (see the comparators in the evidence table) would re-tier cases and
  is the intended way the benchmark stays honest as tools improve.

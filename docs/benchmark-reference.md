# Benchmark Reference

PolicyStrata's deterministic benchmark suite is **DataPolicyDriftBench**. It focuses on B2B SaaS
embedded analytics: tenant isolation, PII restrictions, metric authorization, gross/net revenue
drift, join-grain bugs, fiscal/calendar time drift, query-cost budgets, database containment,
release controls, and ClickHouse-style product analytics policies.

The current benchmark is reproducible without an LLM API key. It is artifact evidence over
implemented operators and fixtures, not evidence of recall on unknown production incidents.

## Suites

Run the main deterministic suites:

```bash
uv run policystrata run --domain support_saas --suite seeded --out runs/repro/seeded
uv run policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out runs/repro/generated
uv run policystrata run \
  --domain support_saas \
  --suite generated_alt_seed \
  --out runs/repro/generated_alt_seed
uv run policystrata run --domain finance_saas --suite seeded --out runs/repro/finance
uv run policystrata run --domain analytics_clickhouse --suite seeded --out runs/repro/analytics
uv run policystrata run --domain support_saas --suite clean_controls --count 80 --seed 260627 --out runs/repro/clean-controls
```

`seeded` is a static public suite. `generated` synthesizes deterministic variants from the policy,
surface versions, seed, and mutation operators. `generated_alt_seed` is a secondary generated suite,
not a blinded held-out set. The legacy suite name `held_out` remains accepted for compatibility,
but should not be used in paper claims unless cases were produced after a detector freeze or
authored independently.

`heldout_v1` is the detector-freeze-oriented generated held-out suite. Use it with
`freeze-benchmark` and `--freeze-manifest` so reviewers can verify that the detector, mutation
registry, generator, policy, surfaces, seed, count, and suite materialization did not change.

`clean_controls` generates authorized and denied no-drift cases for false-positive accounting.

## Domains

Built-in domains:

- `support_saas`: support tickets, invoices, subscriptions, customer PII, tenant isolation.
- `finance_saas`: households, advisors, accounts, transactions, balances, firm isolation, sensitive
  household identifiers.
- `analytics_clickhouse`: product analytics events, sessions, projects, aggregate-only viewers,
  cohort release thresholds, materialized-view lineage, and ClickHouse row-policy assumptions for
  read-only users.

Both domains declare surface responsibility contracts. The point is not that every layer must equal
the canonical policy. Each layer has a declared job, and transitions must preserve the obligations
that layer accepted.

## Generated Mutants

Current operators include:

- stale model-visible metric aliases;
- grammar exposure of forbidden sensitive dimensions;
- validator omissions for sensitive columns;
- dropped tenant predicates;
- swapped tenant/account scope predicates;
- stale tenant keys;
- gross/net metric drift;
- fanout joins;
- fiscal/calendar time drift;
- removed `DISTINCT`;
- left joins changed to inner joins;
- missing database deny propagation;
- cost estimator drift.
- ClickHouse project-policy gaps;
- small-cohort release drift;
- materialized-view lineage loss;
- timezone bucket drift;
- unique-user/session grain drift;
- sampled aggregate release drift.

Generated mutants are policy-driven, but they are generated from the same public taxonomy used by
the deterministic simulator and expected-label fixtures. Treat their results as reproducibility and
operator-coverage evidence, not as blinded external recall evidence.

## Baselines

PolicyStrata includes executable baseline evaluators over trace files:

- `final_answer_only`
- `sql_snapshot`
- `validator_only`
- `db_rls_only`
- `random_data_generation`
- `naive_surface_equality`
- `defense_in_depth_stack`
- `grammar_only`
- `semantic_validator_only`
- `sql_ast_policy_checker`
- `db_policy_only`
- `release_filter_only`
- `lineage_only`
- `policy_as_code_precheck`
- `defense_in_depth_stack_v2`

Run:

```bash
uv run policystrata baselines runs/repro/seeded
uv run policystrata ablations runs/repro/seeded runs/repro/analytics
```

These are intentionally simple observability models. PolicyStrata's own killed/survived count is
reported in the suite table, not as a baseline row. `defense_in_depth_stack` is the strongest
baseline currently included: it counts a mutant as caught if a validator-only check, SQL snapshot,
database/RLS check, or final-answer semantic-difference check would catch it.

## Evidence Tables

After producing one or more runs, regenerate paper-style tables:

```bash
scripts/reproduce-evidence.sh
```

Equivalent direct command:

```bash
scripts/reproduce-final.sh
```

The output includes:

```text
Suite | Mutants | Killed | Survived | Equivalent | Invalid | Clean controls | False positives | Median witness bytes | Evidence level | Provenance | Detector frozen
Evidence level | Suites | Mutants
Baseline | Failures caught | Catch rate
```

Static suite YAML files may include top-level `suite_metadata` to mark externally authored,
detector-frozen, incident-reconstruction, or blinded evidence. The runner writes that metadata into
`metadata.json`; the evidence renderer keeps those suites separate from public/generated scores.

The current checked-in snapshot is in [evidence.md](evidence.md). Methodology details are in
[methodology.md](methodology.md).

## Artifact Usability Report

Artifact-heavy venues often ask whether another lab can run and inspect the artifact without hidden
services. Generate a compact run report with:

```bash
uv run policystrata artifact-report runs/repro/seeded
uv run policystrata artifact-report runs/repro/seeded --format json
```

The report includes trace count, non-clean trace count, minimized witness count, median witness
bytes, trace latency, estimated policy cost, run artifact size, built-in domain fixture size, suite
provenance, detector-freeze status, and whether an LLM API key is required.

## Witness Shape

A minimized witness keeps the replay-stable record needed to explain the violated obligation. It
preserves fields such as:

```json
{
  "task_id": "compiler_drops_tenant_predicate_01",
  "witness_class": "lowering_violation",
  "localized_surface": "compiler",
  "containment_layer": "database",
  "principal": "acme_analyst",
  "request": "Show ticket count by region for my tenant, variant 1.",
  "semantic_ir": {
    "metric": "ticket_count",
    "dimensions": [],
    "time_range": "last_month",
    "limit": 100
  },
  "compiled_sql": "select count(distinct support_tickets.id) as value ...",
  "contract_decisions": {
    "compiler": {
      "allowed": false,
      "reasons": [
        "tenant-scope obligation was not preserved during SQL lowering"
      ]
    }
  },
  "release_allowed": false,
  "reasons": [
    "compiled SQL does not include the canonical tenant predicate"
  ]
}
```

See [failure-taxonomy.md](failure-taxonomy.md) for witness classes and [methodology.md](methodology.md)
for minimization boundaries.

## Limits

- Generated mutants are derived from the same taxonomy used by the deterministic simulator and
  expected-label fixtures.
- `generated_alt_seed` is not a blinded held-out set.
- `heldout_v1` is detector-frozen generated evidence when paired with a freeze manifest; it is not
  externally authored by default.
- Equivalent and stillborn mutant accounting is defined, but the current generators do not emit
  those cases.
- Deterministic benchmark runs simulate database effects.
- Finance and support domains are synthetic built-in fixtures.
- Baselines are simple observability models, not full production test suites.

# PolicyStrata

PolicyStrata is an experimental open-source framework for regression-testing policy drift in LLM
data-agent stacks.

It checks whether authorization, semantic, and release obligations survive across non-equivalent
layers: model-visible manifests, grammars, validators, semantic compilers, database RLS, and output
filters.

The current artifact ships with deterministic `support_saas` and `finance_saas` benchmarks, 50
hand-seeded support drift cases, generated mutation suites, minimized witnesses, JSONL traces,
baseline comparisons, a dbt Semantic Layer adapter, and optional PostgreSQL RLS fixtures.

Status: early research artifact. Useful for reproducing the paper's core failure model; not a
production security scanner.

The benchmark suite, **DataPolicyDriftBench**, focuses on B2B SaaS embedded analytics: tenant
isolation, PII restrictions, metric authorization, gross/net revenue drift, join-grain bugs,
fiscal/calendar time drift, query-cost budgets, and database containment.

The current version is deterministic and does not require an LLM API key.

## Open Source First

PolicyStrata should remain reproducible as an open-source research artifact: deterministic runs,
mutation suites, traces, witnesses, baselines, adapters, and evidence scripts.

Commercial work should build around operating it in real stacks: private CI, self-hosted runners,
enterprise connectors, dashboards, audit exports, managed regression campaigns, custom adapters, and
support. The core mechanism should stay inspectable.

See [`docs/open-source-commercial-strategy.md`](docs/open-source-commercial-strategy.md) for the
packaging boundary.

## What It Tests

PolicyStrata does not assume every layer should behave identically. Simple equality between the
manifest, grammar, validator, compiler, database, and release layer is not the right property
because those layers have different jobs.

Instead, each surface declares a responsibility set:

- `manifest`: expose model-visible capabilities without stale or forbidden options.
- `grammar`: parse the declared intent space and preserve untrusted intent for validation.
- `validator`: authorize semantic queries and bind principal, tenant, time, and budget obligations.
- `compiler`: lower authorized semantic IR into SQL while preserving metric, tenant, time, and row
  obligations.
- `database`: contain row access with RLS and other database-side controls.
- `release`: withhold contained or unauthorized results.

The trace records both surface decisions and contract decisions. A grammar can be broader than the
validator by design, while a compiler that drops a tenant predicate violates the tenant-scope
obligation it accepted from validation.

## Install

```bash
uv sync --extra dev
```

## CLI

```bash
policystrata init-domain support_saas
policystrata run --domain support_saas --suite seeded --out runs/example
policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out runs/generated
policystrata run --domain support_saas --suite generated_alt_seed --out runs/generated_alt_seed
policystrata run --domain finance_saas --suite seeded --out runs/finance
policystrata summarize runs/example
policystrata baselines runs/example
policystrata evidence \
  seeded=runs/example \
  generated=runs/generated \
  generated_alt_seed=runs/generated_alt_seed \
  finance_saas=runs/finance \
  --out runs/evidence.md
policystrata minimize --witness runs/example/witnesses/<id>.json
policystrata scan --config examples/postgres_dbt/policystrata.yaml --out runs/scan
```

The default `run` command uses the built-in deterministic domain fixtures and writes:

```text
runs/<id>/traces.jsonl
runs/<id>/summary.json
runs/<id>/metadata.json
runs/<id>/witnesses/*.json
```

## Production Scanner

`policystrata scan` is the production-oriented path. It is separate from the deterministic
benchmark runner and treats PolicyStrata as a scanner and release gate, not as an authorization
boundary.

The scanner reads a `policystrata.yaml` config with:

- dbt Semantic Layer YAML files;
- imported SQL/semantic trace JSONL files;
- optional schema/seed fixtures and PostgreSQL RLS checks;
- fuzzing and gate settings.

Example:

```bash
policystrata scan --config examples/postgres_dbt/policystrata.yaml --out runs/scan
```

The command writes:

```text
runs/scan/scan.json
runs/scan/findings.jsonl
runs/scan/summary.json
runs/scan/report.md
runs/scan/witnesses/*.json
runs/scan/scan.sarif  # when sarif: true
```

Gate behavior:

- exit code `0`: pass or warning-only scan;
- exit code `1`: high-confidence gate failure;
- parser/config errors still return normal CLI usage errors.

The default gate fails high-confidence authorization, tenant-scope, RLS, unsafe-release, and
semantic-drift findings. Static adapter mismatches and optional unavailable database fixtures are
warnings unless configured as required.

Imported SQL is never executed unless it passes the read-only SQL allowlist. Production database
checks go through Python/`psycopg`; host `psql` is not required. When a PostgreSQL fixture is
configured, authorized imported traces are executed beside canonical compiler SQL under the same
tenant context and any row difference becomes real-db semantic-drift evidence.

The recommended first deployment shape is a disposable Docker/PostgreSQL fixture or sanitized
clone, not direct mutation of a customer database. The scanner can start a compose service when
configured:

```yaml
database:
  start_docker: true
  compose_file: ../../docker-compose.yml
  compose_service: postgres
  schema: ../../src/policystrata/domains/support_saas/schema.sql
  seed: ../../src/policystrata/domains/support_saas/seed.sql
```

## Generated Mutants

The handwritten `support_saas` seeded suite is useful for artifact validation, but generated mutants
are the stronger reproducibility story. `--suite generated` synthesizes deterministic variants from
the policy, surface versions, and mutation operators.

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

`--suite generated_alt_seed` uses the same generator with a different default count and seed. Treat
it as a secondary generated suite, not as a blinded research held-out set. The legacy suite name
`held_out` remains accepted for compatibility, but it should not be used in paper claims unless the
cases were generated after a detector freeze or authored independently.

## Domains

Built-in domains:

- `support_saas`: support tickets, invoices, subscriptions, customer PII, tenant isolation.
- `finance_saas`: households, advisors, accounts, transactions, balances, firm isolation, sensitive
  household identifiers.

Both domains declare surface responsibility contracts. The point is not that every layer must equal
the canonical policy. Each layer has a declared job, and transitions must preserve the obligations
that layer accepted.

## Baselines

PolicyStrata includes executable baseline evaluators over trace files:

- `final_answer_only`
- `sql_snapshot`
- `validator_only`
- `db_rls_only`
- `random_data_generation`
- `naive_surface_equality`

Run:

```bash
policystrata baselines runs/example
```

These are intentionally simple baseline observability models. PolicyStrata's own killed/survived
count is reported in the suite table, not as a baseline row.

## Evidence Tables

After producing one or more runs, regenerate paper-style tables:

```bash
scripts/reproduce-evidence.sh
```

The output includes:

```text
Suite | Mutants | Killed | Survived | Equivalent declared | Median witness bytes
Baseline | Failures caught | Catch rate
```

The numbers are computed from the traces and witnesses in the run directories.

The current checked-in snapshot is in [`docs/evidence.md`](docs/evidence.md). The current benchmark
reports 620/620 killed mutants across the `seeded`, `generated`, `generated_alt_seed`, and
`finance_saas` seeded suites.

What this proves:

- PolicyStrata kills 620/620 non-equivalent mutants generated by the current deterministic
  operators and fixtures. The current suites declare no equivalent mutants.
- The run metadata records the mutation operator IDs used to produce each evidence snapshot.
- The witness files localize each killed mutant to a declared surface responsibility from the
  observed trace decisions and contract outcomes.

What this does not prove:

- It does not establish recall on unknown production incidents.
- It does not show production security-scanner effectiveness.
- It does not remove the circularity risk that generated mutants come from the same taxonomy as the
  deterministic simulator and expected-label fixtures.

That result measures coverage over the current deterministic mutation operators and fixtures. It
does not imply recall on unknown production incidents.

Methodology details are in [`docs/methodology.md`](docs/methodology.md).

## Sample Witness

A minimized witness keeps the smallest stable record needed to explain the violated obligation:

```json
{
  "compiled_sql": "select count(distinct support_tickets.id) as value, accounts.region as region from accounts left join subscriptions on subscriptions.account_id = accounts.id left join invoices on invoices.subscription_id = subscriptions.id left join support_tickets on support_tickets.account_id = accounts.id where invoices.invoice_date >= date '2026-05-01' and invoices.invoice_date < date '2026-06-01' group by accounts.region limit 100",
  "containment_layer": "database",
  "contract_decisions": {
    "compiler": {
      "allowed": false,
      "reasons": [
        "compiler violated its declared responsibility: The compiler drops the principal's tenant predicate.",
        "tenant-scope obligation was not preserved during SQL lowering"
      ]
    },
    "database": {
      "allowed": true,
      "reasons": [
        "database contained a downstream obligation violation"
      ]
    },
    "grammar": {
      "allowed": true,
      "reasons": []
    },
    "manifest": {
      "allowed": true,
      "reasons": []
    },
    "release": {
      "allowed": true,
      "reasons": []
    },
    "validator": {
      "allowed": true,
      "reasons": []
    }
  },
  "db_result": {
    "actual_value": 18,
    "blocked_by_database": true,
    "intended_value": 10,
    "rows": 0
  },
  "localized_surface": "compiler",
  "principal": "acme_analyst",
  "reasons": [
    "The compiler drops the principal's tenant predicate.",
    "compiled SQL does not include the canonical tenant predicate",
    "compiled behavior differs from canonical semantic intent on the generated database state"
  ],
  "release_allowed": false,
  "request": "Show ticket count by region for my tenant, variant 1.",
  "semantic_ir": {
    "dimensions": [
      "region"
    ],
    "filters": {},
    "grain": "month",
    "limit": 100,
    "metric": "ticket_count",
    "time_range": "last_month"
  },
  "surface_responsibilities": {
    "compiler": [
      "preserve_authorized_metric_semantics",
      "preserve_tenant_scope_predicates",
      "preserve_time_semantics",
      "preserve_row_budget"
    ],
    "database": [
      "enforce_tenant_isolation_rls",
      "contain_cross_tenant_row_access"
    ],
    "grammar": [
      "parse_declared_query_intents",
      "preserve_untrusted_intent_for_validation",
      "avoid_advertising_capabilities_outside_manifest_scope"
    ],
    "manifest": [
      "expose_model_visible_metrics_and_dimensions",
      "omit_retired_aliases_and_forbidden_capabilities"
    ],
    "release": [
      "enforce_release_decision",
      "withhold_contained_or_unauthorized_results"
    ],
    "validator": [
      "authorize_metric_dimension_time_and_budget",
      "bind_principal_tenant_scope",
      "produce_canonical_semantic_obligations"
    ]
  },
  "surface_versions": {
    "compiler": "v5",
    "database": "v7",
    "grammar": "v7",
    "manifest": "v7",
    "release": "v7",
    "validator": "v7"
  },
  "task_id": "compiler_drops_tenant_predicate_01",
  "transition_obligations": [
    "capability_scope",
    "syntactic_intent",
    "authorization_decision",
    "metric_semantics",
    "tenant_scope",
    "row_budget",
    "sql_semantics",
    "database_containment_request",
    "row_access_result"
  ],
  "witness_class": "lowering_violation"
}
```

## Known Limitations

- Generated mutants are derived from the same taxonomy used by the deterministic simulator and
  expected-label fixtures.
- `generated_alt_seed` is not a blinded held-out set; legacy `held_out` is only a compatibility
  alias for that secondary generated suite.
- Equivalent and stillborn mutant accounting is defined in the methodology, but the current
  generators do not emit those cases.
- Deterministic benchmark runs simulate database effects; `scan` can run real PostgreSQL fixture
  checks when configured.
- The dbt integration remains an adapter, but scanner diagnostics include names, metric expression
  references, sensitive dimension metadata, and semantic-model lineage presence.
- Imported SQL/IR fuzzing mutates configured traces; it does not execute arbitrary customer
  application code.
- Baselines are simple observability models, not full production test suites.

## Dockerized PostgreSQL Domain

The repo includes a Docker Compose service and SQL fixtures for the built-in domains:

```bash
docker compose up -d postgres
```

The deterministic runner does not require host `psql`. PostgreSQL integration is accessed through
Python using `psycopg`.

To produce a real RLS evidence table against the Docker fixture:

```bash
uv run python scripts/postgres-rls-evidence.py
```

Expected output shape:

```text
| PostgreSQL check | app.tenant_id | Rows | Tenant ids | Result |
| --- | --- | --- | --- | --- |
| accounts RLS | acme | 2 | acme | pass |
| accounts RLS | beta | 2 | beta | pass |
| accounts RLS | <unset> | 0 | - | pass |
```

## Real Integration

The repo also includes a small dbt Semantic Layer adapter and fixture:

```bash
policystrata check-integration dbt-semantic \
  --domain finance_saas \
  --path examples/integrations/dbt_semantic/finance_saas/semantic_models.yml
```

The adapter compares dbt metric, measure, and dimension names against a PolicyStrata domain policy.
Scanner diagnostics additionally check simple measure-expression references, sensitive dimension
metadata, and semantic-model lineage presence. It is deliberately an adapter; core execution is not
coupled to dbt.

## Research Boundary

PolicyStrata tests cross-layer policy drift. It does not claim that grammars, constrained decoding,
or semantic IRs are authorization boundaries.

## Paper And Benchmark

The research contribution is the combination of:

- the PolicyStrata OSS engine;
- the DataPolicyDriftBench benchmark;
- a taxonomy of stale manifests, weak validators, SQL lowering drift, weak RLS, unsafe release, and
  semantic metric drift;
- minimized witnesses that identify the principal, request, policy versions, surface versions,
  compiled SQL, containment layer, and failed contract.

The current seeded suite is useful for artifact validation. Stronger paper evidence should add
more real integrations, stronger held-out bug sources, larger false-positive corpora for
intentional asymmetry, and runtime/scaling numbers.

# Scanner Reference

`policystrata scan` is the production-oriented path. It is separate from the deterministic
benchmark runner and treats PolicyStrata as a scanner and release gate, not as an authorization
boundary.

## Inputs

The scanner reads a `policystrata.yaml` config with:

- dbt Semantic Layer YAML files;
- imported SQL or semantic trace JSONL files;
- optional policy, terms, privacy, DPA, or internal policy documents for doctor/audit accounting;
- optional prompt/tool manifest exports for doctor/audit accounting;
- optional source maps from traces back to tools, routes, or query-builder code paths;
- tenancy predicates and tenant-column vocabulary for real app schemas;
- optional schema and seed fixtures;
- optional PostgreSQL RLS checks and state assertions;
- fuzzing and gate settings.

Create a starter scanner project:

```bash
uv run policystrata init-scan --out policystrata
uv run policystrata scan --config policystrata/policystrata.yaml --out runs/policystrata-smoke
```

The basic scaffold defaults to `support_saas`. Pass `--source-domain finance_saas` to copy the
finance policy and generate a finance-specific starter trace with the correct principal, metric,
and firm-scope predicate.

Installed wheels also include a Postgres/dbt scanner example that can be copied into a local
directory:

```bash
uvx policystrata init-scan postgres_dbt --out policystrata-example
uvx policystrata scan --config policystrata-example/policystrata_clean.yaml --out runs/scan-clean
```

The clean example is a passing smoke test:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata_clean.yaml --out runs/scan-clean
```

The repo also includes an intentionally failing scanner fixture:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata.yaml --out runs/scan
```

That example should exit `1` because it contains imported traces with authorization,
unsafe-release, and tenant-scope findings. Use it to inspect gate-failure output, not as the first
clean smoke test.

## Outputs

The scanner writes:

```text
runs/scan-clean/scan.json
runs/scan-clean/findings.jsonl
runs/scan-clean/summary.json
runs/scan-clean/report.md
runs/scan-clean/witnesses/*.json
runs/scan-clean/scan.sarif  # when sarif: true
```

Findings carry evidence levels such as `deterministic_fixture`, `imported_trace`,
`property_generated`, and `real_db`. See [methodology.md](methodology.md) and
[../EVAL_CARD.md](../EVAL_CARD.md) for the evidence boundary.

`summary.json` also includes `evidence_exercised`, which counts configured evidence that was
successfully checked even when it produced no finding. This is separate from `evidence_levels`,
which counts findings by evidence level. Clean scans should therefore still show imported-trace,
property-generated, or real-db coverage when those checks ran and passed.

`summary.json` includes `integration_readiness`, a configured-readiness level with stages. This is
separate from the gate outcome; a scan can be configured for CI gating and still fail the current
gate because it found drift.

- `demo-ready`: scanner command and policy fixture can run.
- `fixture-ready`: policy and surface fixtures are loadable.
- `trace-ready`: imported traces were loaded and checked.
- `db-ready`: PostgreSQL fixture, RLS checks, state assertions, or real-db comparisons ran.
- `ci-gate-ready`: scan inputs are configured for CI gate exit codes.

## Doctor / Audit Mode

`policystrata doctor` without arguments keeps the lightweight reproducibility check:

```bash
uv run policystrata doctor
```

Pass a scanner config to get a first-class stack audit:

```bash
uv run policystrata doctor --config policystrata/policystrata.yaml
uv run policystrata doctor --config policystrata/policystrata.yaml --format markdown --out runs/doctor.md
```

The config audit reports what is wired and what is missing across policy/domain YAML, surface
contracts, dbt semantic inputs, app SQL traces, tenancy checks, database fixtures, RLS checks, state
assertions, release-layer tests, policy document inputs, prompt/tool manifest inputs, source maps,
export traces, and CI gating. Policy documents are classified deterministically as privacy policy,
terms of service, data processing agreement, internal policy, security policy, or retention policy
inputs, then scanned for obligation signals such as personal-data minimization, purpose limits,
notice/consent, data-subject rights, retention/deletion, third-party sharing, subprocessor controls,
security controls, tenant isolation, and sensitive-data controls. The audit also statically
introspects configured PostgreSQL schema SQL for tables, RLS policies, grants, views, tenant
columns, sensitive columns, and indexes. Prompt and tool manifests are parsed when they are JSON or
YAML, and exposed metrics and dimensions are compared with the canonical policy so stale or
unauthorized model-visible capabilities show up as partial wiring. It does not require an LLM API
key or host `psql`.

The audit emits remediation todos with an owner, expected files, expected tests, and a CI gate
command. Use `--strict` when missing, partial, or invalid wiring should fail CI.

Doctor-only config sections are passive for `policystrata scan` and exist to account for stack
wiring that may be enforced by current or future adapters:

```yaml
policy_docs:
  files:
    - docs/privacy.md
    - docs/terms.md
    - docs/data-processing.md
    - docs/internal-policy.md
prompt_manifests:
  files:
    - policystrata/prompts.json
source_maps:
  files:
    - policystrata/source-map.json
```

## Gate Behavior

- exit code `0`: pass or warning-only scan;
- exit code `1`: high-confidence gate failure;
- parser/config errors return normal CLI usage errors.

The default gate fails high-confidence authorization, tenant-scope, RLS, unsafe-release, and
semantic-drift findings. Static adapter mismatches and optional unavailable database fixtures are
warnings unless configured as required.

Findings include remediation fields:

- `what_changed`
- `owner`
- `probable_fix`
- `minimal_repro_trace`
- `ci_gate_command`

Imported traces and state assertions can carry regression case labels:

- `fail_to_pass`: known drift evidence should now be caught or contained.
- `pass_to_pass`: legitimate behavior should remain clean.
- `contain_to_contain`: later containment should continue blocking an attempted violation.
- `deny_to_deny`: forbidden behavior should stay denied.
- `allow_to_allow`: authorized behavior should stay usable.
- `unclassified`: legacy or unlabeled imported evidence.

## SQL Execution Boundary

Imported SQL is never executed unless it passes the read-only SQL allowlist. Production database
checks go through Python/`psycopg`; host `psql` is not required.

When a PostgreSQL fixture is configured, authorized imported traces are executed beside canonical
compiler SQL under the same tenant context. Any row difference becomes real-db semantic-drift
evidence.

The recommended first deployment shape is a disposable Docker/PostgreSQL fixture or sanitized clone,
not direct mutation of a customer database.

## Trace Contract

Imported traces are JSONL records. See [trace-contract.md](trace-contract.md) for the exact field
contract and examples for:

- `principal`
- `semantic_ir`
- `sql`
- `release_allowed`
- `expected_policy`
- `tenant_ids`

Tiny exporter recipes for TypeScript/Drizzle, Prisma, SQLAlchemy, Rails ActiveRecord, dbt Semantic
Layer, and OpenTelemetry span logs are in [trace-adapters.md](trace-adapters.md).

## Tenancy Configuration

Declare real application tenant vocabulary instead of relying on built-in fixture names:

```yaml
tenancy:
  canonical_predicates:
    - "transactions.household_id = :principal.tenant_id"
    - "accounts.household_id = :principal.tenant_id"
    - "orders.organization_id = current_setting('app.organization_id')"
  tenant_columns:
    - transactions.household_id
    - accounts.household_id
    - organization_id
```

`canonical_predicates` are the strongest signal. `tenant_columns` are also used by the fuzz layer
when generating tenant-scope mutants.

## Docker/PostgreSQL Fixture

Run a clean scanner example that executes imported SQL beside canonical compiler SQL against the
Docker/PostgreSQL fixture:

```bash
docker compose up -d postgres
uv run policystrata scan --config examples/postgres_dbt/policystrata_real_db_clean.yaml --out runs/scan-real-db-clean
```

If host port `55432` is already in use, run the fixture on another port and point the scanner at it:

```bash
POLICYSTRATA_POSTGRES_PORT=55433 docker compose up -d postgres
POLICYSTRATA_DATABASE_URL=postgresql://policystrata:policystrata@localhost:55433/support_saas \
POLICYSTRATA_APP_DATABASE_URL=postgresql://policystrata_app:policystrata_app@localhost:55433/support_saas \
  uv run policystrata scan --config examples/postgres_dbt/policystrata_real_db_clean.yaml --out runs/scan-real-db-clean
```

The scanner can start a compose service when configured:

```yaml
database:
  start_docker: true
  compose_file: ../../docker-compose.yml
  compose_service: postgres
  schema: ../../src/policystrata/domains/support_saas/schema.sql
  seed: ../../src/policystrata/domains/support_saas/seed.sql
```

To produce a standalone RLS evidence table against the Docker fixture:

```bash
docker compose up -d postgres
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

## State Assertions

State assertions are read-only database checks over expected world state. They can assert row
counts, required or forbidden result columns, and allowed or forbidden values:

```yaml
database:
  state_assertions:
    - id: acme_ticket_state_excludes_beta
      sql: "select accounts.tenant_id, count(*) as value from accounts group by accounts.tenant_id"
      tenant_id: acme
      expected_rows: 1
      require_columns: [tenant_id, value]
      forbidden_values:
        tenant_id: [beta]
      regression_case: pass_to_pass
```

These assertions are release-gating evidence. They are not a substitute for application-side
authorization, database RLS, or independent production incident validation.

## dbt Semantic Layer Adapter

The repo includes a small dbt Semantic Layer adapter and fixture:

```bash
uv run policystrata check-integration dbt-semantic \
  --domain finance_saas \
  --path examples/integrations/dbt_semantic/finance_saas/semantic_models.yml
```

The adapter compares dbt metric, measure, and dimension names against a PolicyStrata domain policy.
Scanner diagnostics additionally check simple measure-expression references, sensitive dimension
metadata, and semantic-model lineage presence. It is deliberately an adapter; core execution is not
coupled to dbt.

Use `--strict` or `--fail-on-warning` to make warning-level adapter diagnostics exit nonzero:

```bash
uv run policystrata check-integration dbt-semantic \
  --domain finance_saas \
  --path examples/integrations/dbt_semantic/finance_saas/semantic_models.yml \
  --strict
```

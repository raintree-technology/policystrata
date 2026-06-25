# Scanner Reference

`policystrata scan` is the production-oriented path. It is separate from the deterministic
benchmark runner and treats PolicyStrata as a scanner and release gate, not as an authorization
boundary.

## Inputs

The scanner reads a `policystrata.yaml` config with:

- dbt Semantic Layer YAML files;
- imported SQL or semantic trace JSONL files;
- optional schema and seed fixtures;
- optional PostgreSQL RLS checks and state assertions;
- fuzzing and gate settings.

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

## Gate Behavior

- exit code `0`: pass or warning-only scan;
- exit code `1`: high-confidence gate failure;
- parser/config errors return normal CLI usage errors.

The default gate fails high-confidence authorization, tenant-scope, RLS, unsafe-release, and
semantic-drift findings. Static adapter mismatches and optional unavailable database fixtures are
warnings unless configured as required.

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

## Docker/PostgreSQL Fixture

Run a clean scanner example that executes imported SQL beside canonical compiler SQL against the
Docker/PostgreSQL fixture:

```bash
docker compose up -d postgres
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

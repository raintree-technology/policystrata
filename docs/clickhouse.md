# ClickHouse Row-Policy Integration

The `analytics_clickhouse` domain ships a real ClickHouse fixture next to its simulated benchmark
fixture. `src/policystrata/domains/analytics_clickhouse/row_policies.sql` recreates the domain
tables on a real server, creates the `policystrata_readonly` role, per-project read-only users, and
the project-scope row policies from `schema.sql`. `ClickHouseAdapter` in
`src/policystrata/database_clickhouse.py` talks to the HTTP interface with the standard library
only; no extra dependency is needed.

Scoping works through the connecting user. The row policies use `project_id = currentUser()`, so
each scoped user is named after its project (`project_acme_mobile`, `project_beta_web`).
`policystrata_unscoped` holds the read-only role but matches no project and must see zero rows.
This is the ClickHouse counterpart of the `app.tenant_id` session setting in the PostgreSQL RLS
integration.

## Run it locally

```bash
docker compose up -d clickhouse
POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 uv run pytest tests/test_clickhouse_integration.py
uv run python scripts/clickhouse-rls-evidence.py
docker compose stop clickhouse
```

Without `POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1` the tests skip, so the default `uv run pytest` run
stays hermetic. Override the connection with `POLICYSTRATA_CLICKHOUSE_URL`,
`POLICYSTRATA_CLICKHOUSE_USER`, `POLICYSTRATA_CLICKHOUSE_PASSWORD`, and
`POLICYSTRATA_CLICKHOUSE_DATABASE` (defaults: `http://localhost:8123/`, `policystrata`,
`policystrata`, `policystrata`).

In CI the `clickhouse-integration` job runs the same tests and the evidence script against a
`clickhouse/clickhouse-server:25.6` service container. On `workflow_dispatch` the job is gated by
the `run_clickhouse` input, mirroring `run_postgres` for the PostgreSQL job.

## What it proves

- A scoped read-only user sees only its own project's rows in `events` and `sessions`.
- A read-only user outside every project sees no rows.
- Dropping the row policies is observable: the same scoped user then reads other projects' rows,
  so a missing policy shows up as real over-exposure, not as a simulated finding.
- The evidence script prints a small markdown table of these checks and exits non-zero when any
  containment check fails.

## What it does not prove

- It does not feed the deterministic benchmark score. The benchmark still runs the simulated
  `analytics_clickhouse` fixture (`schema.sql`, `seed.sql`); this integration is side evidence,
  like the PostgreSQL RLS checks.
- Row policies here are containment for read-only users only, matching the benchmark threat model.
  They are not a general authorization boundary: a user with DDL or insert rights, or with direct
  access to the `events_mv` aggregate target, could bypass them. The fixture therefore grants the
  read-only role `SELECT` on the base tables only.

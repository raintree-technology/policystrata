# SECUTE 2026 Anonymous Artifact Reviewer Guide

Artifact zip:

`/Users/mb1/Code/raintree/products/policystrata/dist/policystrata-secute-2026-anonymous-artifact.zip`

SHA256:

`d8182fb6d9b6d6a4a8ffec119e53ec6b3d34896bc4c7c24d38fb3ba376e76225`

## Review Commands

```sh
unzip policystrata-secute-2026-anonymous-artifact.zip -d policystrata-secute-review
cd policystrata-secute-review
uv run --extra dev ruff check .
uv run --extra dev mypy src
uv run --extra dev pytest
POLICYSTRATA_RUN_ROOT=/tmp/policystrata-final ./scripts/reproduce-final.sh
uv run policystrata doctor \
  --config examples/secute_security_cases/policystrata.yaml \
  --format markdown \
  --out /tmp/policystrata-secute-doctor.md
uv run policystrata scan \
  --config examples/secute_security_cases/policystrata.yaml \
  --out /tmp/policystrata-secute-scan
```

## Expected Smoke Output

- `ruff`: pass.
- `mypy`: pass.
- `pytest`: 100 passed, 5 skipped optional integration tests on the checked machine.
- SECUTE scan: expected gate fail with five high-confidence findings:
  - `unsafe_release_unauthorized_metric_exposure_reached_sql`
  - `unauthorized_trace_reached_sql_unauthorized_metric_exposure_reached_sql`
  - `tenant_scope_missing_stale_tenant_key_lowering`
  - `unsafe_release_release_leak_after_database_containment`
  - `unauthorized_trace_reached_sql_release_leak_after_database_containment`

## Pending Before Submission

Host the anonymous artifact zip in a public anonymous review location and replace the artifact URL
placeholder in the PDF source.

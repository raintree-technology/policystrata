import os
from pathlib import Path

import pytest

from policystrata.database import PostgresAdapter
from policystrata.scan_models import GateOutcome
from policystrata.scanner import run_scan

pytestmark = pytest.mark.integration
APP_DATABASE_URL = "postgresql://policystrata_app:policystrata_app@localhost:55432/support_saas"


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_DB_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_DB_TESTS=1 and start docker compose postgres",
)
def test_postgres_rls_blocks_cross_tenant_rows() -> None:
    root = Path("src/policystrata/domains/support_saas")
    adapter = PostgresAdapter()
    adapter.execute_script(root / "schema.sql")
    adapter.execute_script(root / "seed.sql")

    app_adapter = PostgresAdapter(APP_DATABASE_URL)
    rows = app_adapter.query(
        "select tenant_id, name from accounts order by tenant_id, name",
        tenant_id="acme",
    )

    assert rows
    assert {row["tenant_id"] for row in rows} == {"acme"}


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_DB_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_DB_TESTS=1 and start docker compose postgres",
)
def test_postgres_schema_setup_is_idempotent_for_existing_app_role() -> None:
    root = Path("src/policystrata/domains/support_saas")
    adapter = PostgresAdapter()
    adapter.execute_script(root / "schema.sql")
    adapter.execute_script(root / "schema.sql")
    adapter.execute_script(root / "seed.sql")

    app_adapter = PostgresAdapter(APP_DATABASE_URL)
    rows = app_adapter.query(
        "select tenant_id, name from accounts order by tenant_id, name",
        tenant_id="beta",
    )

    assert len(rows) == 2
    assert {row["tenant_id"] for row in rows} == {"beta"}


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_DB_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_DB_TESTS=1 and start docker compose postgres",
)
def test_scanner_runs_real_postgres_rls_check(tmp_path) -> None:
    config = tmp_path / "policystrata.yaml"
    config.write_text(
        f"""
version: 1
domain: support_saas
database:
  required: true
  schema: {Path("src/policystrata/domains/support_saas/schema.sql").resolve()}
  seed: {Path("src/policystrata/domains/support_saas/seed.sql").resolve()}
  rls_checks:
    - id: accounts_acme_rls
      sql: "select tenant_id, name from accounts order by tenant_id, name"
      tenant_id: acme
      expected_rows: 2
      expected_tenant_ids: [acme]
      tenant_column: tenant_id
gate:
  required_inputs: [database]
""".lstrip(),
        encoding="utf-8",
    )

    result = run_scan(config, tmp_path / "scan")

    assert result.gate.outcome == GateOutcome.PASS
    assert result.summary.total_findings == 0
    assert result.summary.evidence_exercised["real_db"] == 1


@pytest.mark.skipif(
    os.environ.get("POLICYSTRATA_RUN_DB_TESTS") != "1",
    reason="set POLICYSTRATA_RUN_DB_TESTS=1 and start docker compose postgres",
)
def test_scanner_executes_imported_trace_against_real_postgres_fixture(tmp_path) -> None:
    result = run_scan(Path("examples/postgres_dbt/policystrata_real_db_clean.yaml"), tmp_path / "scan")

    assert result.gate.outcome == GateOutcome.PASS
    assert result.summary.total_findings == 0
    assert result.summary.evidence_exercised["real_db"] >= 2

#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path

from policystrata.database import PostgresAdapter
from policystrata.evidence import markdown_table

APP_DATABASE_URL = "postgresql://policystrata_app:policystrata_app@localhost:55432/support_saas"
DOMAIN_ROOT = Path("src/policystrata/domains/support_saas")


def main() -> int:
    admin = PostgresAdapter()
    admin.execute_script(DOMAIN_ROOT / "schema.sql")
    admin.execute_script(DOMAIN_ROOT / "seed.sql")

    app = PostgresAdapter(APP_DATABASE_URL)
    rows = [
        evidence_row(app, "acme", expected_tenants={"acme"}, expected_rows=2),
        evidence_row(app, "beta", expected_tenants={"beta"}, expected_rows=2),
        evidence_row(app, None, expected_tenants=set(), expected_rows=0),
    ]

    print(markdown_table(["PostgreSQL check", "app.tenant_id", "Rows", "Tenant ids", "Result"], rows))
    return 0 if all(row[-1] == "pass" for row in rows) else 1


def evidence_row(
    adapter: PostgresAdapter,
    tenant_id: str | None,
    expected_tenants: set[str],
    expected_rows: int,
) -> list[str]:
    rows = adapter.query(
        "select tenant_id, name from accounts order by tenant_id, name",
        tenant_id=tenant_id,
    )
    observed_tenants = {str(row["tenant_id"]) for row in rows}
    passed = observed_tenants == expected_tenants and len(rows) == expected_rows
    return [
        "accounts RLS",
        tenant_id or "<unset>",
        str(len(rows)),
        ", ".join(sorted(observed_tenants)) or "-",
        "pass" if passed else "fail",
    ]


if __name__ == "__main__":
    raise SystemExit(main())

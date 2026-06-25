from pathlib import Path


def test_postgres_assets_define_rls_policies() -> None:
    root = Path("src/policystrata/domains/support_saas")
    schema = (root / "schema.sql").read_text(encoding="utf-8")
    seed = (root / "seed.sql").read_text(encoding="utf-8")

    assert "enable row level security" in schema
    assert "tenant_isolation_accounts" in schema
    assert "support_tickets" in schema
    assert "Acme Health" in seed
    assert "Beta Logistics" in seed


def test_finance_assets_define_rls_policies() -> None:
    root = Path("src/policystrata/domains/finance_saas")
    schema = (root / "schema.sql").read_text(encoding="utf-8")
    seed = (root / "seed.sql").read_text(encoding="utf-8")

    assert "enable row level security" in schema
    assert "firm_isolation_households" in schema
    assert "transactions" in schema
    assert "North Family Office" in seed
    assert "South Retirement Plan" in seed

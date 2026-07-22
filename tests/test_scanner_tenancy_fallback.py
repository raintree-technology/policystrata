"""Regression tests for the custom-domain tenant-column fallback fix.

Before the fix, a scan against a custom (domain_path) domain with no tenancy
config silently inherited the built-in ``accounts.tenant_id`` column and flagged
every trace as tenant-scope-missing. These tests pin the corrected behavior and
guard the built-in path and the per-table override.
"""

from __future__ import annotations

from policystrata.scan_models import ImportedTrace, ScanConfig, TenancyScanConfig
from policystrata.scanner import (
    builtin_domain_tenant_column,
    primary_table_from_sql,
    tenant_columns_for_scope_check,
)


def _trace(sql: str) -> ImportedTrace:
    return ImportedTrace(id="t1", principal="p", sql=sql, tenant_ids=["acme"])


def test_custom_domain_without_tenancy_has_no_scope_columns() -> None:
    config = ScanConfig(domain="brownfield_metricflow", domain_path="domain")
    assert builtin_domain_tenant_column(config) is None
    assert tenant_columns_for_scope_check(config, _trace("select 1 from metrics")) == []


def test_builtin_domain_still_uses_canonical_column() -> None:
    # No domain_path -> built-in domain -> canonical fallback preserved.
    assert builtin_domain_tenant_column(ScanConfig(domain="support_saas")) == "accounts.tenant_id"
    assert builtin_domain_tenant_column(ScanConfig(domain="finance_saas")) == "households.firm_id"
    config = ScanConfig(domain="support_saas")
    assert tenant_columns_for_scope_check(config) == ["accounts.tenant_id"]


def test_explicit_tenant_columns_win_for_custom_domain() -> None:
    config = ScanConfig(
        domain="brownfield_midday",
        domain_path="domain",
        tenancy=TenancyScanConfig(tenant_columns=["team_id"]),
    )
    assert tenant_columns_for_scope_check(config, _trace("select * from invoices")) == ["team_id"]


def test_per_table_tenant_columns_override_global() -> None:
    config = ScanConfig(
        domain="brownfield_midday",
        domain_path="domain",
        tenancy=TenancyScanConfig(
            tenant_columns=["team_id"],
            table_tenant_columns={"insight_user_status": ["user_id"]},
        ),
    )
    # A trace on the special table uses its own column...
    assert tenant_columns_for_scope_check(
        config, _trace("select * from insight_user_status where user_id = $1")
    ) == ["user_id"]
    # ...while other tables use the global column.
    assert tenant_columns_for_scope_check(
        config, _trace("select * from transactions where team_id = $1")
    ) == ["team_id"]


def test_primary_table_extraction() -> None:
    assert primary_table_from_sql("select * from public.accounts where x = 1") == "accounts"
    assert primary_table_from_sql("update team_members set role = 'x'") == "team_members"
    assert primary_table_from_sql("delete from sessions where id = 1") == "sessions"
    assert primary_table_from_sql("insert into audit_log (a) values (1)") == "audit_log"
    assert primary_table_from_sql("with cte as (select 1) select 1") is None

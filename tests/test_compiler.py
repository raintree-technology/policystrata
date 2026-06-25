from policystrata.compiler import compile_query
from policystrata.domain import load_policy
from policystrata.models import SemanticQuery


def test_compiler_preserves_tenant_predicate_by_default() -> None:
    policy = load_policy()
    principal = policy.principals["acme_analyst"]
    result = compile_query(
        policy,
        principal,
        SemanticQuery(metric="ticket_count", dimensions=["region"], time_range="last_month"),
    )

    assert result.includes_tenant_predicate
    assert "accounts.tenant_id in ('acme')" in result.sql


def test_compiler_drop_tenant_mutation_removes_tenant_predicate() -> None:
    policy = load_policy()
    principal = policy.principals["acme_analyst"]
    result = compile_query(
        policy,
        principal,
        SemanticQuery(metric="ticket_count", dimensions=["region"], time_range="last_month"),
        "compiler_drops_tenant_predicate",
    )

    assert not result.includes_tenant_predicate
    assert "accounts.tenant_id in" not in result.sql


def test_gross_net_mutation_changes_metric_expression() -> None:
    policy = load_policy()
    principal = policy.principals["acme_analyst"]
    result = compile_query(
        policy,
        principal,
        SemanticQuery(metric="net_revenue", dimensions=["plan"], time_range="last_month"),
        "gross_net_metric_drift",
    )

    assert result.metric_expression == "sum(invoices.gross_amount_cents)"


def test_compiler_swap_tenant_account_id_uses_wrong_scope_column() -> None:
    policy = load_policy()
    principal = policy.principals["acme_analyst"]
    result = compile_query(
        policy,
        principal,
        SemanticQuery(metric="ticket_count", dimensions=["region"], time_range="last_month"),
        "compiler_swaps_tenant_account_id",
    )

    assert not result.includes_tenant_predicate
    assert "accounts.id in ('acme')" in result.sql


def test_finance_compiler_uses_household_firm_scope() -> None:
    policy = load_policy("finance_saas")
    principal = policy.principals["north_advisor"]
    result = compile_query(
        policy,
        principal,
        SemanticQuery(metric="aum", dimensions=["account_type"], time_range="last_month"),
        domain="finance_saas",
    )

    assert result.includes_tenant_predicate
    assert "from households" in result.sql
    assert "households.firm_id in ('north')" in result.sql

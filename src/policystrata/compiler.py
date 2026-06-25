from __future__ import annotations

from policystrata.models import CompileResult, Policy, Principal, SemanticQuery
from policystrata.policy import PolicyOracle

DIMENSION_SQL = {
    "region": "accounts.region",
    "plan": "subscriptions.plan",
    "month": "date_trunc('month', invoices.invoice_date)",
    "severity": "support_tickets.severity",
    "customer_email": "accounts.customer_email",
    "tenant_id": "accounts.tenant_id",
}

TENANT_SCOPE_MUTATIONS = {
    "compiler_drops_tenant_predicate",
    "compiler_uses_old_tenant_key",
    "compiler_swaps_tenant_account_id",
}


def compile_query(
    policy: Policy,
    principal: Principal,
    query: SemanticQuery,
    mutation: str = "none",
    domain: str = "support_saas",
) -> CompileResult:
    oracle = PolicyOracle(policy)
    metric_name = oracle.resolve_metric(query.metric)
    metric = policy.metrics.get(metric_name)
    metric_expression = metric.expression if metric is not None else "count(*)"

    metric_expression = metric_expression_for_mutation(metric_expression, mutation, domain)

    dimensions = [dimension_sql(policy, dim) for dim in query.dimensions]
    select_parts = [f"{metric_expression} as value"]
    select_parts.extend(
        f"{dim_sql} as {dim}" for dim, dim_sql in zip(query.dimensions, dimensions, strict=True)
    )

    joins = join_path_for_mutation(domain, mutation)

    includes_tenant_predicate = mutation not in TENANT_SCOPE_MUTATIONS
    where = tenant_predicates(domain, principal, mutation)

    date_column = time_column(domain, metric.table if metric is not None else "")
    where.extend(time_predicates(query.time_range, date_column, mutation))

    where_sql = " where " + " and ".join(where) if where else ""
    group_sql = " group by " + ", ".join(dimensions) if dimensions else ""
    limit_sql = f" limit {query.limit}"
    sql = f"select {', '.join(select_parts)} {' '.join(joins)}{where_sql}{group_sql}{limit_sql}"

    return CompileResult(
        sql=sql,
        estimated_cost=estimated_cost_for_query(oracle, query, mutation),
        includes_tenant_predicate=includes_tenant_predicate,
        metric_expression=metric_expression,
        join_grain=join_grain_for_mutation(mutation),
        time_semantics=time_semantics_for_query(query, mutation),
    )


def estimated_cost_for_query(oracle: PolicyOracle, query: SemanticQuery, mutation: str) -> int:
    if mutation == "cost_estimate_ignores_expansion":
        return 1
    return oracle.estimate_cost(query)


def join_grain_for_mutation(mutation: str) -> str:
    if mutation == "fanout_join_drift":
        return "ticket_event"
    if mutation == "compiler_inner_join_drops_rows":
        return "inner_join_required"
    return "account"


def time_semantics_for_query(query: SemanticQuery, mutation: str) -> str:
    if query.time_range == "last_fiscal_month" and mutation != "fiscal_calendar_mismatch":
        return "fiscal"
    return "calendar"


def metric_expression_for_mutation(metric_expression: str, mutation: str, domain: str) -> str:
    if mutation == "gross_net_metric_drift":
        return drift_metric_expression(domain)
    if mutation == "fanout_join_drift":
        return f"({metric_expression}) * 2"
    if mutation == "compiler_removes_distinct":
        return metric_expression.replace("count(distinct ", "count(").replace("distinct ", "")
    return metric_expression


def dimension_sql(policy: Policy, dimension: str) -> str:
    configured = policy.dimensions.get(dimension)
    if configured is not None:
        return configured.column
    return DIMENSION_SQL.get(dimension, dimension)


def drift_metric_expression(domain: str) -> str:
    if domain == "finance_saas":
        return "sum(transactions.gross_amount_cents)"
    return "sum(invoices.gross_amount_cents)"


def join_path_for_mutation(domain: str, mutation: str) -> list[str]:
    joins = join_path(domain)
    if mutation == "compiler_inner_join_drops_rows":
        return [join.replace("left join", "join") for join in joins]
    return joins


def join_path(domain: str) -> list[str]:
    if domain == "finance_saas":
        return [
            "from households",
            "left join advisors on advisors.id = households.advisor_id",
            "left join accounts on accounts.household_id = households.id",
            "left join transactions on transactions.account_id = accounts.id",
            "left join balances on balances.account_id = accounts.id",
        ]
    return [
        "from accounts",
        "left join subscriptions on subscriptions.account_id = accounts.id",
        "left join invoices on invoices.subscription_id = subscriptions.id",
        "left join support_tickets on support_tickets.account_id = accounts.id",
    ]


def tenant_predicates(domain: str, principal: Principal, mutation: str) -> list[str]:
    column = tenant_filter_column(domain, mutation)
    if column is None:
        return []
    tenant_list = ", ".join(f"'{tenant}'" for tenant in principal.tenant_ids)
    return [f"{column} in ({tenant_list})"]


def tenant_filter_column(domain: str, mutation: str) -> str | None:
    if mutation == "compiler_drops_tenant_predicate":
        return None
    if mutation == "compiler_uses_old_tenant_key":
        return legacy_tenant_column(domain)
    if mutation == "compiler_swaps_tenant_account_id":
        return "accounts.id"
    return tenant_column(domain)


def time_predicates(time_range: str, date_column: str, mutation: str) -> list[str]:
    if time_range == "last_month" or (
        time_range == "last_fiscal_month" and mutation == "fiscal_calendar_mismatch"
    ):
        return [f"{date_column} >= date '2026-05-01'", f"{date_column} < date '2026-06-01'"]
    if time_range == "last_fiscal_month":
        return [f"{date_column} >= date '2026-04-27'", f"{date_column} < date '2026-05-25'"]
    if time_range == "quarter_to_date":
        return [f"{date_column} >= date '2026-04-01'", f"{date_column} < date '2026-06-24'"]
    return []


def tenant_column(domain: str) -> str:
    if domain == "finance_saas":
        return "households.firm_id"
    return "accounts.tenant_id"


def legacy_tenant_column(domain: str) -> str:
    if domain == "finance_saas":
        return "households.legacy_firm_id"
    return "accounts.legacy_tenant_id"


def time_column(domain: str, table: str) -> str:
    if domain == "finance_saas":
        if table == "balances":
            return "balances.balance_date"
        return "transactions.transaction_date"
    return "invoices.invoice_date"

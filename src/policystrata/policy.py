from __future__ import annotations

from policystrata.models import Decision, Policy, SemanticQuery


class PolicyOracle:
    """Independent canonical-policy interpreter.

    This module intentionally does not call the SQL compiler. It reasons over
    the typed semantic query, role policy, and policy metadata only.
    """

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def principal(self, principal_id: str) -> tuple[Decision, str | None]:
        principal = self.policy.principals.get(principal_id)
        if principal is None:
            return Decision(allowed=False, reasons=[f"unknown principal: {principal_id}"]), None
        if principal.role not in self.policy.roles:
            return Decision(allowed=False, reasons=[f"unknown role: {principal.role}"]), None
        return Decision(allowed=True), principal.role

    def authorize(self, principal_id: str, query: SemanticQuery) -> Decision:
        principal_decision, role_name = self.principal(principal_id)
        if not principal_decision.allowed or role_name is None:
            return principal_decision

        principal = self.policy.principals[principal_id]
        role = self.policy.roles[role_name]
        reasons: list[str] = []
        metric_name = self.resolve_metric(query.metric)
        metric = self.policy.metrics.get(metric_name)

        if metric is None:
            reasons.append(f"unknown metric: {query.metric}")
        elif metric_name not in role.allowed_metrics:
            reasons.append(f"metric not allowed for role {role_name}: {metric_name}")
        elif role_name not in metric.allowed_roles:
            reasons.append(f"metric policy excludes role {role_name}: {metric_name}")

        for dimension_name in query.dimensions:
            dimension = self.policy.dimensions.get(dimension_name)
            if dimension is None:
                reasons.append(f"unknown dimension: {dimension_name}")
                continue
            if dimension_name not in role.allowed_dimensions:
                reasons.append(f"dimension not allowed for role {role_name}: {dimension_name}")
            if role_name not in dimension.allowed_roles:
                reasons.append(f"dimension policy excludes role {role_name}: {dimension_name}")

        tenant_filter = query.filters.get("tenant_id")
        if tenant_filter is not None and str(tenant_filter) not in principal.tenant_ids:
            reasons.append(f"tenant filter outside principal scope: {tenant_filter}")

        if query.time_range not in role.allowed_time_ranges:
            reasons.append(f"time range not allowed: {query.time_range}")

        if query.limit > role.max_rows:
            reasons.append(f"limit {query.limit} exceeds max rows {role.max_rows}")

        estimated_cost = self.estimate_cost(query)
        if estimated_cost > role.max_cost:
            reasons.append(f"estimated cost {estimated_cost} exceeds max cost {role.max_cost}")

        return Decision(allowed=not reasons, reasons=reasons)

    def resolve_metric(self, metric_or_alias: str) -> str:
        if metric_or_alias in self.policy.metrics:
            return metric_or_alias
        for name, metric in self.policy.metrics.items():
            if metric_or_alias in metric.aliases:
                return name
        return metric_or_alias

    def estimate_cost(self, query: SemanticQuery) -> int:
        metric_name = self.resolve_metric(query.metric)
        metric = self.policy.metrics.get(metric_name)
        metric_cost = metric.cost if metric is not None else 100
        dimension_cost = 0
        for dim in query.dimensions:
            dimension = self.policy.dimensions.get(dim)
            dimension_cost += dimension.cost if dimension is not None else 20
        limit_cost = max(1, query.limit // 100)
        return metric_cost + dimension_cost + limit_cost

from __future__ import annotations

from policystrata.models import MutationSpec, WitnessClass

MUTATIONS: dict[str, MutationSpec] = {
    "stale_metric_alias_manifest": MutationSpec(
        id="stale_metric_alias_manifest",
        family="stale_metric_alias_manifest",
        affected_surface="manifest",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="A retired gross-revenue alias remains model-visible for an analyst role.",
    ),
    "grammar_permits_forbidden_dimension": MutationSpec(
        id="grammar_permits_forbidden_dimension",
        family="grammar_permits_forbidden_dimension",
        affected_surface="grammar",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="The grammar still permits a sensitive customer_email dimension.",
    ),
    "validator_omits_sensitive_column": MutationSpec(
        id="validator_omits_sensitive_column",
        family="validator_omits_sensitive_column",
        affected_surface="validator",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="The semantic validator omits the newly sensitive customer_email column.",
    ),
    "compiler_drops_tenant_predicate": MutationSpec(
        id="compiler_drops_tenant_predicate",
        family="compiler_drops_tenant_predicate",
        affected_surface="compiler",
        witness_class=WitnessClass.LOWERING_VIOLATION,
        description="The compiler drops the principal's tenant predicate.",
        containment_layer="database",
        requires_db_containment=True,
    ),
    "compiler_uses_old_tenant_key": MutationSpec(
        id="compiler_uses_old_tenant_key",
        family="compiler_uses_old_tenant_key",
        affected_surface="compiler",
        witness_class=WitnessClass.LOWERING_VIOLATION,
        description="The compiler emits a predicate against legacy_tenant_id instead of tenant_id.",
        containment_layer="database",
        requires_db_containment=True,
    ),
    "compiler_swaps_tenant_account_id": MutationSpec(
        id="compiler_swaps_tenant_account_id",
        family="compiler_swaps_tenant_account_id",
        affected_surface="compiler",
        witness_class=WitnessClass.LOWERING_VIOLATION,
        description="The compiler binds the tenant-scope obligation to account IDs instead of tenant IDs.",
        containment_layer="database",
        requires_db_containment=True,
    ),
    "db_rls_old_ownership_field": MutationSpec(
        id="db_rls_old_ownership_field",
        family="db_rls_old_ownership_field",
        affected_surface="database",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="The database RLS policy references an old ownership field.",
    ),
    "gross_net_metric_drift": MutationSpec(
        id="gross_net_metric_drift",
        family="gross_net_metric_drift",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="The compiler uses gross revenue for the net_revenue semantic metric.",
    ),
    "fanout_join_drift": MutationSpec(
        id="fanout_join_drift",
        family="fanout_join_drift",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="A join-path change double-counts invoice rows through ticket events.",
    ),
    "compiler_removes_distinct": MutationSpec(
        id="compiler_removes_distinct",
        family="compiler_removes_distinct",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="The compiler removes DISTINCT from an aggregate metric and double-counts entities.",
    ),
    "compiler_inner_join_drops_rows": MutationSpec(
        id="compiler_inner_join_drops_rows",
        family="compiler_inner_join_drops_rows",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="The compiler turns optional left joins into inner joins and drops valid rows.",
    ),
    "fiscal_calendar_mismatch": MutationSpec(
        id="fiscal_calendar_mismatch",
        family="fiscal_calendar_mismatch",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="The compiler uses calendar-month bounds for a fiscal-month query.",
    ),
    "cost_estimate_ignores_expansion": MutationSpec(
        id="cost_estimate_ignores_expansion",
        family="cost_estimate_ignores_expansion",
        affected_surface="compiler",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="The compiler cost estimator ignores a fan-out expansion.",
    ),
    "app_deny_missing_db_policy": MutationSpec(
        id="app_deny_missing_db_policy",
        family="app_deny_missing_db_policy",
        affected_surface="database",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="An application deny rule was not propagated into the database policy.",
    ),
}


def get_mutation(mutation_id: str) -> MutationSpec:
    try:
        return MUTATIONS[mutation_id]
    except KeyError as exc:
        raise ValueError(f"unknown mutation: {mutation_id}") from exc

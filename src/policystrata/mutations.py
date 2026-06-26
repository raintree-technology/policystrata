from __future__ import annotations

from policystrata.models import MutationSpec, WitnessClass

NO_MUTATION_ID = "none"
CLEAN_MUTATION = MutationSpec(
    id=NO_MUTATION_ID,
    family=NO_MUTATION_ID,
    affected_surface="release",
    witness_class=WitnessClass.CLEAN,
    description="No injected policy drift; clean-control request.",
)

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
    "clickhouse_row_policy_missing_project_filter": MutationSpec(
        id="clickhouse_row_policy_missing_project_filter",
        family="clickhouse_row_policy_missing_project_filter",
        affected_surface="database",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="A ClickHouse row policy omits the project-scope predicate for a read-only role.",
    ),
    "clickhouse_row_policy_readonly_assumption_violation": MutationSpec(
        id="clickhouse_row_policy_readonly_assumption_violation",
        family="clickhouse_row_policy_readonly_assumption_violation",
        affected_surface="database",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="A row-policy assumption is invalidated by a non-read-only execution context.",
    ),
    "aggregate_small_cohort_release": MutationSpec(
        id="aggregate_small_cohort_release",
        family="aggregate_small_cohort_release",
        affected_surface="release",
        witness_class=WitnessClass.UNSAFE_RELEASE,
        description=(
            "The release layer returns an aggregate whose cohort is below the configured k threshold."
        ),
    ),
    "materialized_view_lineage_drop": MutationSpec(
        id="materialized_view_lineage_drop",
        family="materialized_view_lineage_drop",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="A materialized-view rewrite drops source-table and release-class lineage.",
    ),
    "timezone_bucket_drift": MutationSpec(
        id="timezone_bucket_drift",
        family="timezone_bucket_drift",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="The compiler buckets events in UTC instead of the policy-declared project timezone.",
    ),
    "uniq_to_count_drift": MutationSpec(
        id="uniq_to_count_drift",
        family="uniq_to_count_drift",
        affected_surface="compiler",
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        description="The compiler lowers a unique-user metric to a raw event count.",
    ),
    "sample_clause_release_drift": MutationSpec(
        id="sample_clause_release_drift",
        family="sample_clause_release_drift",
        affected_surface="release",
        witness_class=WitnessClass.UNSAFE_RELEASE,
        description="A sampled aggregate is released without the required sampling disclosure and lineage.",
    ),
    "distributed_table_policy_gap": MutationSpec(
        id="distributed_table_policy_gap",
        family="distributed_table_policy_gap",
        affected_surface="database",
        witness_class=WitnessClass.OVER_PERMISSIVE,
        description="A distributed-table read bypasses a local-table row policy.",
    ),
}


def get_mutation(mutation_id: str) -> MutationSpec:
    if mutation_id == NO_MUTATION_ID:
        return CLEAN_MUTATION
    try:
        return MUTATIONS[mutation_id]
    except KeyError as exc:
        raise ValueError(f"unknown mutation: {mutation_id}") from exc

from __future__ import annotations

import random

from policystrata.models import (
    MetricPolicy,
    Policy,
    Principal,
    SemanticQuery,
    SurfaceVersions,
    Task,
    WitnessClass,
)
from policystrata.mutations import MUTATIONS, get_mutation

GENERATED_SUITE = "generated"
GENERATED_ALT_SEED_SUITE = "generated_alt_seed"
HELD_OUT_SUITE = "held_out"
HELDOUT_V1_SUITE = "heldout_v1"
CLEAN_CONTROLS_SUITE = "clean_controls"
NO_MUTATION_ID = "none"
DEFAULT_GENERATED_COUNT = 500
DEFAULT_GENERATED_ALT_SEED_COUNT = 50
DEFAULT_HELDOUT_V1_COUNT = 500
DEFAULT_CLEAN_CONTROL_COUNT = 80
DEFAULT_GENERATED_SEED = 1729
DEFAULT_GENERATED_ALT_SEED_SEED = 8675309
DEFAULT_HELDOUT_V1_SEED = 260626
DEFAULT_CLEAN_CONTROL_SEED = 260627
MAX_GENERATED_COUNT = 10_000
MAX_GENERATED_DIMENSIONS = 3
CLICKHOUSE_MUTATION_IDS = {
    "clickhouse_row_policy_missing_project_filter",
    "clickhouse_row_policy_readonly_assumption_violation",
    "aggregate_small_cohort_release",
    "materialized_view_lineage_drop",
    "timezone_bucket_drift",
    "uniq_to_count_drift",
    "sample_clause_release_drift",
    "distributed_table_policy_gap",
}


def generate_tasks(
    domain: str,
    policy: Policy,
    surface_versions: SurfaceVersions,
    count: int = DEFAULT_GENERATED_COUNT,
    seed: int = DEFAULT_GENERATED_SEED,
) -> list[Task]:
    count = validate_generated_count(count)
    rng = random.Random(seed)
    principal = select_restricted_principal(policy)
    mutations = mutation_ids_for_domain(domain)
    tasks: list[Task] = []

    for index in range(count):
        mutation_id = mutations[index % len(mutations)]
        mutation = get_mutation(mutation_id)
        query = query_for_mutation(policy, principal, mutation_id, rng)
        task_versions = surface_versions.model_copy(
            update={mutation.affected_surface: f"{surface_versions.as_dict()[mutation.affected_surface]}-gen"}
        )
        tasks.append(
            Task(
                id=f"{mutation_id}_generated_{index + 1:04d}",
                domain=domain,
                principal=principal.id,
                request=request_for_query(query, mutation_id, index + 1),
                policy_version=policy.version,
                surface_versions=task_versions,
                mutation=mutation_id,
                semantic_query=query,
                expected_witness_class=WitnessClass(mutation.witness_class),
                expected_localized_surface=mutation.affected_surface,
                expected_containment_layer=mutation.containment_layer,
            )
        )

    rng.shuffle(tasks)
    return tasks


def mutation_ids_for_domain(domain: str) -> list[str]:
    mutation_ids = list(MUTATIONS)
    if domain == "analytics_clickhouse":
        return mutation_ids
    return [mutation_id for mutation_id in mutation_ids if mutation_id not in CLICKHOUSE_MUTATION_IDS]


def generate_clean_control_tasks(
    domain: str,
    policy: Policy,
    surface_versions: SurfaceVersions,
    count: int = DEFAULT_CLEAN_CONTROL_COUNT,
    seed: int = DEFAULT_CLEAN_CONTROL_SEED,
) -> list[Task]:
    count = validate_generated_count(count)
    rng = random.Random(seed)
    principals = sorted(policy.principals.values(), key=lambda principal: principal.id)
    tasks: list[Task] = []

    for index in range(count):
        principal = principals[index % len(principals)]
        scenario = index % 4
        if scenario == 0:
            query = authorized_query(policy, principal, rng)
            request = request_for_query(query, NO_MUTATION_ID, index + 1)
        elif scenario == 1:
            query = denied_metric_query(policy, principal, rng)
            request = f"Clean control {index + 1}: denied metric should be rejected before release."
        elif scenario == 2:
            query = denied_dimension_query(policy, principal, rng)
            request = f"Clean control {index + 1}: denied dimension should be rejected before release."
        else:
            query = authorized_query(policy, principal, rng).model_copy(
                update={"limit": policy.roles[principal.role].max_rows}
            )
            request = f"Clean control {index + 1}: maximum allowed row budget remains clean."

        tasks.append(
            Task(
                id=f"clean_control_{index + 1:04d}",
                domain=domain,
                principal=principal.id,
                request=request,
                policy_version=policy.version,
                surface_versions=surface_versions,
                mutation=NO_MUTATION_ID,
                semantic_query=query,
                expected_witness_class=WitnessClass.CLEAN,
                expected_localized_surface="release",
            )
        )

    rng.shuffle(tasks)
    return tasks


def validate_generated_count(count: int) -> int:
    if not isinstance(count, int) or isinstance(count, bool):
        raise TypeError("generated count must be an integer")
    if count < 1 or count > MAX_GENERATED_COUNT:
        raise ValueError(f"generated count must be between 1 and {MAX_GENERATED_COUNT}: {count}")
    return count


def select_restricted_principal(policy: Policy) -> Principal:
    for principal in policy.principals.values():
        if "admin" not in principal.role:
            return principal
    return next(iter(policy.principals.values()))


def authorized_query(policy: Policy, principal: Principal, rng: random.Random) -> SemanticQuery:
    role = policy.roles[principal.role]
    allowed_dimensions = choose_allowed_dimensions(policy, principal.role, rng)
    return SemanticQuery(
        metric=choose_allowed_metric(policy, principal.role, rng),
        dimensions=allowed_dimensions[:1],
        time_range=choose_time_range(role.allowed_time_ranges, rng),
        limit=min(role.max_rows, 100),
    )


def denied_metric_query(policy: Policy, principal: Principal, rng: random.Random) -> SemanticQuery:
    role = policy.roles[principal.role]
    denied_metric = choose_denied_metric(policy, principal.role, rng)
    return SemanticQuery(
        metric=first_alias(denied_metric) or denied_metric.expression,
        dimensions=choose_allowed_dimensions(policy, principal.role, rng)[:1],
        time_range=choose_time_range(role.allowed_time_ranges, rng),
        limit=min(role.max_rows, 100),
    )


def denied_dimension_query(policy: Policy, principal: Principal, rng: random.Random) -> SemanticQuery:
    role = policy.roles[principal.role]
    return SemanticQuery(
        metric=choose_allowed_metric(policy, principal.role, rng),
        dimensions=[choose_sensitive_dimension(policy, principal.role, rng)],
        time_range=choose_time_range(role.allowed_time_ranges, rng),
        limit=min(role.max_rows, 100),
    )


def query_for_mutation(
    policy: Policy,
    principal: Principal,
    mutation_id: str,
    rng: random.Random,
) -> SemanticQuery:
    role = policy.roles[principal.role]
    allowed_metric = choose_allowed_metric(policy, principal.role, rng)
    denied_metric = choose_denied_metric(policy, principal.role, rng)
    sensitive_dimension = choose_sensitive_dimension(policy, principal.role, rng)
    allowed_dimensions = choose_allowed_dimensions(policy, principal.role, rng)
    time_range = choose_time_range(role.allowed_time_ranges, rng)
    fiscal_time_range = "last_fiscal_month" if "last_fiscal_month" in role.allowed_time_ranges else time_range

    if mutation_id == "stale_metric_alias_manifest":
        metric = first_alias(denied_metric) or denied_metric.expression
        return SemanticQuery(
            metric=metric,
            dimensions=allowed_dimensions[:1],
            time_range=time_range,
            limit=min(role.max_rows, 100),
        )
    if mutation_id in {"grammar_permits_forbidden_dimension", "validator_omits_sensitive_column"}:
        return SemanticQuery(
            metric=allowed_metric,
            dimensions=[sensitive_dimension],
            time_range=time_range,
            limit=min(role.max_rows, 100),
        )
    if mutation_id == "fiscal_calendar_mismatch":
        return SemanticQuery(
            metric=choose_semantic_metric(policy, principal.role, rng),
            dimensions=allowed_dimensions[:1],
            time_range=fiscal_time_range,
            limit=min(role.max_rows, 100),
        )
    if mutation_id == "cost_estimate_ignores_expansion":
        return SemanticQuery(
            metric=choose_semantic_metric(policy, principal.role, rng),
            dimensions=allowed_dimensions[:MAX_GENERATED_DIMENSIONS],
            time_range=time_range,
            limit=role.max_rows + 1,
        )
    if mutation_id == "app_deny_missing_db_policy":
        denied_alias = first_alias(denied_metric) or denied_metric.expression
        return SemanticQuery(
            metric=denied_alias,
            dimensions=allowed_dimensions[:1],
            time_range=time_range,
            limit=min(role.max_rows, 100),
        )

    return SemanticQuery(
        metric=choose_semantic_metric(policy, principal.role, rng),
        dimensions=allowed_dimensions[:1],
        time_range=time_range,
        limit=min(role.max_rows, 100),
    )


def choose_allowed_metric(policy: Policy, role_name: str, rng: random.Random) -> str:
    role = policy.roles[role_name]
    candidates = sorted(metric for metric in role.allowed_metrics if metric in policy.metrics)
    return rng.choice(candidates)


def choose_semantic_metric(policy: Policy, role_name: str, rng: random.Random) -> str:
    preferred = [
        "net_revenue",
        "net_deposits",
        "aum",
        "fee_revenue",
        "ticket_count",
        "escalated_tickets",
    ]
    role = policy.roles[role_name]
    for metric in preferred:
        if metric in role.allowed_metrics and metric in policy.metrics:
            return metric
    return choose_allowed_metric(policy, role_name, rng)


def choose_denied_metric(policy: Policy, role_name: str, rng: random.Random) -> MetricPolicy:
    role = policy.roles[role_name]
    candidates = [
        metric
        for name, metric in sorted(policy.metrics.items())
        if name not in role.allowed_metrics or role_name not in metric.allowed_roles
    ]
    if not candidates:
        return policy.metrics[choose_allowed_metric(policy, role_name, rng)]
    return rng.choice(candidates)


def choose_sensitive_dimension(policy: Policy, role_name: str, rng: random.Random) -> str:
    role = policy.roles[role_name]
    candidates = [
        name
        for name, dimension in sorted(policy.dimensions.items())
        if dimension.sensitive
        and (name not in role.allowed_dimensions or role_name not in dimension.allowed_roles)
    ]
    if candidates:
        return rng.choice(candidates)
    fallback = [name for name in sorted(policy.dimensions) if name not in role.allowed_dimensions]
    return rng.choice(fallback or sorted(policy.dimensions))


def choose_allowed_dimensions(policy: Policy, role_name: str, rng: random.Random) -> list[str]:
    role = policy.roles[role_name]
    candidates = [
        name
        for name, dimension in sorted(policy.dimensions.items())
        if name in role.allowed_dimensions
        and role_name in dimension.allowed_roles
        and not dimension.sensitive
    ]
    if len(candidates) <= MAX_GENERATED_DIMENSIONS:
        return candidates
    rng.shuffle(candidates)
    return candidates[:MAX_GENERATED_DIMENSIONS]


def choose_time_range(time_ranges: list[str], rng: random.Random) -> str:
    preferred = ["last_month", "last_fiscal_month", "quarter_to_date"]
    for time_range in preferred:
        if time_range in time_ranges:
            return time_range
    return rng.choice(time_ranges)


def first_alias(metric: MetricPolicy) -> str | None:
    return metric.aliases[0] if metric.aliases else None


def request_for_query(query: SemanticQuery, mutation_id: str, index: int) -> str:
    dimensions = ", ".join(query.dimensions) if query.dimensions else "total"
    return (
        f"Generated drift case {index}: show {query.metric} by {dimensions} "
        f"for {query.time_range} using operator {mutation_id}."
    )

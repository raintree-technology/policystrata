from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from policystrata.models import Trace, WitnessClass
from policystrata.summary import load_traces

BaselinePredicate = Callable[[Trace], bool]


def final_answer_only(trace: Trace) -> bool:
    return trace.semantic_difference and trace.release_decision.allowed


def grammar_only(trace: Trace) -> bool:
    return trace.localized_surface == "grammar"


def semantic_validator_only(trace: Trace) -> bool:
    return trace.localized_surface == "validator" or (
        not trace.canonical_decision.allowed and trace.witness_class != WitnessClass.CLEAN
    )


def sql_ast_policy_checker(trace: Trace) -> bool:
    return trace.localized_surface == "compiler" and (
        "tenant" in trace.compiled_sql or trace.semantic_difference
    )


def db_policy_only(trace: Trace) -> bool:
    return db_rls_only(trace)


def release_filter_only(trace: Trace) -> bool:
    return trace.localized_surface == "release" or not trace.release_decision.allowed


def lineage_only(trace: Trace) -> bool:
    has_lineage_obligation = any("lineage" in obligation for obligation in trace.transition_obligations)
    return has_lineage_obligation and trace.localized_surface in {"compiler", "release"}


def policy_as_code_precheck(trace: Trace) -> bool:
    return not trace.canonical_decision.allowed and trace.localized_surface in {
        "manifest",
        "grammar",
        "validator",
    }


def sql_snapshot(trace: Trace) -> bool:
    if trace.localized_surface != "compiler":
        return False
    return trace.mutation not in {"cost_estimate_ignores_expansion"}


def validator_only(trace: Trace) -> bool:
    return not trace.canonical_decision.allowed and trace.localized_surface != "validator"


def db_rls_only(trace: Trace) -> bool:
    return trace.containment_layer == "database" or (
        trace.localized_surface == "database" and bool(trace.db_result.get("blocked_by_database"))
    )


def random_data_generation(trace: Trace) -> bool:
    return trace.semantic_difference


def naive_surface_equality(trace: Trace) -> bool:
    canonical = trace.canonical_decision.allowed
    return any(decision.allowed != canonical for decision in trace.surface_decisions.values())


def defense_in_depth_stack(trace: Trace) -> bool:
    return (
        validator_only(trace)
        or sql_snapshot(trace)
        or db_rls_only(trace)
        or final_answer_only(trace)
    )


def defense_in_depth_stack_v2(trace: Trace) -> bool:
    return (
        grammar_only(trace)
        or semantic_validator_only(trace)
        or sql_ast_policy_checker(trace)
        or db_policy_only(trace)
        or release_filter_only(trace)
    )


# conventional_test_suite models the hand-written unit/integration test suite a
# competent engineer would derive from the policy contract documents alone,
# without access to the mutation operator list. Each check maps to a spec clause:
#
# 1. Tenant scope predicate present in compiled SQL.
#    Spec: surfaces.yaml validator responsibility "bind_principal_tenant_scope",
#    compiler responsibility "preserve_tenant_scope_predicates", database
#    responsibility "enforce_tenant_isolation_rls"; principals.tenant_ids in
#    domains/*/policy.yaml. The expected scope column per domain schema is
#    accounts.tenant_id, households.firm_id, events.project_id.
# 2. Denied metric rejected by the validator.
#    Spec: policy.yaml roles.<role>.allowed_metrics and metrics.<m>.allowed_roles;
#    surfaces.yaml validator responsibility
#    "authorize_metric_dimension_time_and_budget".
# 3. Denied dimension rejected by the validator.
#    Spec: policy.yaml roles.<role>.allowed_dimensions and
#    dimensions.<d>.allowed_roles; same validator responsibility as check 2.
# 4. Row limit enforced end to end.
#    Spec: policy.yaml roles.<role>.max_rows; surfaces.yaml compiler
#    responsibility "preserve_row_budget" and the "row_budget" transition
#    obligation. The compiled SQL must carry the requested limit and the
#    observed result must not exceed it.
# 5. Release blocked when the canonical policy denies.
#    Spec: surfaces.yaml release responsibilities "enforce_release_decision" and
#    "withhold_contained_or_unauthorized_results"; docs/methodology.md "What
#    PolicyStrata Can Observe" (canonical policy oracle over semantic IR).
# 6. Golden-value assertions for the headline seeded metrics.
#    Spec: the seeded fixtures define intended metric values per
#    docs/methodology.md "Suite Definitions" ("seeded" is a static public
#    suite); db_result.intended_value is that fixture golden value. A real
#    suite would pin a handful of released metric values, so the assertion is
#    limited to the headline metrics of each domain policy.

_TENANT_SCOPE_PREDICATES: dict[str, str] = {
    "support_saas": "accounts.tenant_id in (",
    "finance_saas": "households.firm_id in (",
    "analytics_clickhouse": "events.project_id in (",
}

_METRIC_DENIAL_PREFIXES: tuple[str, ...] = (
    "unknown metric:",
    "metric not allowed for role",
    "metric policy excludes role",
)

_DIMENSION_DENIAL_PREFIXES: tuple[str, ...] = (
    "unknown dimension:",
    "dimension not allowed for role",
    "dimension policy excludes role",
)

_GOLDEN_VALUE_METRICS: frozenset[str] = frozenset(
    {
        # support_saas headline metrics (bookings is the documented alias).
        "net_revenue",
        "bookings",
        "ticket_count",
        # finance_saas headline metrics.
        "aum",
        "net_deposits",
        # analytics_clickhouse headline metrics.
        "events",
        "active_users",
    }
)


def _canonical_denies_for(trace: Trace, prefixes: tuple[str, ...]) -> bool:
    if trace.canonical_decision.allowed:
        return False
    return any(reason.startswith(prefixes) for reason in trace.canonical_decision.reasons)


def _test_tenant_predicate_present(trace: Trace) -> bool:
    predicate = _TENANT_SCOPE_PREDICATES.get(trace.domain)
    return predicate is not None and predicate not in trace.compiled_sql


def _test_denied_metric_rejected(trace: Trace) -> bool:
    if not _canonical_denies_for(trace, _METRIC_DENIAL_PREFIXES):
        return False
    validator = trace.surface_decisions.get("validator")
    return validator is not None and validator.allowed


def _test_denied_dimension_rejected(trace: Trace) -> bool:
    if not _canonical_denies_for(trace, _DIMENSION_DENIAL_PREFIXES):
        return False
    validator = trace.surface_decisions.get("validator")
    return validator is not None and validator.allowed


def _test_row_limit_enforced(trace: Trace) -> bool:
    limit = trace.semantic_ir.limit
    if re.search(rf"\blimit {limit}\b", trace.compiled_sql) is None:
        return True
    rows = trace.db_result.get("rows")
    return isinstance(rows, int) and rows > limit


def _test_release_blocked_on_canonical_deny(trace: Trace) -> bool:
    return not trace.canonical_decision.allowed and trace.release_decision.allowed


def _test_golden_metric_values(trace: Trace) -> bool:
    if trace.semantic_ir.metric not in _GOLDEN_VALUE_METRICS:
        return False
    if not trace.release_decision.allowed:
        return False
    intended = trace.db_result.get("intended_value")
    actual = trace.db_result.get("actual_value")
    return intended is not None and actual is not None and bool(intended != actual)


def conventional_test_suite(trace: Trace) -> bool:
    return (
        _test_tenant_predicate_present(trace)
        or _test_denied_metric_rejected(trace)
        or _test_denied_dimension_rejected(trace)
        or _test_row_limit_enforced(trace)
        or _test_release_blocked_on_canonical_deny(trace)
        or _test_golden_metric_values(trace)
    )


_ADJACENT_SURFACES: tuple[tuple[str, str], ...] = (
    ("manifest", "grammar"),
    ("grammar", "validator"),
    ("validator", "compiler"),
    ("compiler", "database"),
    ("database", "release"),
)


def property_differential(trace: Trace) -> bool:
    """Cedar-style property-based differential check over surface decisions.

    Re-evaluates the canonical policy oracle decision against the observed
    surface decisions pairwise: flags any allow/deny disagreement between
    adjacent surfaces in pipeline order (manifest, grammar, validator,
    compiler, database, release), plus canonical versus the final release
    decision.

    Limitation: it only catches faults that show up as a pairwise decision
    disagreement. When every surface agrees on the same allow/deny outcome
    but the pipeline drifts semantically (wrong metric expression, wrong time
    window, or a dropped predicate with identical decisions), no pair
    disagrees and the fault is missed.
    """
    for left, right in _ADJACENT_SURFACES:
        left_decision = trace.surface_decisions.get(left)
        right_decision = trace.surface_decisions.get(right)
        if left_decision is None or right_decision is None:
            continue
        if left_decision.allowed != right_decision.allowed:
            return True
    return trace.canonical_decision.allowed != trace.release_decision.allowed


BASELINES: dict[str, BaselinePredicate] = {
    "grammar_only": grammar_only,
    "semantic_validator_only": semantic_validator_only,
    "sql_ast_policy_checker": sql_ast_policy_checker,
    "db_policy_only": db_policy_only,
    "release_filter_only": release_filter_only,
    "lineage_only": lineage_only,
    "policy_as_code_precheck": policy_as_code_precheck,
    "defense_in_depth_stack_v2": defense_in_depth_stack_v2,
    "final_answer_only": final_answer_only,
    "sql_snapshot": sql_snapshot,
    "validator_only": validator_only,
    "db_rls_only": db_rls_only,
    "random_data_generation": random_data_generation,
    "naive_surface_equality": naive_surface_equality,
    "defense_in_depth_stack": defense_in_depth_stack,
    "conventional_test_suite": conventional_test_suite,
    "property_differential": property_differential,
}


ABLATIONS: dict[str, BaselinePredicate] = {
    "without_lineage": lambda trace: trace.localized_surface != "release"
    and trace.mutation not in {"materialized_view_lineage_drop", "sample_clause_release_drift"},
    "without_policy_version": lambda trace: bool(trace.policy_version),
    "without_release_policy": lambda trace: trace.localized_surface != "release",
    "without_independent_oracle": lambda trace: trace.semantic_difference or trace.localized_surface in {
        "compiler",
        "database",
        "release",
    },
    "without_database_containment": lambda trace: trace.containment_layer != "database",
    "without_minimization": lambda trace: trace.witness_class != WitnessClass.CLEAN,
    "without_transition_obligations": lambda trace: trace.localized_surface in {
        "manifest",
        "grammar",
        "validator",
    },
}


def evaluate_baselines(traces: list[Trace]) -> dict[str, dict[str, int | float]]:
    return evaluate_predicates(traces, BASELINES)


def evaluate_ablations(traces: list[Trace]) -> dict[str, dict[str, int | float]]:
    return evaluate_predicates(traces, ABLATIONS)


def evaluate_predicates(
    traces: list[Trace],
    predicates: dict[str, BaselinePredicate],
) -> dict[str, dict[str, int | float]]:
    total_failures = sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN)
    results: dict[str, dict[str, int | float]] = {}
    for name, predicate in predicates.items():
        caught = sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN and predicate(trace))
        results[name] = {
            "caught": caught,
            "total_failures": total_failures,
            "missed": total_failures - caught,
            "catch_rate": caught / total_failures if total_failures else 0.0,
        }
    return results


def evaluate_false_positives(
    traces: list[Trace],
    predicates: dict[str, BaselinePredicate] | None = None,
) -> dict[str, dict[str, int | float]]:
    """False-positive rate of each predicate over clean traces.

    ``evaluate_predicates`` scores catch rate on non-clean traces only, so it
    never measures false positives. This counts, for each baseline, how many
    CLEAN traces it wrongly flags. Naive denial-flagging baselines fire on
    legitimately-denied clean controls; the responsibility-contract detector
    (never a predicate here) returns CLEAN on all of them by construction.
    """
    predicates = predicates if predicates is not None else BASELINES
    clean = [trace for trace in traces if trace.witness_class == WitnessClass.CLEAN]
    total_clean = len(clean)
    results: dict[str, dict[str, int | float]] = {}
    for name, predicate in predicates.items():
        false_positives = sum(1 for trace in clean if predicate(trace))
        results[name] = {
            "false_positives": false_positives,
            "total_clean": total_clean,
            "false_positive_rate": false_positives / total_clean if total_clean else 0.0,
        }
    return results


def evaluate_false_positive_runs(run_dirs: list[Path]) -> dict[str, dict[str, int | float]]:
    return evaluate_false_positives(load_many_traces(run_dirs))


def evaluate_baseline_run(run_dir: Path) -> dict[str, dict[str, int | float]]:
    return evaluate_baseline_runs([run_dir])


def evaluate_ablation_run(run_dir: Path) -> dict[str, dict[str, int | float]]:
    return evaluate_ablation_runs([run_dir])


def evaluate_baseline_runs(run_dirs: list[Path]) -> dict[str, dict[str, int | float]]:
    return evaluate_baselines(load_many_traces(run_dirs))


def evaluate_ablation_runs(run_dirs: list[Path]) -> dict[str, dict[str, int | float]]:
    return evaluate_ablations(load_many_traces(run_dirs))


def load_many_traces(run_dirs: list[Path]) -> list[Trace]:
    traces: list[Trace] = []
    for run_dir in run_dirs:
        traces.extend(load_traces(run_dir))
    return traces

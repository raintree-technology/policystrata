from __future__ import annotations

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

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from policystrata.models import Trace, WitnessClass
from policystrata.summary import load_traces

BaselinePredicate = Callable[[Trace], bool]


def final_answer_only(trace: Trace) -> bool:
    return trace.semantic_difference and trace.release_decision.allowed


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


BASELINES: dict[str, BaselinePredicate] = {
    "final_answer_only": final_answer_only,
    "sql_snapshot": sql_snapshot,
    "validator_only": validator_only,
    "db_rls_only": db_rls_only,
    "random_data_generation": random_data_generation,
    "naive_surface_equality": naive_surface_equality,
}


def evaluate_baselines(traces: list[Trace]) -> dict[str, dict[str, int | float]]:
    total_failures = sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN)
    results: dict[str, dict[str, int | float]] = {}
    for name, predicate in BASELINES.items():
        caught = sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN and predicate(trace))
        results[name] = {
            "caught": caught,
            "total_failures": total_failures,
            "missed": total_failures - caught,
            "catch_rate": caught / total_failures if total_failures else 0.0,
        }
    return results


def evaluate_baseline_run(run_dir: Path) -> dict[str, dict[str, int | float]]:
    return evaluate_baselines(load_traces(run_dir))

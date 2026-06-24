from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from policystrata.compiler import compile_query
from policystrata.detection import detect_witness
from policystrata.domain import load_policy, load_surface_config, load_tasks
from policystrata.minimize import minimize_trace
from policystrata.models import (
    SAFE_IDENTIFIER_PATTERN,
    Decision,
    Policy,
    SemanticQuery,
    SurfaceConfig,
    SurfaceName,
    Task,
    Trace,
    WitnessClass,
)
from policystrata.mutations import MUTATIONS, get_mutation
from policystrata.policy import PolicyOracle
from policystrata.summary import summarize_traces

SURFACES: tuple[SurfaceName, ...] = ("manifest", "grammar", "validator", "compiler", "database", "release")
INTENDED_METRIC_VALUES = {
    "ticket_count": 10,
    "tickets": 10,
    "escalated_tickets": 4,
    "escalations": 4,
    "net_revenue": 10000,
    "recognized_revenue": 10000,
    "gross_revenue": 12000,
    "bookings": 12000,
    "aum": 2500000,
    "assets": 2500000,
    "net_deposits": 125000,
    "flows": 125000,
    "gross_deposits": 190000,
    "inflows": 190000,
    "fee_revenue": 17500,
    "advisory_fees": 17500,
    "average_resolution_hours": 18,
}


def run_suite(
    domain: str,
    suite: str,
    out_dir: Path,
    base_path: Path | None = None,
    generated_count: int | None = None,
    generated_seed: int | None = None,
) -> list[Trace]:
    policy = load_policy(domain, base_path)
    surface_config = load_surface_config(domain, base_path)
    tasks = load_tasks(domain, suite, base_path, generated_count, generated_seed)
    traces = [evaluate_task(policy, task, surface_config) for task in tasks]

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    witness_dir = out_dir / "witnesses"
    witness_dir.mkdir(parents=True, exist_ok=True)

    traces_path = out_dir / "traces.jsonl"
    with traces_path.open("w", encoding="utf-8") as handle:
        for task, trace in zip(tasks, traces, strict=True):
            if trace.witness_class != WitnessClass.CLEAN:
                witness = minimize_trace(trace)
                witness_path = witness_file_path(witness_dir, task.id)
                witness_path.write_text(
                    json.dumps(witness, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                trace.witness_path = str(witness_path.relative_to(out_dir))
            handle.write(trace.model_dump_json() + "\n")

    summary = summarize_traces(traces)
    (out_dir / "summary.json").write_text(summary.model_dump_json(indent=2) + "\n", encoding="utf-8")
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "domain": domain,
                "suite": suite,
                "generated_count": generated_count,
                "generated_seed": generated_seed,
                "policy_version": policy.version,
                "default_surface_versions": surface_config.version_dict(),
                "surface_contracts": surface_config.contract_dict(),
                "transition_obligations": surface_config.transition_obligations,
                "mutation_operator_ids": list(MUTATIONS),
                "trace_count": len(traces),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return traces


def evaluate_task(policy: Policy, task: Task, surface_config: SurfaceConfig) -> Trace:
    started = time.perf_counter()
    mutation = get_mutation(task.mutation)
    oracle = PolicyOracle(policy)
    principal_decision, _role_name = oracle.principal(task.principal)
    if not principal_decision.allowed:
        reason = principal_decision.reasons[0] if principal_decision.reasons else task.principal
        raise ValueError(f"task {task.id} references invalid principal: {reason}")
    principal = policy.principals[task.principal]
    canonical = oracle.authorize(task.principal, task.semantic_query)
    compile_result = compile_query(policy, principal, task.semantic_query, mutation.family, task.domain)
    surface_decisions = evaluate_surfaces(task, canonical)
    db_result = simulate_db_result(task.semantic_query, mutation.family, canonical.allowed)
    containment_layer = mutation.containment_layer if mutation.requires_db_containment else None
    release_allowed = containment_layer is None
    release_decision = Decision(
        allowed=release_allowed,
        reasons=[] if release_allowed else [f"contained by {containment_layer}"],
    )
    semantic_difference = bool(db_result["intended_value"] != db_result["actual_value"])
    contract_decisions = evaluate_contracts(
        task,
        canonical,
        surface_decisions,
        compile_result.includes_tenant_predicate,
        semantic_difference,
    )
    detection = detect_witness(
        canonical=canonical,
        surface_decisions=surface_decisions,
        contract_decisions=contract_decisions,
        includes_tenant_predicate=compile_result.includes_tenant_predicate,
        semantic_difference=semantic_difference,
        release_decision=release_decision,
        db_result=db_result,
    )
    reasons = build_reasons(task, canonical, compile_result.includes_tenant_predicate, semantic_difference)
    latency_ms = (time.perf_counter() - started) * 1000

    return Trace(
        task_id=task.id,
        domain=task.domain,
        request=task.request,
        principal=task.principal,
        mutation=task.mutation,
        semantic_ir=task.semantic_query,
        policy_version=task.policy_version,
        surface_versions=task.surface_versions.as_dict(),
        canonical_decision=canonical,
        surface_decisions=surface_decisions,
        surface_contracts=surface_config.contracts,
        contract_decisions=contract_decisions,
        transition_obligations=surface_config.transition_obligations,
        compiled_sql=compile_result.sql,
        db_result=db_result,
        release_decision=release_decision,
        witness_class=detection.witness_class,
        expected_witness_class=task.expected_witness_class,
        localized_surface=detection.localized_surface,
        expected_localized_surface=task.expected_localized_surface,
        containment_layer=detection.containment_layer,
        expected_containment_layer=task.expected_containment_layer,
        semantic_difference=semantic_difference,
        latency_ms=latency_ms,
        cost={"estimated": compile_result.estimated_cost, "tokens": 0, "usd": 0.0},
        reasons=reasons,
    )


def witness_file_path(witness_dir: Path, task_id: str) -> Path:
    if re.fullmatch(SAFE_IDENTIFIER_PATTERN, task_id) is None:
        raise ValueError(f"unsafe task id for witness filename: {task_id}")
    root = witness_dir.resolve()
    candidate = (witness_dir / f"{task_id}.json").resolve()
    if candidate.parent != root:
        raise ValueError(f"unsafe task id for witness filename: {task_id}")
    return candidate


def evaluate_contracts(
    task: Task,
    canonical: Decision,
    surface_decisions: dict[str, Decision],
    includes_tenant_predicate: bool,
    semantic_difference: bool,
) -> dict[str, Decision]:
    mutation = get_mutation(task.mutation)
    decisions: dict[str, Decision] = {}

    for surface in SURFACES:
        if surface == mutation.affected_surface:
            surface_decision = surface_decisions[surface]
            reasons = [f"{surface} violated its declared responsibility: {mutation.description}"]
            if canonical.allowed and not surface_decision.allowed:
                reasons.append("authorized query was rejected by this layer")
            elif not canonical.allowed and surface_decision.allowed:
                reasons.append("unauthorized query was accepted by this layer")
            elif surface == "compiler" and not includes_tenant_predicate:
                reasons.append("tenant-scope obligation was not preserved during SQL lowering")
            elif surface == "compiler" and semantic_difference:
                reasons.append("semantic obligation was not preserved during SQL lowering")
            elif surface == "database":
                reasons.append("database obligation did not contain the observable policy drift")
            decisions[surface] = Decision(allowed=False, reasons=reasons)
            continue

        if surface == mutation.containment_layer and mutation.requires_db_containment:
            decisions[surface] = Decision(
                allowed=True,
                reasons=[f"{surface} contained a downstream obligation violation"],
            )
        else:
            decisions[surface] = Decision(allowed=True, reasons=[])

    return decisions


def evaluate_surfaces(task: Task, canonical: Decision) -> dict[str, Decision]:
    mutation = get_mutation(task.mutation)
    decisions: dict[str, Decision] = {}
    for surface in SURFACES:
        if surface == mutation.affected_surface:
            if mutation.witness_class == WitnessClass.OVER_RESTRICTIVE:
                decisions[surface] = Decision(allowed=False, reasons=[f"{surface} rejects authorized query"])
            else:
                decisions[surface] = Decision(
                    allowed=True,
                    reasons=[f"{surface} accepts due to {mutation.family}"],
                )
            continue

        if (
            mutation.witness_class == WitnessClass.OVER_PERMISSIVE
            and surface in upstream_surfaces(mutation.affected_surface)
        ):
            decisions[surface] = Decision(
                allowed=True,
                reasons=[f"{surface} exposes query before {mutation.affected_surface}"],
            )
        elif mutation.witness_class in {WitnessClass.LOWERING_VIOLATION, WitnessClass.SEMANTIC_DRIFT}:
            decisions[surface] = Decision(allowed=True, reasons=["authorized before mutated lowering"])
        else:
            decisions[surface] = canonical
    return decisions


def upstream_surfaces(surface: SurfaceName) -> set[SurfaceName]:
    ordered = list(SURFACES)
    index = ordered.index(surface)
    return set(ordered[:index])


def simulate_db_result(query: SemanticQuery, mutation: str, canonical_allowed: bool) -> dict[str, Any]:
    intended = intended_value(query)
    actual = intended
    blocked = False

    if mutation in {
        "compiler_drops_tenant_predicate",
        "compiler_uses_old_tenant_key",
        "compiler_swaps_tenant_account_id",
    }:
        actual = intended + 8
        blocked = True
    elif mutation == "gross_net_metric_drift":
        actual = 12000
    elif mutation == "fanout_join_drift":
        actual = intended * 2
    elif mutation == "compiler_removes_distinct":
        actual = intended + 3
    elif mutation == "compiler_inner_join_drops_rows":
        actual = max(0, intended - 2)
    elif mutation == "fiscal_calendar_mismatch":
        actual = max(0, intended - 1200)
    elif mutation == "db_rls_old_ownership_field":
        actual = intended + 6
    elif mutation == "app_deny_missing_db_policy":
        actual = 12000
    elif mutation == "cost_estimate_ignores_expansion":
        actual = intended if canonical_allowed else intended + 1

    return {
        "intended_value": intended,
        "actual_value": actual,
        "blocked_by_database": blocked,
        "rows": 0 if blocked else 1,
    }


def intended_value(query: SemanticQuery) -> int:
    return INTENDED_METRIC_VALUES.get(query.metric, 1)


def build_reasons(
    task: Task,
    canonical: Decision,
    includes_tenant_predicate: bool,
    semantic_difference: bool,
) -> list[str]:
    mutation = get_mutation(task.mutation)
    reasons = [mutation.description]
    if not canonical.allowed:
        reasons.extend(canonical.reasons)
    if not includes_tenant_predicate:
        reasons.append("compiled SQL does not include the canonical tenant predicate")
    if semantic_difference:
        reasons.append(
            "compiled behavior differs from canonical semantic intent on the generated database state"
        )
    return reasons

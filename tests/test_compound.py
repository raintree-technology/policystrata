from __future__ import annotations

import pytest

from policystrata.compound import (
    CompoundCase,
    evaluate_compound_case,
    generate_compound_cases,
    merge_contract_decisions,
    run_compound_study,
    summarize_compound,
)
from policystrata.domain import load_policy, load_surface_config
from policystrata.generator import mutation_ids_for_domain
from policystrata.models import (
    Decision,
    Policy,
    SemanticQuery,
    SurfaceConfig,
    Task,
    Trace,
    WitnessClass,
)
from policystrata.mutations import compound_expectations, get_mutation
from policystrata.runner import evaluate_task


def support_policy_and_surfaces() -> tuple[Policy, SurfaceConfig]:
    return load_policy("support_saas"), load_surface_config("support_saas")


def test_compound_expectations_uses_earliest_surface() -> None:
    specs = [
        get_mutation("db_rls_old_ownership_field"),
        get_mutation("stale_metric_alias_manifest"),
    ]
    expectation = compound_expectations(specs)
    assert expectation.localized_surface == "manifest"
    assert expectation.witness_class == get_mutation("stale_metric_alias_manifest").witness_class
    assert expectation.affected_surfaces == frozenset({"manifest", "database"})


def test_compound_expectations_drops_containment_when_layer_is_skewed() -> None:
    specs = [
        get_mutation("compiler_drops_tenant_predicate"),
        get_mutation("db_rls_old_ownership_field"),
    ]
    expectation = compound_expectations(specs)
    assert expectation.localized_surface == "compiler"
    assert expectation.containment_layer is None


def test_compound_expectations_keeps_containment_when_layer_clean() -> None:
    specs = [
        get_mutation("stale_metric_alias_manifest"),
        get_mutation("compiler_drops_tenant_predicate"),
    ]
    expectation = compound_expectations(specs)
    assert expectation.localized_surface == "manifest"
    assert expectation.containment_layer == "database"


def test_merge_contract_decisions_unions_violations() -> None:
    policy, surfaces = support_policy_and_surfaces()

    def sub(mutation_id: str) -> Trace:
        principal = next(p.id for p in policy.principals.values() if "admin" not in p.role)

        spec = get_mutation(mutation_id)
        task = Task(
            id=f"merge_{mutation_id}",
            domain="support_saas",
            principal=principal,
            request="merge test",
            policy_version=policy.version,
            surface_versions=surfaces.versions,
            mutation=mutation_id,
            semantic_query=SemanticQuery(metric="ticket_count"),
            expected_witness_class=WitnessClass(spec.witness_class),
            expected_localized_surface=spec.affected_surface,
            expected_containment_layer=spec.containment_layer,
        )
        return evaluate_task(policy, task, surfaces)

    traces = [sub("stale_metric_alias_manifest"), sub("db_rls_old_ownership_field")]
    merged = merge_contract_decisions(traces)
    assert merged["manifest"].allowed is False
    assert merged["database"].allowed is False
    assert merged["grammar"].allowed is True


def test_evaluate_compound_case_attributes_to_first_transition() -> None:
    policy, surfaces = support_policy_and_surfaces()
    case = CompoundCase(
        id="compound_case_1",
        domain="support_saas",
        principal=next(p.id for p in policy.principals.values() if "admin" not in p.role),
        request="manifest + database skew",
        policy_version=policy.version,
        surface_versions=surfaces.versions,
        mutations=["db_rls_old_ownership_field", "stale_metric_alias_manifest"],
        semantic_query=SemanticQuery(metric="ticket_count"),
    )
    result = evaluate_compound_case(policy, case, surfaces)
    assert result.detected is True
    assert result.observed_first_transition == "manifest"
    assert result.attribution_correct is True
    assert result.class_correct is True


def test_generate_compound_cases_uses_distinct_surfaces() -> None:
    policy, surfaces = support_policy_and_surfaces()
    cases = generate_compound_cases(
        "support_saas",
        policy,
        surfaces.versions,
        mutation_ids_for_domain("support_saas"),
        order=2,
        count=20,
    )
    assert len(cases) == 20
    for case in cases:
        surfaces_hit = {get_mutation(m).affected_surface for m in case.mutations}
        assert len(surfaces_hit) == len(case.mutations)


def test_generate_compound_cases_rejects_order_below_two() -> None:
    policy, surfaces = support_policy_and_surfaces()
    with pytest.raises(ValueError):
        generate_compound_cases(
            "support_saas",
            policy,
            surfaces.versions,
            mutation_ids_for_domain("support_saas"),
            order=1,
        )


def test_compound_case_requires_two_mutations() -> None:
    policy, surfaces = support_policy_and_surfaces()
    with pytest.raises(ValueError):
        CompoundCase(
            id="too_small",
            principal=next(iter(policy.principals)),
            request="one mutation",
            policy_version=policy.version,
            surface_versions=surfaces.versions,
            mutations=["stale_metric_alias_manifest"],
            semantic_query=SemanticQuery(metric="ticket_count"),
        )


def test_run_compound_study_full_domain_all_detected() -> None:
    report = run_compound_study("support_saas", orders=(2, 3), per_order=30)
    assert report.total == 60
    assert report.detection_rate == 1.0
    assert report.attribution_accuracy == 1.0


def test_summarize_compound_handles_empty() -> None:
    report = summarize_compound([])
    assert report.total == 0
    assert report.detection_rate == 0.0


def test_merge_prefers_violation_over_containment() -> None:
    violated = Decision(allowed=False, reasons=["database violated its declared responsibility"])
    contained = Decision(
        allowed=True, reasons=["database contained a downstream obligation violation"]
    )
    def trace_with(database_decision: Decision) -> Trace:
        return Trace(
            task_id="t",
            domain="support_saas",
            request="r",
            principal="p",
            mutation="m",
            semantic_ir=SemanticQuery(metric="ticket_count"),
            policy_version="v7",
            surface_versions={},
            canonical_decision=Decision(allowed=True),
            surface_decisions={},
            contract_decisions={"database": database_decision},
            compiled_sql="select 1",
            db_result={},
            release_decision=Decision(allowed=True),
            witness_class=WitnessClass.OVER_PERMISSIVE,
            expected_witness_class=WitnessClass.OVER_PERMISSIVE,
            localized_surface="database",
            expected_localized_surface="database",
        )

    merged = merge_contract_decisions([trace_with(contained), trace_with(violated)])
    assert merged["database"].allowed is False

from __future__ import annotations

import random

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from policystrata.domain import BUILTIN_DOMAINS, load_policy, load_surface_config, load_surfaces
from policystrata.generator import (
    mutation_ids_for_domain,
    query_for_mutation,
    select_restricted_principal,
)
from policystrata.models import Task, WitnessClass
from policystrata.mutations import get_mutation
from policystrata.runner import evaluate_task
from policystrata.soundness import (
    completeness_by_class,
    operator_contract_map,
    witness_implies_contract_violation,
)

_DOMAIN_CACHE: dict[str, tuple] = {}


def _domain(domain: str):
    if domain not in _DOMAIN_CACHE:
        _DOMAIN_CACHE[domain] = (
            load_policy(domain),
            load_surfaces(domain),
            load_surface_config(domain),
        )
    return _DOMAIN_CACHE[domain]


def _trace_for(domain: str, mutation_id: str, seed: int):
    policy, surfaces, surface_config = _domain(domain)
    principal = select_restricted_principal(policy)
    rng = random.Random(seed)
    query = query_for_mutation(policy, principal, mutation_id, rng)
    spec = get_mutation(mutation_id)
    task = Task(
        id=f"{mutation_id}_{seed}",
        domain=domain,
        principal=principal.id,
        request="soundness probe",
        policy_version=policy.version,
        surface_versions=surfaces,
        mutation=mutation_id,
        semantic_query=query,
        expected_witness_class=WitnessClass(spec.witness_class),
        expected_localized_surface=spec.affected_surface,
        expected_containment_layer=spec.containment_layer,
    )
    return evaluate_task(policy, task, surface_config)


@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    domain=st.sampled_from(BUILTIN_DOMAINS),
    seed=st.integers(min_value=0, max_value=10_000),
    data=st.data(),
)
def test_soundness_witness_implies_contract_violation(domain: str, seed: int, data) -> None:
    mutation_id = data.draw(st.sampled_from(mutation_ids_for_domain(domain)))
    trace = _trace_for(domain, mutation_id, seed)
    assert witness_implies_contract_violation(trace)


def test_soundness_exhaustive_over_taxonomy() -> None:
    # A finite exhaustive sweep over every operator x several seeds per domain.
    for domain in BUILTIN_DOMAINS:
        for mutation_id in mutation_ids_for_domain(domain):
            for seed in range(25):
                trace = _trace_for(domain, mutation_id, seed)
                assert witness_implies_contract_violation(trace)


def test_clean_controls_have_no_contract_violation() -> None:
    for domain in BUILTIN_DOMAINS:
        policy, surfaces, surface_config = _domain(domain)
        principal = select_restricted_principal(policy)
        from policystrata.models import SemanticQuery

        task = Task(
            id="clean_probe",
            domain=domain,
            principal=principal.id,
            request="clean",
            policy_version=policy.version,
            surface_versions=surfaces,
            mutation="none",
            semantic_query=SemanticQuery(metric=_first_allowed_metric(policy, principal.role)),
            expected_witness_class=WitnessClass.CLEAN,
            expected_localized_surface="release",
        )
        trace = evaluate_task(policy, task, surface_config)
        assert trace.witness_class == WitnessClass.CLEAN
        assert all(decision.allowed for decision in trace.contract_decisions.values())


def _first_allowed_metric(policy, role_name: str) -> str:
    role = policy.roles[role_name]
    for metric in sorted(role.allowed_metrics):
        if metric in policy.metrics:
            return metric
    return next(iter(policy.metrics))


def test_completeness_covers_all_operators() -> None:
    coverage = completeness_by_class()
    listed = {operator for entry in coverage for operator in entry.operators}
    contract_map = {entry.operator for entry in operator_contract_map()}
    # Every operator is characterized in both views, and they agree.
    assert listed == contract_map
    # Every non-clean witness class produced by the taxonomy is represented.
    classes = {entry.witness_class for entry in coverage}
    assert WitnessClass.CLEAN not in classes
    assert len(classes) >= 4

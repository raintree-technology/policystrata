import pytest

from policystrata.domain import load_policy, load_surface_config
from policystrata.generator import generate_tasks
from policystrata.mutations import MUTATIONS
from policystrata.runner import evaluate_task

INTENTIONAL_ASYMMETRIES = [
    ("app_deny_missing_db_policy", "manifest"),
    ("app_deny_missing_db_policy", "grammar"),
    ("app_deny_missing_db_policy", "validator"),
    ("app_deny_missing_db_policy", "compiler"),
    ("cost_estimate_ignores_expansion", "manifest"),
    ("cost_estimate_ignores_expansion", "grammar"),
    ("cost_estimate_ignores_expansion", "validator"),
    ("grammar_permits_forbidden_dimension", "manifest"),
    ("validator_omits_sensitive_column", "manifest"),
    ("validator_omits_sensitive_column", "grammar"),
]


@pytest.mark.parametrize(("mutation_id", "surface"), INTENTIONAL_ASYMMETRIES)
def test_intentional_surface_asymmetry_is_not_a_false_positive(
    mutation_id: str,
    surface: str,
) -> None:
    policy = load_policy()
    surface_config = load_surface_config()
    tasks = {
        task.mutation: task
        for task in generate_tasks(
            "support_saas",
            policy,
            surface_config.versions,
            count=len(MUTATIONS),
            seed=17,
        )
    }

    trace = evaluate_task(policy, tasks[mutation_id], surface_config)

    assert trace.surface_decisions[surface].allowed != trace.canonical_decision.allowed
    assert trace.contract_decisions[surface].allowed
    assert trace.localized_surface != surface
    assert not trace.contract_decisions[trace.localized_surface].allowed

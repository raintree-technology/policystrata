from policystrata.minimize import minimize_trace
from policystrata.runner import run_suite


def test_minimized_witness_preserves_violated_obligation(tmp_path) -> None:
    traces = run_suite("support_saas", "seeded", tmp_path / "run")
    trace = next(item for item in traces if item.mutation == "compiler_drops_tenant_predicate")

    witness = minimize_trace(trace)

    assert witness["task_id"] == trace.task_id
    assert witness["witness_class"] == trace.witness_class
    assert witness["localized_surface"] == trace.localized_surface
    assert witness["containment_layer"] == trace.containment_layer
    assert witness["semantic_ir"] == trace.semantic_ir.normalized()
    assert witness["contract_decisions"]["compiler"]["allowed"] is False
    assert "tenant-scope obligation" in " ".join(
        witness["contract_decisions"]["compiler"]["reasons"]
    )
    assert witness["release_allowed"] == trace.release_decision.allowed

import json

from policystrata.minimize import minimize_trace
from policystrata.runner import run_suite


def test_minimized_witness_preserves_violated_obligation(tmp_path) -> None:
    run_dir = tmp_path / "run"
    traces = run_suite("support_saas", "seeded", run_dir)
    trace = next(item for item in traces if item.mutation == "compiler_drops_tenant_predicate")

    witness_path = run_dir / (trace.witness_path or "")
    witness = json.loads(witness_path.read_text(encoding="utf-8"))

    assert witness["task_id"] == trace.task_id
    assert witness["witness_class"] == trace.witness_class
    assert witness["localized_surface"] == trace.localized_surface
    assert witness["containment_layer"] == trace.containment_layer
    assert witness["semantic_ir"]["dimensions"] == []
    assert witness["contract_decisions"]["compiler"]["allowed"] is False
    assert "tenant-scope obligation" in " ".join(
        witness["contract_decisions"]["compiler"]["reasons"]
    )
    assert witness["release_allowed"] == trace.release_decision.allowed


def test_minimized_witness_keeps_semantically_required_dimension(tmp_path) -> None:
    run_dir = tmp_path / "run"
    traces = run_suite("support_saas", "seeded", run_dir)
    trace = next(item for item in traces if item.mutation == "grammar_permits_forbidden_dimension")

    witness_path = run_dir / (trace.witness_path or "")
    witness = json.loads(witness_path.read_text(encoding="utf-8"))

    assert witness["semantic_ir"]["dimensions"] == ["customer_email"]
    assert witness["witness_class"] == trace.witness_class


def test_minimize_without_replay_returns_compact_projection(tmp_path) -> None:
    traces = run_suite("support_saas", "seeded", tmp_path / "run")
    trace = next(item for item in traces if item.mutation == "compiler_drops_tenant_predicate")

    witness = minimize_trace(trace)

    assert witness["semantic_ir"] == trace.semantic_ir.normalized()

from __future__ import annotations

from typing import Any

import pytest

from policystrata.writes import (
    WRITE_OPERATORS,
    WritePrincipal,
    WriteRequest,
    WriteTask,
    authorize_write,
    evaluate_write_task,
    generate_clean_write_controls,
    generate_write_tasks,
    get_write_operator,
    run_write_study,
    summarize_writes,
)


def _principal() -> WritePrincipal:
    return WritePrincipal(
        id="acme_writer",
        tenant_id="acme",
        writable_tables=["accounts", "subscriptions"],
        writable_columns=["plan", "status", "tenant_id"],
    )


def _task(operator: str, **request_kwargs: Any) -> WriteTask:
    request = WriteRequest(
        action=request_kwargs.pop("action", "update"),
        table=request_kwargs.pop("table", "accounts"),
        columns=request_kwargs.pop("columns", ["plan"]),
        tenant_scoped=request_kwargs.pop("tenant_scoped", True),
        tenant_id=request_kwargs.pop("tenant_id", "acme"),
    )
    return WriteTask(id=f"{operator}_t", principal=_principal(), request=request, operator=operator)


def test_every_operator_localizes_to_its_surface() -> None:
    for operator_id, operator in WRITE_OPERATORS.items():
        trace = evaluate_write_task(_task(operator_id))
        assert trace.witness_class != trace.witness_class.CLEAN
        assert trace.localized_surface == operator.affected_surface


def test_tenant_scope_drops_are_database_contained() -> None:
    contained = (
        "update_drops_tenant_predicate",
        "delete_missing_tenant_scope",
        "insert_forges_tenant_id",
    )
    for operator_id in contained:
        trace = evaluate_write_task(_task(operator_id))
        assert trace.containment_layer == "database"
        assert trace.committed is False


def test_containment_layer_failures_commit() -> None:
    for operator_id in ("db_write_policy_missing_with_check", "commit_releases_uncontained_write"):
        trace = evaluate_write_task(_task(operator_id))
        assert trace.containment_layer is None
        assert trace.committed is True


def test_clean_write_control_produces_no_witness() -> None:
    trace = evaluate_write_task(_task("none"))
    assert trace.witness_class == trace.witness_class.CLEAN
    assert trace.localized_surface is None
    assert all(decision.allowed for decision in trace.surface_contracts.values())


def test_authorize_write_flags_foreign_tenant_and_columns() -> None:
    principal = _principal()
    foreign = WriteRequest(action="update", table="accounts", columns=["plan"], tenant_id="beta")
    assert authorize_write(principal, foreign).allowed is False
    bad_column = WriteRequest(action="update", table="accounts", columns=["ssn"], tenant_id="acme")
    assert authorize_write(principal, bad_column).allowed is False
    unscoped = WriteRequest(
        action="delete", table="accounts", columns=[], tenant_scoped=False, tenant_id="acme"
    )
    assert authorize_write(principal, unscoped).allowed is False


def test_summary_zero_false_positives_full_localization() -> None:
    summary = run_write_study(per_operator=6, clean_count=40)
    assert summary.false_positives == 0
    assert summary.localization_accuracy == 1.0
    assert summary.killed == 6 * len(WRITE_OPERATORS)
    assert 0.0 < summary.containment_rate < 1.0


def test_generators_are_deterministic() -> None:
    a = [t.model_dump() for t in generate_write_tasks(seed=1)]
    b = [t.model_dump() for t in generate_write_tasks(seed=1)]
    assert a == b
    controls = summarize_writes([evaluate_write_task(t) for t in generate_clean_write_controls(10)])
    assert controls.false_positives == 0


def test_unknown_operator_rejected() -> None:
    with pytest.raises(ValueError):
        get_write_operator("no_such_write_operator")

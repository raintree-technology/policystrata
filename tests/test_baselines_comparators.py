from __future__ import annotations

from typing import Any

from policystrata.baselines import (
    BASELINES,
    conventional_test_suite,
    evaluate_predicates,
    property_differential,
)
from policystrata.models import Decision, SemanticQuery, Trace, WitnessClass

SURFACES = ["manifest", "grammar", "validator", "compiler", "database", "release"]

CLEAN_SUPPORT_SQL = (
    "select sum(invoices.net_amount_cents) as value, accounts.region as region "
    "from accounts left join subscriptions on subscriptions.account_id = accounts.id "
    "left join invoices on invoices.subscription_id = subscriptions.id "
    "where accounts.tenant_id in ('acme') "
    "and invoices.invoice_date >= date '2026-05-01' and invoices.invoice_date < date '2026-06-01' "
    "group by accounts.region limit 100"
)


def make_trace(**overrides: Any) -> Trace:
    base: dict[str, Any] = {
        "task_id": "comparator_case",
        "domain": "support_saas",
        "request": "Show net revenue by region for last month.",
        "principal": "acme_analyst",
        "mutation": "clean_control",
        "semantic_ir": SemanticQuery(metric="net_revenue", dimensions=["region"], limit=100),
        "policy_version": "v7",
        "surface_versions": dict.fromkeys(SURFACES, "v7"),
        "canonical_decision": Decision(allowed=True),
        "surface_decisions": {surface: Decision(allowed=True) for surface in SURFACES},
        "transition_obligations": [],
        "compiled_sql": CLEAN_SUPPORT_SQL,
        "db_result": {
            "intended_value": 8600,
            "actual_value": 8600,
            "blocked_by_database": False,
            "rows": 1,
        },
        "release_decision": Decision(allowed=True),
        "witness_class": WitnessClass.CLEAN,
        "expected_witness_class": WitnessClass.CLEAN,
        "localized_surface": "validator",
        "expected_localized_surface": "validator",
    }
    base.update(overrides)
    return Trace(**base)


def denied_decisions(*, denied_from: str, reason: str) -> dict[str, Decision]:
    decisions: dict[str, Decision] = {}
    denying = False
    for surface in SURFACES:
        if surface == denied_from:
            denying = True
        decisions[surface] = Decision(allowed=False, reasons=[reason]) if denying else Decision(allowed=True)
    return decisions


def test_new_baselines_are_registered() -> None:
    assert BASELINES["conventional_test_suite"] is conventional_test_suite
    assert BASELINES["property_differential"] is property_differential


def test_conventional_test_suite_passes_on_clean_trace() -> None:
    assert not conventional_test_suite(make_trace())


def test_conventional_test_suite_catches_dropped_tenant_predicate() -> None:
    trace = make_trace(
        mutation="compiler_drops_tenant_predicate",
        compiled_sql=CLEAN_SUPPORT_SQL.replace("accounts.tenant_id in ('acme') and ", ""),
        witness_class=WitnessClass.LOWERING_VIOLATION,
        expected_witness_class=WitnessClass.LOWERING_VIOLATION,
        localized_surface="compiler",
        expected_localized_surface="compiler",
    )

    assert conventional_test_suite(trace)


def test_conventional_test_suite_catches_denied_metric_accepted_by_validator() -> None:
    reason = "metric not allowed for role analyst: gross_revenue"
    surface_decisions = {surface: Decision(allowed=True) for surface in SURFACES}
    trace = make_trace(
        mutation="validator_skips_metric_authorization",
        semantic_ir=SemanticQuery(metric="gross_revenue", dimensions=["region"], limit=100),
        canonical_decision=Decision(allowed=False, reasons=[reason]),
        surface_decisions=surface_decisions,
        witness_class=WitnessClass.OVER_PERMISSIVE,
        expected_witness_class=WitnessClass.OVER_PERMISSIVE,
    )

    assert conventional_test_suite(trace)


def test_conventional_test_suite_catches_denied_dimension_accepted_by_validator() -> None:
    reason = "dimension not allowed for role analyst: account_owner_email"
    surface_decisions = {surface: Decision(allowed=True) for surface in SURFACES}
    trace = make_trace(
        mutation="validator_skips_dimension_authorization",
        semantic_ir=SemanticQuery(metric="net_revenue", dimensions=["account_owner_email"], limit=100),
        canonical_decision=Decision(allowed=False, reasons=[reason]),
        surface_decisions=surface_decisions,
        witness_class=WitnessClass.OVER_PERMISSIVE,
        expected_witness_class=WitnessClass.OVER_PERMISSIVE,
    )

    assert conventional_test_suite(trace)


def test_conventional_test_suite_catches_row_limit_overflow() -> None:
    trace = make_trace(
        mutation="database_ignores_row_budget",
        db_result={
            "intended_value": 8600,
            "actual_value": 8600,
            "blocked_by_database": False,
            "rows": 250,
        },
        semantic_ir=SemanticQuery(metric="net_revenue", dimensions=["region"], limit=100),
        witness_class=WitnessClass.OVER_PERMISSIVE,
        expected_witness_class=WitnessClass.OVER_PERMISSIVE,
        localized_surface="database",
        expected_localized_surface="database",
    )

    assert conventional_test_suite(trace)


def test_conventional_test_suite_catches_release_of_canonically_denied_query() -> None:
    reason = "limit 5000 exceeds max rows 1000"
    trace = make_trace(
        mutation="release_ignores_authorization",
        semantic_ir=SemanticQuery(metric="net_revenue", dimensions=["region"], limit=100),
        canonical_decision=Decision(allowed=False, reasons=[reason]),
        release_decision=Decision(allowed=True),
        witness_class=WitnessClass.UNSAFE_RELEASE,
        expected_witness_class=WitnessClass.UNSAFE_RELEASE,
        localized_surface="release",
        expected_localized_surface="release",
    )

    assert conventional_test_suite(trace)


def test_conventional_test_suite_catches_golden_value_drift() -> None:
    trace = make_trace(
        mutation="metric_expression_gross_for_net",
        db_result={
            "intended_value": 8600,
            "actual_value": 12000,
            "blocked_by_database": False,
            "rows": 1,
        },
        semantic_difference=True,
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        expected_witness_class=WitnessClass.SEMANTIC_DRIFT,
        localized_surface="compiler",
        expected_localized_surface="compiler",
    )

    assert conventional_test_suite(trace)


def test_conventional_test_suite_misses_over_restrictive_validator() -> None:
    # Canonical allows the query, the validator wrongly denies it, and nothing
    # is released. Every hand-written check passes, so the fault is missed.
    reason = "metric not allowed for role analyst: net_revenue"
    trace = make_trace(
        mutation="validator_over_restricts_metric",
        surface_decisions=denied_decisions(denied_from="validator", reason=reason),
        db_result={
            "intended_value": 8600,
            "actual_value": 0,
            "blocked_by_database": False,
            "rows": 0,
        },
        release_decision=Decision(allowed=False, reasons=[reason]),
        witness_class=WitnessClass.OVER_RESTRICTIVE,
        expected_witness_class=WitnessClass.OVER_RESTRICTIVE,
    )

    assert not conventional_test_suite(trace)


def test_property_differential_catches_adjacent_surface_disagreement() -> None:
    reason = "metric not allowed for role analyst: gross_revenue"
    surface_decisions = denied_decisions(denied_from="grammar", reason=reason)
    surface_decisions["manifest"] = Decision(
        allowed=True, reasons=["manifest accepts due to stale_metric_alias_manifest"]
    )
    trace = make_trace(
        mutation="stale_metric_alias_manifest",
        semantic_ir=SemanticQuery(metric="bookings", dimensions=["region"], limit=100),
        canonical_decision=Decision(allowed=False, reasons=[reason]),
        surface_decisions=surface_decisions,
        release_decision=Decision(allowed=False, reasons=[reason]),
        witness_class=WitnessClass.OVER_PERMISSIVE,
        expected_witness_class=WitnessClass.OVER_PERMISSIVE,
        localized_surface="manifest",
        expected_localized_surface="manifest",
    )

    assert property_differential(trace)


def test_property_differential_catches_canonical_release_disagreement() -> None:
    reason = "limit 5000 exceeds max rows 1000"
    trace = make_trace(
        mutation="release_ignores_authorization",
        canonical_decision=Decision(allowed=False, reasons=[reason]),
        release_decision=Decision(allowed=True),
        witness_class=WitnessClass.UNSAFE_RELEASE,
        expected_witness_class=WitnessClass.UNSAFE_RELEASE,
        localized_surface="release",
        expected_localized_surface="release",
    )

    assert property_differential(trace)


def test_property_differential_misses_semantic_drift_with_agreeing_decisions() -> None:
    # The documented limitation: every surface allows, canonical allows, and
    # the release ships a semantically wrong value. No pair disagrees.
    trace = make_trace(
        mutation="metric_expression_gross_for_net",
        db_result={
            "intended_value": 8600,
            "actual_value": 12000,
            "blocked_by_database": False,
            "rows": 1,
        },
        semantic_ir=SemanticQuery(metric="escalated_tickets", dimensions=["region"], limit=100),
        semantic_difference=True,
        witness_class=WitnessClass.SEMANTIC_DRIFT,
        expected_witness_class=WitnessClass.SEMANTIC_DRIFT,
        localized_surface="compiler",
        expected_localized_surface="compiler",
    )

    assert not property_differential(trace)


def test_property_differential_passes_on_clean_trace() -> None:
    assert not property_differential(make_trace())


def test_evaluate_predicates_reports_new_baselines() -> None:
    reason = "metric not allowed for role analyst: gross_revenue"
    caught = make_trace(
        mutation="release_ignores_authorization",
        canonical_decision=Decision(allowed=False, reasons=[reason]),
        release_decision=Decision(allowed=True),
        witness_class=WitnessClass.UNSAFE_RELEASE,
        expected_witness_class=WitnessClass.UNSAFE_RELEASE,
    )
    clean = make_trace()
    predicates = {
        "conventional_test_suite": BASELINES["conventional_test_suite"],
        "property_differential": BASELINES["property_differential"],
    }

    results = evaluate_predicates([caught, clean], predicates)

    assert results["conventional_test_suite"] == {
        "caught": 1,
        "total_failures": 1,
        "missed": 0,
        "catch_rate": 1.0,
    }
    assert results["property_differential"]["caught"] == 1

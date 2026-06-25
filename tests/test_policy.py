import pytest
from pydantic import ValidationError

from policystrata.domain import load_policy
from policystrata.models import SemanticQuery
from policystrata.policy import PolicyOracle


def test_policy_allows_authorized_metric_and_dimensions() -> None:
    policy = load_policy()
    oracle = PolicyOracle(policy)

    decision = oracle.authorize(
        "acme_analyst",
        SemanticQuery(
            metric="net_revenue",
            dimensions=["region", "plan"],
            time_range="last_month",
            limit=100,
        ),
    )

    assert decision.allowed


def test_policy_denies_gross_revenue_for_analyst_alias() -> None:
    policy = load_policy()
    oracle = PolicyOracle(policy)

    decision = oracle.authorize(
        "acme_analyst",
        SemanticQuery(metric="bookings", dimensions=["region"], time_range="last_month", limit=100),
    )

    assert not decision.allowed
    assert any("metric not allowed" in reason for reason in decision.reasons)


def test_policy_denies_sensitive_customer_email_dimension() -> None:
    policy = load_policy()
    oracle = PolicyOracle(policy)

    decision = oracle.authorize(
        "acme_analyst",
        SemanticQuery(
            metric="ticket_count",
            dimensions=["customer_email"],
            time_range="last_month",
            limit=100,
        ),
    )

    assert not decision.allowed
    assert any("dimension not allowed" in reason for reason in decision.reasons)


def test_policy_denies_query_over_budget() -> None:
    policy = load_policy()
    oracle = PolicyOracle(policy)

    decision = oracle.authorize(
        "acme_analyst",
        SemanticQuery(
            metric="net_revenue",
            dimensions=["region", "plan", "severity"],
            time_range="last_month",
            limit=5000,
        ),
    )

    assert not decision.allowed
    assert any("exceeds max rows" in reason for reason in decision.reasons)


@pytest.mark.parametrize("limit", [0, -1, True, "1"])
def test_semantic_query_rejects_invalid_limits(limit) -> None:
    with pytest.raises(ValidationError):
        SemanticQuery(
            metric="ticket_count",
            dimensions=["region"],
            time_range="last_month",
            limit=limit,
        )

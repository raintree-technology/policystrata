from pathlib import Path

from policystrata.integrations.dbt_semantic import compare_dbt_semantic_model


def test_dbt_semantic_adapter_matches_finance_policy_fixture() -> None:
    result = compare_dbt_semantic_model(
        "finance_saas",
        Path("examples/integrations/dbt_semantic/finance_saas/semantic_models.yml"),
    )

    assert result["matched_metrics"] == ["aum", "fee_revenue", "gross_deposits", "net_deposits"]
    assert result["missing_policy_metrics"] == []
    assert result["stale_dbt_metrics"] == []
    assert result["missing_policy_dimensions"] == []

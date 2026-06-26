from pathlib import Path

from policystrata.integrations.dbt_semantic import compare_dbt_semantic_model, dbt_semantic_has_warnings


def test_dbt_semantic_adapter_matches_finance_policy_fixture() -> None:
    result = compare_dbt_semantic_model(
        "finance_saas",
        Path("examples/integrations/dbt_semantic/finance_saas/semantic_models.yml"),
    )

    assert result["matched_metrics"] == ["aum", "fee_revenue", "gross_deposits", "net_deposits"]
    assert result["missing_policy_metrics"] == []
    assert result["stale_dbt_metrics"] == []
    assert result["missing_policy_dimensions"] == []


def test_dbt_semantic_adapter_classifies_warning_diagnostics(tmp_path) -> None:
    fixture = tmp_path / "semantic_models.yml"
    fixture.write_text(
        """
semantic_models:
  - name: support_metrics
    model: ref('fct_support_metrics')
    dimensions:
      - name: customer_email
        type: categorical
metrics: []
""".lstrip(),
        encoding="utf-8",
    )

    result = compare_dbt_semantic_model("support_saas", fixture)

    assert result["sensitive_metadata_missing"] == ["customer_email"]
    assert dbt_semantic_has_warnings(result)


def test_dbt_semantic_adapter_does_not_classify_lineage_info_as_warning() -> None:
    assert not dbt_semantic_has_warnings({"models_missing_lineage": ["support_metrics"]})

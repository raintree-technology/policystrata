import ast
from pathlib import Path

from policystrata.integrations.dbt_semantic import compare_dbt_semantic_model, dbt_semantic_has_warnings
from policystrata.scan_models import GateOutcome
from policystrata.scanner import run_scan


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


def test_snowflake_text_to_sql_fixture_runs_without_snowflake(tmp_path) -> None:
    result = run_scan(
        Path("examples/integrations/snowflake_text_to_sql/policystrata.yaml"),
        tmp_path / "snowflake",
    )

    assert result.gate.outcome == GateOutcome.PASS
    assert result.summary.evidence_exercised["imported_trace"] == 1


def test_dbt_semantic_adapter_stays_out_of_core_execution_modules() -> None:
    core_modules = [
        Path("src/policystrata/compiler.py"),
        Path("src/policystrata/database.py"),
        Path("src/policystrata/domain.py"),
        Path("src/policystrata/generator.py"),
        Path("src/policystrata/policy.py"),
        Path("src/policystrata/runner.py"),
        Path("src/policystrata/runtime.py"),
    ]

    for path in core_modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
        ]
        imported_modules = {
            alias.name
            for node in imports
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in imports
            if isinstance(node, ast.ImportFrom)
        }
        assert "policystrata.integrations.dbt_semantic" not in imported_modules, path

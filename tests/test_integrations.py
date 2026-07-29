import ast
from pathlib import Path

from policystrata.domain import load_policy
from policystrata.integrations.dbt_semantic import (
    compare_dbt_semantic_model,
    dbt_semantic_has_warnings,
    expression_matches_policy,
    inspect_dbt_semantic_model,
    load_dbt_semantic_inventory,
    resolvable_dimension_names,
)
from policystrata.scan_models import GateOutcome
from policystrata.scanner import run_scan

METRICFLOW_DOMAIN = Path("examples/brownfield/metricflow/domain")


def write_semantic_model(tmp_path: Path, body: str) -> Path:
    fixture = tmp_path / "semantic_models.yml"
    fixture.write_text(body.lstrip(), encoding="utf-8")
    return fixture


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


# Scanner gap 3 (docs/brownfield-results.md): a semantic layer declares a dimension under a local
# name but lets a query reach it through an entity join as `entity__dimension`, a name that never
# appears verbatim in the manifest. Flat name matching reported every such policy reference as
# missing. These pin the resolution rules and, importantly, their limits.


def test_dbt_semantic_adapter_resolves_entity_qualified_dimension_names(tmp_path) -> None:
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: bookings_source
    model: ref('fct_bookings')
    entities:
      - name: booking
        type: primary
    dimensions:
      - name: region
        type: categorical
metrics: []
""",
    )

    resolvable = resolvable_dimension_names(load_dbt_semantic_inventory(fixture))

    assert "region" in resolvable
    assert "booking__region" in resolvable
    # The entity is groupable on its own, and every metric exposes the aggregation-time dimension.
    assert "booking" in resolvable
    assert "metric_time" in resolvable


def test_dbt_semantic_adapter_resolves_entity_reached_through_another_entity(tmp_path) -> None:
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: lux_listing_mapping
    model: ref('dim_lux_listing_id_mapping')
    entities:
      - name: listing
        type: primary
      - name: lux_listing
        type: foreign
metrics: []
""",
    )

    resolvable = resolvable_dimension_names(load_dbt_semantic_inventory(fixture))

    assert {"listing", "lux_listing", "listing__lux_listing", "lux_listing__listing"} <= resolvable


def test_dbt_semantic_adapter_qualifies_dimensions_only_by_their_own_models_entities(
    tmp_path,
) -> None:
    """Qualification is per-model, not project-wide, or the resolvable set would accept anything."""
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: bookings_source
    model: ref('fct_bookings')
    entities:
      - name: booking
        type: primary
    dimensions:
      - name: region
        type: categorical
  - name: users_source
    model: ref('dim_users')
    entities:
      - name: user
        type: primary
metrics: []
""",
    )

    resolvable = resolvable_dimension_names(load_dbt_semantic_inventory(fixture))

    assert "booking__region" in resolvable
    # `region` belongs to the bookings model, so the users entity must not qualify it.
    assert "user__region" not in resolvable


def test_dbt_semantic_adapter_reports_missing_dimensions_against_resolvable_names(
    tmp_path,
) -> None:
    """Pins the wiring, not just the helper: a policy naming `booking__is_instant` is satisfied by
    a model that declares entity `booking` and dimension `is_instant`."""
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: bookings_source
    model: ref('fct_bookings')
    entities:
      - name: booking
        type: primary
    dimensions:
      - name: is_instant
        type: categorical
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("brownfield_metricflow", fixture, METRICFLOW_DOMAIN)

    assert "booking__is_instant" in result["matched_dimensions"]
    assert "booking__is_instant" not in result["missing_policy_dimensions"]


def test_dbt_semantic_adapter_judges_dimension_staleness_on_declared_names(tmp_path) -> None:
    """A declared dimension the policy names only in qualified form is matched, not stale."""
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: support_metrics
    model: ref('fct_support_metrics')
    entities:
      - name: ticket
        type: primary
    dimensions:
      - name: region
        type: categorical
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("support_saas", fixture)

    assert "region" in result["matched_dimensions"]
    assert result["stale_dbt_dimensions"] == []


# Scanner gap 4: `metrics | measures` treated every measure as individually governable, so private
# building-block measures were reported stale against a policy never meant to name them.


def test_dbt_semantic_adapter_reports_promoted_measure_without_policy_as_stale(tmp_path) -> None:
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: support_metrics
    model: ref('fct_support_metrics')
    measures:
      - name: abandoned_tickets
        agg: sum
        create_metric: true
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("support_saas", fixture)

    assert result["stale_dbt_metrics"] == ["abandoned_tickets"]


def test_dbt_semantic_adapter_does_not_report_private_measure_as_stale(tmp_path) -> None:
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: support_metrics
    model: ref('fct_support_metrics')
    measures:
      - name: abandoned_tickets
        agg: sum
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("support_saas", fixture)

    assert result["stale_dbt_metrics"] == []


def test_dbt_semantic_adapter_serves_policy_metric_backed_by_private_measure(tmp_path) -> None:
    """The pools are asymmetric on purpose: a private measure still answers a policy metric."""
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: support_metrics
    model: ref('fct_support_metrics')
    measures:
      - name: ticket_count
        agg: count_distinct
        expr: support_tickets.id
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("support_saas", fixture)

    assert "ticket_count" in result["matched_metrics"]
    assert "ticket_count" not in result["missing_policy_metrics"]
    assert result["stale_dbt_metrics"] == []


# Scanner gap 5: an omitted `expr:` is not an empty expression. dbt and MetricFlow default it to
# the measure's own name, and the adapter reported every such measure as a mismatch.


def test_dbt_semantic_adapter_resolves_omitted_expression_to_measure_name(tmp_path) -> None:
    """`account_balance` is the real upstream case: the measure omits `expr:` and the policy
    column is the measure's own name, so the implicit default matches."""
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: accounts_source
    model: ref('fct_accounts')
    measures:
      - name: account_balance
        agg: sum
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("brownfield_metricflow", fixture, METRICFLOW_DOMAIN)

    assert result["expression_mismatches"] == []


def test_dbt_semantic_adapter_still_reports_wrong_implicit_expression(tmp_path) -> None:
    """The fix resolves the default; it does not stop checking it."""
    fixture = write_semantic_model(
        tmp_path,
        """
semantic_models:
  - name: accounts_source
    model: ref('fct_accounts')
    measures:
      - name: account_balance
        agg: sum
        expr: booking_value
metrics: []
""",
    )

    result = inspect_dbt_semantic_model("brownfield_metricflow", fixture, METRICFLOW_DOMAIN)

    assert [mismatch["metric"] for mismatch in result["expression_mismatches"]] == ["account_balance"]


def test_dbt_semantic_adapter_never_matches_an_empty_expression() -> None:
    """An empty expression must not match, or dropping the implicit-default resolution would turn
    every omitted `expr:` into a check that silently passes."""
    metric = load_policy("support_saas").metrics["net_revenue"]

    assert not expression_matches_policy("", metric)
    assert not expression_matches_policy("   ", metric)


def test_dbt_semantic_adapter_reports_only_real_warnings_on_metricflow_manifest() -> None:
    """Real-input regression for gaps 3-5 against the checked-in upstream MetricFlow manifest.

    Before the fixes this emitted 27 adapter warnings, of which 23 were the adapter's own fault.
    The four that remain are findings the adapter should report: three measures declaring
    `create_metric: true` that the scoped policy does not cover, and one sensitive dimension the
    manifest does not mark.
    """
    result = inspect_dbt_semantic_model(
        "brownfield_metricflow",
        Path("examples/brownfield/metricflow/semantic_models.yml"),
        Path("examples/brownfield/metricflow/domain"),
    )

    assert result["missing_policy_dimensions"] == []
    assert result["expression_mismatches"] == []
    assert result["stale_dbt_metrics"] == [
        "archived_users",
        "new_users",
        "total_account_balance_first_day_of_month",
    ]
    assert result["sensitive_metadata_missing"] == ["company_name"]


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
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
        imported_modules = {
            alias.name for node in imports if isinstance(node, ast.Import) for alias in node.names
        } | {node.module or "" for node in imports if isinstance(node, ast.ImportFrom)}
        assert "policystrata.integrations.dbt_semantic" not in imported_modules, path

import pytest

from policystrata.domain import copy_domain, load_surface_config, load_tasks
from policystrata.generator import MAX_GENERATED_COUNT
from policystrata.models import MAX_SAFE_IDENTIFIER_LENGTH
from policystrata.mutations import MUTATIONS


def test_seeded_suite_expands_to_50_tasks() -> None:
    tasks = load_tasks("support_saas", "seeded")

    assert len(tasks) == 50
    assert {task.mutation for task in tasks}.issubset(set(MUTATIONS))


def test_tasks_have_expected_surface_versions() -> None:
    tasks = load_tasks("support_saas", "seeded")
    task = next(task for task in tasks if task.mutation == "compiler_drops_tenant_predicate")

    assert task.surface_versions.compiler == "v5"
    assert task.expected_witness_class == "lowering_violation"
    assert task.expected_containment_layer == "database"


def test_surface_contracts_describe_layer_responsibilities() -> None:
    config = load_surface_config("support_saas")

    assert config.versions.compiler == "v7"
    assert config.contracts["compiler"].mode == "sql_lowering"
    assert "authorize_metric_dimension_time_and_budget" in config.contracts["validator"].responsibilities
    assert "enforce_tenant_isolation_rls" in config.contracts["database"].responsibilities
    assert "authorize_metric_dimension_time_and_budget" not in config.contracts["database"].responsibilities
    assert "tenant_scope" in config.transition_obligations


def test_generated_suite_is_seeded_and_policy_driven() -> None:
    first = load_tasks("support_saas", "generated", generated_count=12, generated_seed=7)
    second = load_tasks("support_saas", "generated", generated_count=12, generated_seed=7)

    assert len(first) == 12
    assert [task.id for task in first] == [task.id for task in second]
    assert {task.mutation for task in first}.issubset(set(MUTATIONS))
    assert all(task.id.endswith(tuple(f"{index:04d}" for index in range(1, 13))) for task in first)


@pytest.mark.parametrize("count", [0, -1, MAX_GENERATED_COUNT + 1])
def test_generated_suite_rejects_out_of_range_count(count: int) -> None:
    with pytest.raises(ValueError, match="generated count must be between"):
        load_tasks("support_saas", "generated", generated_count=count, generated_seed=7)


@pytest.mark.parametrize("count", [True, "1"])
def test_generated_suite_rejects_non_integer_count(count) -> None:
    with pytest.raises(TypeError, match="generated count must be an integer"):
        load_tasks("support_saas", "generated", generated_count=count, generated_seed=7)


@pytest.mark.parametrize(
    "suite",
    ["../secret", "nested/suite", r"nested\\suite", "a" * (MAX_SAFE_IDENTIFIER_LENGTH + 1)],
)
def test_load_tasks_rejects_path_like_suite_names(tmp_path, suite: str) -> None:
    domain_path = copy_domain("support_saas", tmp_path)
    (tmp_path / "secret.yaml").write_text("suite: secret\ntasks: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsafe suite name"):
        load_tasks("support_saas", suite, base_path=domain_path)


@pytest.mark.parametrize("count", [0, -1, MAX_GENERATED_COUNT + 1])
def test_matrix_rejects_out_of_range_count(tmp_path, count: int) -> None:
    domain_path = copy_domain("support_saas", tmp_path)
    (domain_path / "tasks" / "adversarial.yaml").write_text(
        f"""
suite: adversarial
policy_version: v7
surface_versions:
  manifest: v7
  grammar: v7
  validator: v7
  compiler: v7
  database: v7
  release: v7
matrix:
  - mutation: stale_metric_alias_manifest
    count: {count}
    semantic_query:
      metric: bookings
      dimensions: [region]
      time_range: last_month
      grain: month
      limit: 100
    request: "Adversarial matrix count {{index}}."
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="matrix count must be between"):
        load_tasks("support_saas", "adversarial", base_path=domain_path)


@pytest.mark.parametrize("count", [True, "1"])
def test_matrix_rejects_non_integer_count(tmp_path, count) -> None:
    domain_path = copy_domain("support_saas", tmp_path)
    rendered_count = "true" if count is True else f'"{count}"'
    (domain_path / "tasks" / "adversarial.yaml").write_text(
        f"""
suite: adversarial
policy_version: v7
surface_versions:
  manifest: v7
  grammar: v7
  validator: v7
  compiler: v7
  database: v7
  release: v7
matrix:
  - mutation: stale_metric_alias_manifest
    count: {rendered_count}
    semantic_query:
      metric: bookings
      dimensions: [region]
      time_range: last_month
      grain: month
      limit: 100
    request: "Adversarial matrix count {{index}}."
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="matrix count must be an integer"):
        load_tasks("support_saas", "adversarial", base_path=domain_path)


def test_finance_saas_domain_loads_seeded_tasks_and_contracts() -> None:
    tasks = load_tasks("finance_saas", "seeded")
    config = load_surface_config("finance_saas")

    assert len(tasks) == 20
    assert tasks[0].domain == "finance_saas"
    assert config.contracts["validator"].mode == "semantic_validation"
    assert "bind_principal_firm_scope" in config.contracts["validator"].responsibilities

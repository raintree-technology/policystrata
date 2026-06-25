import json

import pytest
from pydantic import ValidationError

from policystrata.domain import copy_domain, load_policy, load_surface_config
from policystrata.models import MAX_SAFE_IDENTIFIER_LENGTH, SemanticQuery, Task, WitnessClass
from policystrata.runner import evaluate_task, run_suite, witness_file_path
from policystrata.summary import summarize_run


def test_run_suite_writes_traces_summary_and_witnesses(tmp_path) -> None:
    out_dir = tmp_path / "run"

    traces = run_suite("support_saas", "seeded", out_dir)
    summary = summarize_run(out_dir)

    assert len(traces) == 50
    assert (out_dir / "traces.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert summary.total == 50
    assert summary.mutant_kill_rate == 1.0
    assert summary.expected_class_accuracy == 1.0
    assert summary.localization_accuracy == 1.0
    assert summary.minimized_witness_count == 50

    lines = (out_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert first["semantic_ir"]["metric"] == "bookings"
    assert first["witness_path"].startswith("witnesses/")
    assert first["surface_contracts"]["compiler"]["mode"] == "sql_lowering"
    assert not first["contract_decisions"]["manifest"]["allowed"]
    assert "tenant_scope" in first["transition_obligations"]

    metadata = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["surface_contracts"]["validator"]["mode"] == "semantic_validation"
    assert metadata["evidence_level"] == "deterministic_fixture"
    assert metadata["suite_provenance"] == "hand_authored"
    assert metadata["detector_frozen"] is False
    assert "metric_semantics" in metadata["transition_obligations"]
    assert "compiler_drops_tenant_predicate" in metadata["mutation_operator_ids"]


def test_run_suite_handles_symlinked_output_directory(tmp_path) -> None:
    real_dir = tmp_path / "real"
    linked_dir = tmp_path / "linked"
    real_dir.mkdir()
    try:
        linked_dir.symlink_to(real_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    traces = run_suite("support_saas", "seeded", linked_dir)

    assert len(traces) == 50
    assert (linked_dir / "traces.jsonl").exists()
    assert (linked_dir / "summary.json").exists()
    assert all(trace.witness_path and trace.witness_path.startswith("witnesses/") for trace in traces)


def test_run_suite_rejects_path_like_task_ids(tmp_path) -> None:
    domain_path = copy_domain("support_saas", tmp_path)
    (domain_path / "tasks" / "adversarial.yaml").write_text(
        """
suite: adversarial
policy_version: v7
surface_versions:
  manifest: v7
  grammar: v7
  validator: v7
  compiler: v7
  database: v7
  release: v7
tasks:
  - id: ../../escaped_policystrata_witness
    principal: acme_analyst
    request: "Show bookings by region with an escaping task id."
    mutation: stale_metric_alias_manifest
    semantic_query:
      metric: bookings
      dimensions: [region]
      time_range: last_month
      grain: month
      limit: 100
    expected_witness_class: over_permissive
    expected_localized_surface: manifest
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        run_suite("support_saas", "adversarial", tmp_path / "run", domain_path)

    assert not (tmp_path / "run").exists()
    assert not (tmp_path / "escaped_policystrata_witness.json").exists()


@pytest.mark.parametrize("task_id", ["../../escaped", "nested/path", r"nested\\path"])
def test_witness_file_path_rejects_escape_attempts(tmp_path, task_id: str) -> None:
    with pytest.raises(ValueError, match="unsafe task id"):
        witness_file_path(tmp_path / "run" / "witnesses", task_id)


def test_task_id_rejects_overlong_filename() -> None:
    policy = load_policy()
    surface_config = load_surface_config()

    with pytest.raises(ValidationError):
        Task(
            id="a" * (MAX_SAFE_IDENTIFIER_LENGTH + 1),
            principal="acme_analyst",
            request="Overlong task id should be rejected.",
            policy_version=policy.version,
            surface_versions=surface_config.versions,
            mutation="stale_metric_alias_manifest",
            semantic_query=SemanticQuery(
                metric="ticket_count",
                dimensions=["region"],
                time_range="last_month",
                limit=100,
            ),
            expected_witness_class=WitnessClass.OVER_PERMISSIVE,
            expected_localized_surface="manifest",
        )


def test_evaluate_task_rejects_unknown_principal_with_clear_error() -> None:
    policy = load_policy()
    surface_config = load_surface_config()
    task = Task(
        id="unknown_principal",
        principal="mallory",
        request="Unknown principal should be rejected clearly.",
        policy_version=policy.version,
        surface_versions=surface_config.versions,
        mutation="stale_metric_alias_manifest",
        semantic_query=SemanticQuery(
            metric="ticket_count",
            dimensions=["region"],
            time_range="last_month",
            limit=100,
        ),
        expected_witness_class=WitnessClass.OVER_PERMISSIVE,
        expected_localized_surface="manifest",
    )

    with pytest.raises(ValueError, match="unknown principal: mallory"):
        evaluate_task(policy, task, surface_config)


def test_run_suite_detects_database_containment(tmp_path) -> None:
    traces = run_suite("support_saas", "seeded", tmp_path / "run")

    contained = [trace for trace in traces if trace.containment_layer == "database"]

    assert contained
    assert all(not trace.release_decision.allowed for trace in contained)


def test_generated_suite_writes_many_generated_mutants(tmp_path) -> None:
    traces = run_suite(
        "support_saas",
        "generated",
        tmp_path / "generated",
        generated_count=24,
        generated_seed=17,
    )

    assert len(traces) == 24
    assert {trace.witness_class for trace in traces}
    assert all(trace.witness_path for trace in traces)
    assert any(trace.mutation == "compiler_removes_distinct" for trace in traces)
    metadata = json.loads((tmp_path / "generated" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["evidence_level"] == "property_generated"
    assert metadata["suite_provenance"] == "generated"


def test_static_suite_can_declare_detector_frozen_blinded_metadata(tmp_path) -> None:
    domain_path = copy_domain("support_saas", tmp_path)
    (domain_path / "tasks" / "external_blinded.yaml").write_text(
        """
suite: external_blinded
suite_metadata:
  provenance: externally_authored
  evidence_level: blinded_suite
  detector_frozen: true
  detector_freeze_id: ps-freeze-2026-07-01
  authored_after_detector_freeze: true
  notes:
    - externally authored after detector freeze
policy_version: v7
surface_versions:
  manifest: v7
  grammar: v7
  validator: v7
  compiler: v7
  database: v7
  release: v7
tasks:
  - id: external_blinded_metric_alias
    principal: acme_analyst
    request: "External author requests bookings by region."
    mutation: stale_metric_alias_manifest
    semantic_query:
      metric: bookings
      dimensions: [region]
      time_range: last_month
      grain: month
      limit: 100
    expected_witness_class: over_permissive
    expected_localized_surface: manifest
""".lstrip(),
        encoding="utf-8",
    )

    run_suite("support_saas", "external_blinded", tmp_path / "run", domain_path)

    metadata = json.loads((tmp_path / "run" / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["evidence_level"] == "blinded_suite"
    assert metadata["suite_provenance"] == "externally_authored"
    assert metadata["detector_frozen"] is True
    assert metadata["detector_freeze_id"] == "ps-freeze-2026-07-01"


def test_generated_alt_seed_suite_preserves_held_out_compatibility(tmp_path) -> None:
    alt_seed_traces = run_suite("support_saas", "generated_alt_seed", tmp_path / "generated_alt_seed")
    held_out_traces = run_suite("support_saas", "held_out", tmp_path / "held_out")

    assert len(alt_seed_traces) == 50
    assert [trace.task_id for trace in alt_seed_traces] == [trace.task_id for trace in held_out_traces]


def test_finance_saas_seeded_suite_runs_with_finance_sql(tmp_path) -> None:
    traces = run_suite("finance_saas", "seeded", tmp_path / "finance")

    assert len(traces) == 20
    assert all(trace.domain == "finance_saas" for trace in traces)
    assert any("from households" in trace.compiled_sql for trace in traces)
    assert any("households.firm_id" in trace.compiled_sql for trace in traces)

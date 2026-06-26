import json

from policystrata.cli import main
from policystrata.domain import load_surface_config, load_tasks
from policystrata.runner import run_suite


def test_clickhouse_domain_seeded_suite_has_analytics_contracts() -> None:
    tasks = load_tasks("analytics_clickhouse", "seeded")
    config = load_surface_config("analytics_clickhouse")

    assert len(tasks) == 100
    assert tasks[0].domain == "analytics_clickhouse"
    assert "preserve_timezone_window_semantics" in config.contracts["compiler"].responsibilities
    assert "withhold_small_cohort_aggregates" in config.contracts["release"].responsibilities


def test_clickhouse_seeded_suite_runs_with_clickhouse_sql(tmp_path) -> None:
    traces = run_suite("analytics_clickhouse", "seeded", tmp_path / "analytics")

    assert len(traces) == 100
    assert all(trace.domain == "analytics_clickhouse" for trace in traces)
    assert all(trace.accounting_status == "killed" for trace in traces)
    assert any("from events" in trace.compiled_sql for trace in traces)
    assert any("events.project_id" in trace.compiled_sql for trace in traces)
    assert any(trace.localized_surface == "release" for trace in traces)


def test_clickhouse_generated_suite_supports_large_deterministic_counts(tmp_path) -> None:
    first = run_suite(
        "analytics_clickhouse",
        "generated",
        tmp_path / "first",
        generated_count=300,
        generated_seed=260626,
    )
    second = run_suite(
        "analytics_clickhouse",
        "generated",
        tmp_path / "second",
        generated_count=300,
        generated_seed=260626,
    )

    assert len(first) == 300
    assert [trace.task_id for trace in first] == [trace.task_id for trace in second]
    assert any(trace.mutation == "uniq_to_count_drift" for trace in first)
    assert any(trace.mutation == "aggregate_small_cohort_release" for trace in first)


def test_clean_controls_report_false_positive_accounting(tmp_path) -> None:
    run_dir = tmp_path / "clean"

    traces = run_suite("support_saas", "clean_controls", run_dir, generated_count=16, generated_seed=1)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert len(traces) == 16
    assert summary["clean_controls"] == 16
    assert summary["false_positives"] == 0
    assert summary["mutant_kill_rate"] == 0.0


def test_ablation_and_doctor_cli(tmp_path, capsys) -> None:
    run_dir = tmp_path / "analytics"
    ablations_path = tmp_path / "ablations.json"

    assert main(["run", "--domain", "analytics_clickhouse", "--suite", "seeded", "--out", str(run_dir)]) == 0
    capsys.readouterr()

    assert main(["ablations", str(run_dir), "--out", str(ablations_path)]) == 0
    capsys.readouterr()
    ablations = json.loads(ablations_path.read_text(encoding="utf-8"))
    assert "without_lineage" in ablations
    assert "without_release_policy" in ablations

    assert main(["doctor"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["requires_llm_api_key"] is False
    assert doctor["requires_host_psql"] is False

import json

import pytest

from policystrata.cli import main
from policystrata.domain import BUILTIN_DOMAINS, copy_domain, load_policy
from policystrata.init_scan import BASIC_SCAN_TEMPLATES


def test_cli_demo_runs_built_in_demo(tmp_path, capsys) -> None:
    out_dir = tmp_path / "demo"

    assert main(["demo", "--out", str(out_dir)]) == 0
    output = capsys.readouterr().out

    assert "PolicyStrata demo" in output
    assert "Loaded built-in domain: support_saas" in output
    assert "Ran 50 deterministic cases with no LLM API key" in output
    assert "Detected 50 policy-drift witnesses" in output
    assert "over_permissive=26" in output
    assert "lowering_violation=10" in output
    assert "semantic_drift=14" in output
    assert (out_dir / "traces.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert any((out_dir / "witnesses").glob("*.json"))


def test_cli_run_and_summarize(tmp_path, capsys) -> None:
    out_dir = tmp_path / "run"

    assert main(["run", "--domain", "support_saas", "--suite", "seeded", "--out", str(out_dir)]) == 0
    run_output = json.loads(capsys.readouterr().out)
    assert run_output["traces"] == 50

    assert main(["summarize", str(out_dir)]) == 0
    summary_output = json.loads(capsys.readouterr().out)
    assert summary_output["total"] == 50
    assert summary_output["mutant_kill_rate"] == 1.0


def test_cli_minimize(tmp_path, capsys) -> None:
    out_dir = tmp_path / "run"
    main(["run", "--domain", "support_saas", "--suite", "seeded", "--out", str(out_dir)])
    capsys.readouterr()
    witness = next((out_dir / "witnesses").glob("*.json"))

    assert main(["minimize", "--witness", str(witness)]) == 0
    minimized = json.loads(capsys.readouterr().out)
    assert "task_id" in minimized
    assert "compiled_sql" in minimized
    assert "surface_responsibilities" in minimized
    assert "contract_decisions" in minimized


def test_cli_generated_baselines_and_evidence(tmp_path, capsys) -> None:
    out_dir = tmp_path / "generated"

    assert (
        main(
            [
                "run",
                "--domain",
                "support_saas",
                "--suite",
                "generated",
                "--count",
                "16",
                "--seed",
                "9",
                "--out",
                str(out_dir),
            ]
        )
        == 0
    )
    run_output = json.loads(capsys.readouterr().out)
    assert run_output["traces"] == 16

    assert main(["baselines", str(out_dir)]) == 0
    baselines = json.loads(capsys.readouterr().out)
    assert "policystrata" not in baselines
    assert baselines["sql_snapshot"]["caught"] < 16

    evidence_path = tmp_path / "evidence.md"
    assert main(["evidence", f"generated={out_dir}", "--out", str(evidence_path)]) == 0
    capsys.readouterr()
    evidence = evidence_path.read_text(encoding="utf-8")
    assert "## Suite Results" in evidence
    assert "False positives" in evidence
    assert "| generated | 16 | 16 | 0 | 0 | 0 | 0 | 0 |" in evidence
    assert "| policystrata |" not in evidence


def test_cli_artifact_report_outputs_usability_metrics(tmp_path, capsys) -> None:
    out_dir = tmp_path / "run"

    assert main(["run", "--domain", "support_saas", "--suite", "seeded", "--out", str(out_dir)]) == 0
    capsys.readouterr()

    assert main(["artifact-report", str(out_dir)]) == 0
    markdown = capsys.readouterr().out
    assert "# PolicyStrata Artifact Report" in markdown
    assert "| Traces | 50 |" in markdown
    assert "| Minimized witnesses | 50 |" in markdown
    assert "| Requires LLM API key | no |" in markdown

    assert main(["artifact-report", str(out_dir), "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["traces"] == 50
    assert report["minimized_witnesses"] == 50
    assert report["requires_llm_api_key"] is False
    assert report["domain_fixture_lines"] > 0


def test_cli_export_adapters(tmp_path, capsys) -> None:
    out_dir = tmp_path / "run"
    inspect_path = tmp_path / "exports" / "inspect.jsonl"
    benchflow_path = tmp_path / "exports" / "benchflow.json"

    assert main(["run", "--domain", "support_saas", "--suite", "seeded", "--out", str(out_dir)]) == 0
    capsys.readouterr()

    assert main(["export", str(out_dir), "--format", "inspect", "--out", str(inspect_path)]) == 0
    inspect_output = json.loads(capsys.readouterr().out)
    assert inspect_output["records"] == 50
    inspect_record = json.loads(inspect_path.read_text(encoding="utf-8").splitlines()[0])
    assert inspect_record["metadata"]["adapter"] == "policystrata.inspect.v1"
    assert inspect_record["target"]["witness_class"] != "clean"

    assert main(["export", str(out_dir), "--format", "benchflow", "--out", str(benchflow_path)]) == 0
    benchflow_output = json.loads(capsys.readouterr().out)
    assert benchflow_output["records"] == 50
    benchflow = json.loads(benchflow_path.read_text(encoding="utf-8"))
    assert benchflow["version"] == "policystrata.benchflow.adapter.v1"
    assert benchflow["environment"]["requires_llm_api_key"] is False
    assert len(benchflow["tasks"]) == 50


def test_cli_rejects_negative_generated_count(tmp_path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run",
                "--domain",
                "support_saas",
                "--suite",
                "generated",
                "--count",
                "-1",
                "--out",
                str(tmp_path / "generated"),
            ]
        )

    assert exc_info.value.code == 2


def test_cli_rejects_path_like_suite_without_traceback(tmp_path, capsys) -> None:
    out_dir = tmp_path / "run"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run",
                "--domain",
                "support_saas",
                "--suite",
                "../secret",
                "--out",
                str(out_dir),
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "unsafe suite name" in captured.err
    assert "Traceback" not in captured.err
    assert not out_dir.exists()


def test_cli_rejects_invalid_external_task_without_partial_output(tmp_path, capsys) -> None:
    domain_path = copy_domain("support_saas", tmp_path)
    out_dir = tmp_path / "run"
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
  - id: ../../escaped
    principal: acme_analyst
    request: "Invalid task id should fail cleanly."
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

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run",
                "--domain",
                "support_saas",
                "--suite",
                "adversarial",
                "--domain-path",
                str(domain_path),
                "--out",
                str(out_dir),
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "id:" in captured.err
    assert "Traceback" not in captured.err
    assert not out_dir.exists()


def test_cli_check_dbt_semantic_integration(capsys) -> None:
    fixture = "examples/integrations/dbt_semantic/finance_saas/semantic_models.yml"

    assert main(["check-integration", "dbt-semantic", "--domain", "finance_saas", "--path", fixture]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["matched_metrics"] == ["aum", "fee_revenue", "gross_deposits", "net_deposits"]
    assert output["stale_dbt_metrics"] == []


def test_cli_check_integration_can_fail_on_warnings(tmp_path, capsys) -> None:
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

    assert (
        main(["check-integration", "dbt-semantic", "--domain", "support_saas", "--path", str(fixture)])
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["sensitive_metadata_missing"] == ["customer_email"]

    assert (
        main(
            [
                "check-integration",
                "dbt-semantic",
                "--domain",
                "support_saas",
                "--path",
                str(fixture),
                "--strict",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["sensitive_metadata_missing"] == ["customer_email"]


def test_cli_init_scan_creates_runnable_scaffold(tmp_path, capsys) -> None:
    scanner_dir = tmp_path / "scanner"

    assert main(["init-scan", "--out", str(scanner_dir)]) == 0
    scaffold = json.loads(capsys.readouterr().out)

    assert (scanner_dir / "policystrata.yaml").is_file()
    assert (scanner_dir / "domain" / "policy.yaml").is_file()
    assert (scanner_dir / "domain" / "surfaces.yaml").is_file()
    assert (scanner_dir / "traces.example.jsonl").is_file()
    assert "policystrata scan --config" in scaffold["command"]

    assert main(["scan", "--config", scaffold["files"]["config"], "--out", str(tmp_path / "scan")]) == 0
    scan = json.loads(capsys.readouterr().out)
    assert scan["gate"] == "pass"


@pytest.mark.parametrize("source_domain", BUILTIN_DOMAINS)
def test_cli_init_scan_creates_runnable_source_domain_scaffold(
    source_domain: str,
    tmp_path,
    capsys,
) -> None:
    scanner_dir = tmp_path / f"{source_domain}-scanner"

    assert main(["init-scan", "--source-domain", source_domain, "--out", str(scanner_dir)]) == 0
    scaffold = json.loads(capsys.readouterr().out)

    template = BASIC_SCAN_TEMPLATES[source_domain]
    policy = load_policy(source_domain, scanner_dir / "domain")
    config = (scanner_dir / "policystrata.yaml").read_text(encoding="utf-8")
    trace = json.loads((scanner_dir / "traces.example.jsonl").read_text(encoding="utf-8"))
    assert f"domain: {source_domain}" in config
    assert template.tenant_column in config
    assert template.tenant_column in trace["sql"]
    assert trace["principal"] in policy.principals
    assert trace["tenant_ids"] == policy.principals[trace["principal"]].tenant_ids
    assert trace["semantic_ir"]["metric"] in policy.metrics
    assert set(trace["semantic_ir"]["dimensions"]).issubset(policy.dimensions)

    assert main(["scan", "--config", scaffold["files"]["config"], "--out", str(tmp_path / "scan")]) == 0
    scan = json.loads(capsys.readouterr().out)
    assert scan["gate"] == "pass"


def test_cli_init_scan_copies_packaged_postgres_dbt_example(tmp_path, capsys) -> None:
    scanner_dir = tmp_path / "policystrata-example"

    assert main(["init-scan", "postgres_dbt", "--out", str(scanner_dir)]) == 0
    scaffold = json.loads(capsys.readouterr().out)

    assert scaffold["example"] == "postgres_dbt"
    assert (scanner_dir / "policystrata.yaml").is_file()
    assert (scanner_dir / "policystrata_clean.yaml").is_file()
    assert (scanner_dir / "policystrata_real_db_clean.yaml").is_file()
    assert (scanner_dir / "domain" / "schema.sql").is_file()
    assert (scanner_dir / "domain" / "seed.sql").is_file()

    assert main(["scan", "--config", scaffold["files"]["clean_config"], "--out", str(tmp_path / "scan")]) == 0
    clean = json.loads(capsys.readouterr().out)
    assert clean["gate"] == "pass"


def test_cli_scan_help_documents_examples_and_config_sections(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["scan", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "policystrata init-scan postgres_dbt --out policystrata-example" in output
    assert "Accepted config sections" in output
    assert "dbt, sql_traces" in output


def test_cli_scan_uses_gate_exit_codes(tmp_path, capsys) -> None:
    failed_out = tmp_path / "failed"
    clean_out = tmp_path / "clean"

    assert (
        main(["scan", "--config", "examples/postgres_dbt/policystrata.yaml", "--out", str(failed_out)])
        == 1
    )
    failed = json.loads(capsys.readouterr().out)
    assert failed["gate"] == "fail"
    assert failed["findings"] >= 1

    assert (
        main(["scan", "--config", "examples/postgres_dbt/policystrata_clean.yaml", "--out", str(clean_out)])
        == 0
    )
    clean = json.loads(capsys.readouterr().out)
    assert clean["gate"] == "pass"
    assert clean["findings"] == 0

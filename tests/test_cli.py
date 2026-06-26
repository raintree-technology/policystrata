import json
import re
from pathlib import Path

import pytest

from policystrata import __version__
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


def test_docs_github_action_examples_use_current_release_tag() -> None:
    docs = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in ("README.md", "docs/github-action.md")
    )

    action_refs = re.findall(r"raintree-technology/policystrata@v[0-9.]+", docs)
    assert action_refs
    assert set(action_refs) == {f"raintree-technology/policystrata@v{__version__}"}


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
    assert scaffold["commands"]["clean_smoke_scan"].endswith("policystrata_clean.yaml")
    assert (
        scaffold["commands"]["db_readiness_doctor"].endswith(
            "policystrata_real_db_clean.yaml --strict"
        )
    )
    assert "doctor audits only the selected config" in scaffold["notes"][0]

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


def test_cli_doctor_config_reports_wired_and_missing_stack(capsys) -> None:
    assert main(["doctor", "--config", "examples/postgres_dbt/policystrata.yaml"]) == 0
    doctor = json.loads(capsys.readouterr().out)

    stack = {item["id"]: item for item in doctor["stack"]}
    assert doctor["version"] == "doctor.v1"
    assert doctor["environment"]["requires_llm_api_key"] is False
    assert stack["dbt_semantic_adapter"]["status"] == "wired"
    assert stack["app_sql_traces"]["status"] == "wired"
    assert stack["database_fixture"]["status"] == "missing"
    assert stack["release_layer_tests"]["status"] == "wired"
    assert doctor["coverage_accounting"]["sql_trace_records"] >= 1
    assert any(todo["id"] == "fix_database_fixture" for todo in doctor["remediation"])


def test_cli_doctor_environment_markdown_without_config(capsys) -> None:
    assert main(["doctor", "--format", "markdown"]) == 0
    markdown = capsys.readouterr().out

    assert markdown.startswith("# PolicyStrata Doctor")
    assert "Mode: `environment`" in markdown
    assert "| Requires LLM API key | no |" in markdown
    assert "| Requires host psql | no |" in markdown
    assert not markdown.lstrip().startswith("{")


def test_cli_doctor_real_db_config_introspects_schema_and_writes_markdown(tmp_path, capsys) -> None:
    report_path = tmp_path / "doctor.md"

    assert (
        main(
            [
                "doctor",
                "--config",
                "examples/postgres_dbt/policystrata_real_db_clean.yaml",
                "--format",
                "markdown",
                "--out",
                str(report_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["out"] == str(report_path)
    markdown = report_path.read_text(encoding="utf-8")
    assert "# PolicyStrata Doctor" in markdown
    assert "PostgreSQL fixture" in markdown

    assert main(["doctor", "--config", "examples/postgres_dbt/policystrata_real_db_clean.yaml"]) == 0
    doctor = json.loads(capsys.readouterr().out)
    schema = doctor["database_introspection"]
    stack = {item["id"]: item for item in doctor["stack"]}
    assert "accounts" in schema["tables"]
    assert "accounts" in schema["rls_tables"]
    assert "accounts.customer_email" in schema["sensitive_columns"]
    assert stack["database_fixture"]["status"] == "wired"
    assert stack["rls_policies"]["status"] == "wired"
    assert stack["state_assertions"]["status"] == "wired"


def test_cli_doctor_policy_docs_classify_privacy_tos_and_obligations(tmp_path, capsys) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "privacy.md").write_text(
        """
# Privacy Policy

We collect only personal data limited to what is necessary. We use your information to
provide the service. This privacy notice explains consent and privacy rights, including
how to access your data, correct your data, and delete your data. We retain and delete
personal information according to a retention schedule. We share data with third party
service providers. Sensitive personal data such as customer_email is protected by
safeguards and access control.
""".lstrip(),
        encoding="utf-8",
    )
    (docs_dir / "terms.md").write_text(
        """
# Terms of Service

These service terms describe acceptable use and authorized users for customer data.
""".lstrip(),
        encoding="utf-8",
    )
    (docs_dir / "data-processing.md").write_text(
        """
# Data Processing Agreement

The customer is controller, PolicyStrata is processor, and subprocessors are reviewed
under security controls and encryption requirements.
""".lstrip(),
        encoding="utf-8",
    )
    (docs_dir / "internal-policy.md").write_text(
        """
# Internal Policy

Employee access uses role-based access and least privilege for tenant account data.
""".lstrip(),
        encoding="utf-8",
    )
    config_path = tmp_path / "policystrata.yaml"
    config_path.write_text(
        """
version: 1
domain: support_saas
policy_docs:
  files:
    - docs/privacy.md
    - docs/terms.md
    - docs/data-processing.md
    - docs/internal-policy.md
fuzz:
  enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["doctor", "--config", str(config_path)]) == 0
    doctor = json.loads(capsys.readouterr().out)

    policy_docs = doctor["policy_documents"]
    stack = {item["id"]: item for item in doctor["stack"]}
    assert policy_docs["status"] == "wired"
    assert policy_docs["missing_required_types"] == []
    assert policy_docs["missing_expected_obligations"] == []
    assert set(policy_docs["detected_types"]) >= {
        "privacy_policy",
        "terms_of_service",
        "data_processing_agreement",
        "internal_policy",
    }
    assert set(policy_docs["detected_obligations"]) >= {
        "personal_data_minimization",
        "purpose_limited_processing",
        "notice_or_consent",
        "retention_and_deletion",
        "third_party_sharing",
        "security_controls",
        "sensitive_data_controls",
    }
    assert "accounts.customer_email" in policy_docs["referenced_sensitive_columns"]
    assert stack["policy_docs_ingestion"]["status"] == "wired"


def test_cli_doctor_prompt_manifest_compares_exposed_policy_surface(tmp_path, capsys) -> None:
    manifest_path = tmp_path / "prompts.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "searchTickets",
                        "exposed_metrics": ["ticket_count", "retired_metric"],
                        "dimensions": ["region", "private_field"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "policystrata.yaml"
    config_path.write_text(
        """
version: 1
domain: support_saas
prompt_manifests:
  files:
    - prompts.json
fuzz:
  enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    assert main(["doctor", "--config", str(config_path)]) == 0
    doctor = json.loads(capsys.readouterr().out)
    stack = {item["id"]: item for item in doctor["stack"]}
    coverage = doctor["coverage_accounting"]

    assert stack["prompt_manifest_checks"]["status"] == "partial"
    assert "retired_metric" in coverage["prompt_manifest_unauthorized_metrics"]
    assert "private_field" in coverage["prompt_manifest_unauthorized_dimensions"]

    assert main(["doctor", "--config", str(config_path), "--strict"]) == 1
    capsys.readouterr()

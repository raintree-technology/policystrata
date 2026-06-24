import json

import pytest

from policystrata.cli import main
from policystrata.domain import copy_domain


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
    assert "Equivalent declared" in evidence
    assert "| generated | 16 | 16 | 0 | 0 |" in evidence
    assert "| policystrata |" not in evidence


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

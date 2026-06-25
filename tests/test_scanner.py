import json
from pathlib import Path

import psycopg
import pytest

from policystrata.database import assert_read_only_sql
from policystrata.domain import load_policy
from policystrata.integrations.dbt_semantic import inspect_dbt_semantic_model
from policystrata.models import SemanticQuery
from policystrata.scan_models import GateOutcome, MutantStatus
from policystrata.scanner import load_scan_config, run_scan, scan_imported_trace, start_docker_fixture
from policystrata.trace_import import (
    fuzz_imported_trace,
    load_imported_traces,
    resolve_scan_input_paths,
)


def test_scan_config_loads_stable_sections() -> None:
    config = load_scan_config(Path("examples/postgres_dbt/policystrata.yaml"))

    assert config.version == 1
    assert config.domain == "support_saas"
    assert config.sql_traces.required
    assert config.database.mode == "postgres"
    assert config.gate.fail_on_high_confidence


def test_scan_failing_fixture_writes_gate_outputs(tmp_path) -> None:
    result = run_scan(Path("examples/postgres_dbt/policystrata.yaml"), tmp_path / "scan")

    assert result.gate.outcome == GateOutcome.FAIL
    assert result.summary.high_confidence_failures >= 2
    assert (tmp_path / "scan" / "scan.json").is_file()
    assert (tmp_path / "scan" / "findings.jsonl").is_file()
    assert (tmp_path / "scan" / "summary.json").is_file()
    assert (tmp_path / "scan" / "report.md").is_file()
    assert any(item.witness_path for item in result.findings)
    assert any(item.id.startswith("unsafe_release") for item in result.findings)
    assert any(item.id.startswith("tenant_scope_missing") for item in result.findings)

    scan_json = json.loads((tmp_path / "scan" / "scan.json").read_text(encoding="utf-8"))
    assert scan_json["gate"]["outcome"] == "fail"


def test_scan_clean_fixture_passes(tmp_path) -> None:
    result = run_scan(Path("examples/postgres_dbt/policystrata_clean.yaml"), tmp_path / "clean")

    assert result.gate.outcome == GateOutcome.PASS
    assert result.summary.total_findings == 0
    assert (tmp_path / "clean" / "report.md").read_text(encoding="utf-8").count("No findings") == 1


def test_dbt_adapter_reports_expression_and_metadata_diagnostics(tmp_path) -> None:
    fixture = tmp_path / "semantic_models.yml"
    fixture.write_text(
        """
semantic_models:
  - name: support_metrics
    model: ref('fct_support_metrics')
    measures:
      - name: net_revenue
        agg: sum
        expr: gross_amount_cents
    dimensions:
      - name: customer_email
        type: categorical
metrics:
  - name: net_revenue
    type: simple
    type_params:
      measure: net_revenue
""".lstrip(),
        encoding="utf-8",
    )

    result = inspect_dbt_semantic_model("support_saas", fixture)

    assert result["expression_mismatches"][0]["metric"] == "net_revenue"
    assert "customer_email" in result["sensitive_metadata_missing"]


def test_imported_trace_rejects_non_read_only_sql(tmp_path) -> None:
    trace_path = tmp_path / "traces.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "id": "bad_trace",
                "principal": "acme_analyst",
                "sql": "drop table accounts",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only read-only"):
        load_imported_traces([trace_path])


def test_imported_trace_paths_must_stay_under_config_dir(tmp_path) -> None:
    with pytest.raises(ValueError, match="must stay under"):
        resolve_scan_input_paths(tmp_path, ["../traces.jsonl"], "sql trace")


def test_read_only_sql_rejects_write_tokens() -> None:
    assert_read_only_sql("select tenant_id from accounts")

    with pytest.raises(ValueError, match="at most one trailing semicolon"):
        assert_read_only_sql("select tenant_id from accounts; delete from accounts")


def test_fuzz_classifies_stillborn_and_equivalent_mutants(tmp_path) -> None:
    trace_path = tmp_path / "traces.jsonl"
    trace_path.write_text(
        json.dumps(
            {
                "id": "no_semantic_ir",
                "principal": "acme_analyst",
                "sql": "select accounts.tenant_id from accounts where accounts.tenant_id in ('acme')",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    trace = load_imported_traces([trace_path])[0]
    fuzzed = fuzz_imported_trace(trace, load_policy(), seed=7, max_cases=6)
    statuses = {item["status"] for item in fuzzed}

    assert MutantStatus.STILLBORN in statuses
    assert MutantStatus.EQUIVALENT in statuses


def test_scan_imported_trace_compares_real_db_rows() -> None:
    policy = load_policy()
    config = load_scan_config(Path("examples/postgres_dbt/policystrata_clean.yaml"))
    trace = load_imported_traces([Path("examples/postgres_dbt/traces_clean.jsonl")])[0]
    fake_db = FakePostgresAdapter()

    findings = scan_imported_trace(config, Path("policystrata.yaml"), policy, trace, fake_db)

    assert any(item.id.startswith("real_db_semantic_drift") for item in findings)
    assert fake_db.tenant_ids == ["acme", "acme"]


def test_scan_imported_trace_reports_database_execution_errors() -> None:
    policy = load_policy()
    config = load_scan_config(Path("examples/postgres_dbt/policystrata_clean.yaml"))
    trace = load_imported_traces([Path("examples/postgres_dbt/traces_clean.jsonl")])[0]

    findings = scan_imported_trace(
        config,
        Path("policystrata.yaml"),
        policy,
        trace.model_copy(
            update={"semantic_ir": SemanticQuery(metric="ticket_count", dimensions=["region"])},
        ),
        FailingPostgresAdapter(),
    )

    assert findings[0].id.startswith("imported_sql_execution_error")
    assert findings[0].evidence_level == "real_db"


def test_start_docker_fixture_uses_docker_compose(monkeypatch) -> None:
    calls = []

    def fake_run(command, check, capture_output, text):
        calls.append((command, check, capture_output, text))

    def fake_wait(database_url, timeout_seconds):
        calls.append((database_url, timeout_seconds))

    config = load_scan_config(Path("examples/postgres_dbt/policystrata.yaml"))
    config.database.start_docker = True
    config.database.compose_file = "../../docker-compose.yml"
    config.database.startup_timeout_seconds = 4.0
    monkeypatch.setattr("policystrata.scanner.subprocess.run", fake_run)
    monkeypatch.setattr("policystrata.scanner.wait_for_postgres", fake_wait)

    start_docker_fixture(
        config,
        Path("examples/postgres_dbt").resolve(),
        "postgresql://policystrata:policystrata@localhost:55432/support_saas",
    )

    assert calls[0][0][:4] == ["docker", "compose", "-f", str(Path("docker-compose.yml").resolve())]
    assert calls[0][0][-3:] == ["up", "-d", "postgres"]
    assert calls[1] == (
        "postgresql://policystrata:policystrata@localhost:55432/support_saas",
        4.0,
    )


class FakePostgresAdapter:
    def __init__(self) -> None:
        self.tenant_ids: list[str | None] = []

    def query(self, sql: str, tenant_id: str | None = None) -> list[dict[str, object]]:
        self.tenant_ids.append(tenant_id)
        if "left join subscriptions" in sql:
            return [{"value": 3, "region": "west"}]
        return [{"value": 6, "region": "west"}]


class FailingPostgresAdapter:
    def query(self, sql: str, tenant_id: str | None = None) -> list[dict[str, object]]:
        raise psycopg.OperationalError("fixture unavailable")

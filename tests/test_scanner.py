import json
from collections import Counter
from pathlib import Path

import psycopg
import pytest

from policystrata.database import assert_read_only_sql
from policystrata.domain import load_policy
from policystrata.integrations.dbt_semantic import inspect_dbt_semantic_model
from policystrata.models import SemanticQuery
from policystrata.scan_models import GateOutcome, ImportedTrace, MutantStatus, RegressionCase
from policystrata.scanner import (
    exercised_evidence_levels,
    load_scan_config,
    run_scan,
    scan_imported_trace,
    scan_state_assertions,
    start_docker_fixture,
)
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
    assert all(item.minimal_repro_trace == item.witness_path for item in result.findings)
    assert all(item.ci_gate_command for item in result.findings)
    assert any(item.id.startswith("unsafe_release") for item in result.findings)
    assert any(item.id.startswith("tenant_scope_missing") for item in result.findings)
    assert not any(item.id == "postgres_fixture_unavailable" for item in result.findings)
    assert result.summary.regression_cases["fail_to_pass"] >= 2
    assert result.summary.integration_readiness["level"] == "ci-gate-ready"

    scan_json = json.loads((tmp_path / "scan" / "scan.json").read_text(encoding="utf-8"))
    assert scan_json["gate"]["outcome"] == "fail"
    report = (tmp_path / "scan" / "report.md").read_text(encoding="utf-8")
    assert "## Production Integration" in report
    assert "Configured readiness:" in report
    assert "Score:" not in report
    assert "## Remediation" in report


def test_scan_clean_fixture_passes(tmp_path) -> None:
    result = run_scan(Path("examples/postgres_dbt/policystrata_clean.yaml"), tmp_path / "clean")

    assert result.gate.outcome == GateOutcome.PASS
    assert result.summary.total_findings == 0
    assert result.summary.evidence_exercised["imported_trace"] == 1
    assert (tmp_path / "clean" / "report.md").read_text(encoding="utf-8").count("No findings") == 1
    assert "## Evidence Exercised" in (tmp_path / "clean" / "report.md").read_text(encoding="utf-8")


def test_scan_accepts_configured_tenancy_predicate(tmp_path) -> None:
    trace_path = tmp_path / "traces.jsonl"
    config_path = tmp_path / "policystrata.yaml"
    trace_path.write_text(
        json.dumps(
            {
                "id": "custom_household_scope",
                "principal": "acme_analyst",
                "tenant_ids": ["acme"],
                "release_allowed": True,
                "semantic_ir": {"metric": "ticket_count", "limit": 100},
                "sql": (
                    "select count(distinct support_tickets.id) as value "
                    "from support_tickets "
                    "join transactions on transactions.ticket_id = support_tickets.id "
                    "where transactions.household_id = 'acme' "
                    "limit 100"
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config_path.write_text(
        """
version: 1
domain: support_saas
sql_traces:
  files:
    - traces.jsonl
tenancy:
  canonical_predicates:
    - "transactions.household_id = :principal.tenant_id"
  tenant_columns:
    - transactions.household_id
fuzz:
  enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    result = run_scan(config_path, tmp_path / "scan")

    assert result.gate.outcome == GateOutcome.PASS
    assert not any(item.id.startswith("tenant_scope_missing") for item in result.findings)


def test_scan_accepts_policystrata_node_mixed_jsonl(tmp_path) -> None:
    trace_path = tmp_path / "traces.jsonl"
    config_path = tmp_path / "policystrata.yaml"
    records = [
        {
            "id": "session_1",
            "record_type": "agent_session",
            "session_id": "chat-run-1",
            "prompt_class": "user_finance_question",
            "tools_available": ["searchTickets"],
        },
        {
            "trace_id": "ask_ai_read_1",
            "record_type": "sql_trace",
            "principal": "acme_analyst",
            "tenant_ids": ["acme"],
            "release_allowed": True,
            "semantic_ir": {"metric": "ticket_count", "limit": 100},
            "query": {
                "sql": (
                    "select count(distinct support_tickets.id) as value "
                    "from accounts "
                    "left join support_tickets on support_tickets.account_id = accounts.id "
                    "where accounts.tenant_id = $1 "
                    "limit 100"
                )
            },
            "tool": {"name": "searchTickets", "kind": "read"},
        },
        {
            "id": "write_1",
            "record_type": "mutation",
            "session_id": "chat-run-1",
            "mutation": {
                "table": "support_tickets",
                "where_predicates": ["id", "tenant_id"],
                "columns_written": ["status"],
            },
        },
    ]
    trace_path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    config_path.write_text(
        """
version: 1
domain: support_saas
sql_traces:
  files:
    - traces.jsonl
fuzz:
  enabled: false
""".lstrip(),
        encoding="utf-8",
    )

    traces = load_imported_traces([trace_path])
    result = run_scan(config_path, tmp_path / "scan")

    assert [trace.id for trace in traces] == ["ask_ai_read_1"]
    assert traces[0].sql.startswith("select count")
    assert result.gate.outcome == GateOutcome.PASS


def test_scan_state_assertions_detect_forbidden_database_state() -> None:
    config = load_scan_config(Path("examples/postgres_dbt/policystrata_real_db_clean.yaml"))
    findings = scan_state_assertions(
        config,
        Path("examples/postgres_dbt/policystrata_real_db_clean.yaml"),
        LeakyStatePostgresAdapter(),
    )

    assert len(findings) == 1
    assert findings[0].id.startswith("postgres_state_assertion_failed")
    assert findings[0].evidence_level == "real_db"
    assert findings[0].regression_case == RegressionCase.PASS_TO_PASS
    assert "forbidden values" in findings[0].reasons[-1]


def test_scan_state_assertions_pass_clean_database_state() -> None:
    config = load_scan_config(Path("examples/postgres_dbt/policystrata_real_db_clean.yaml"))
    findings = scan_state_assertions(
        config,
        Path("examples/postgres_dbt/policystrata_real_db_clean.yaml"),
        CleanStatePostgresAdapter(),
    )

    assert findings == []


def test_scan_summary_counts_successful_real_db_evidence(tmp_path) -> None:
    config_path = Path("examples/postgres_dbt/policystrata_real_db_clean.yaml")
    config = load_scan_config(config_path)
    trace = load_imported_traces([Path("examples/postgres_dbt/traces_real_db_clean.jsonl")])[0]

    exercised = exercised_evidence_levels(
        config,
        load_policy(),
        [trace],
        CleanStatePostgresAdapter(),
        Counter(),
    )

    assert exercised["imported_trace"] == 1
    assert exercised["real_db"] >= 2


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


def test_fuzz_uses_configured_tenant_columns() -> None:
    trace = ImportedTrace(
        id="custom_tenant_column",
        principal="acme_analyst",
        sql="select * from transactions where transactions.household_id = 'acme'",
        semantic_ir=SemanticQuery(metric="ticket_count"),
        release_allowed=True,
    )

    fuzzed = fuzz_imported_trace(
        trace,
        load_policy(),
        seed=7,
        max_cases=1,
        tenant_columns=["transactions.household_id"],
    )

    assert fuzzed == [
        {
            "mutation": "tenant_predicate_removed",
            "status": MutantStatus.KILLED,
            "sql": "select * from transactions where transactions.legacy_household_id = 'acme'",
            "reason": "tenant-scope predicate can be changed away from the configured policy column",
        }
    ]


def test_fuzz_handles_declared_principal_with_unknown_role() -> None:
    policy = load_policy().model_copy(deep=True)
    policy.principals["orphaned_principal"] = policy.principals["acme_analyst"].model_copy(
        update={"id": "orphaned_principal", "role": "missing_role"}
    )
    trace = ImportedTrace(
        id="orphaned_role_trace",
        principal="orphaned_principal",
        sql="select accounts.tenant_id from accounts where accounts.tenant_id in ('acme')",
        semantic_ir=SemanticQuery(metric="ticket_count"),
        release_allowed=True,
    )

    fuzzed = fuzz_imported_trace(trace, policy, seed=7, max_cases=8)

    assert {
        "mutation": "limit_expanded",
        "status": MutantStatus.STILLBORN,
        "reason": "trace principal role is not declared in the policy",
    } in fuzzed


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


class LeakyStatePostgresAdapter:
    def query(self, sql: str, tenant_id: str | None = None) -> list[dict[str, object]]:
        return [{"tenant_id": "acme", "value": 2}, {"tenant_id": "beta", "value": 1}]


class CleanStatePostgresAdapter:
    def query(self, sql: str, tenant_id: str | None = None) -> list[dict[str, object]]:
        return [{"tenant_id": "acme", "value": 2}]

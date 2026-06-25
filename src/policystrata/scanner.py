from __future__ import annotations

import json
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

import psycopg
from pydantic import ValidationError

from policystrata.compiler import compile_query, tenant_column
from policystrata.database import (
    DEFAULT_APP_DATABASE_URL,
    DEFAULT_DATABASE_URL,
    PostgresAdapter,
    assert_read_only_sql,
)
from policystrata.domain import load_policy, load_surface_config, load_yaml_mapping
from policystrata.evidence import markdown_table
from policystrata.integrations.dbt_semantic import inspect_dbt_semantic_model
from policystrata.models import Decision, Policy, SemanticQuery, SurfaceName, WitnessClass
from policystrata.policy import PolicyOracle
from policystrata.scan_models import (
    EvidenceLevel,
    FindingConfidence,
    FindingSeverity,
    GateDecision,
    GateOutcome,
    ImportedTrace,
    MutantStatus,
    RegressionCase,
    ScanConfig,
    ScanFinding,
    ScanResult,
    ScanSummary,
    StateAssertionConfig,
)
from policystrata.trace_import import (
    fuzz_imported_trace,
    load_imported_traces,
    resolve_optional_config_path,
    resolve_scan_input_paths,
    semantic_query_dump,
)

SCAN_OUTPUT_FILES = {
    "scan": "scan.json",
    "findings": "findings.jsonl",
    "summary": "summary.json",
    "report": "report.md",
}
DATABASE_FIXTURE_EXCEPTIONS = (
    OSError,
    TimeoutError,
    ValueError,
    subprocess.SubprocessError,
    psycopg.Error,
)
DATABASE_QUERY_EXCEPTIONS = (OSError, ValueError, psycopg.Error)
POSTGRES_STARTUP_EXCEPTIONS = (OSError, psycopg.Error)
DbtValueFindingSpec = tuple[
    str,
    str,
    str,
    str,
    str,
    FindingSeverity,
    FindingConfidence,
]
DBT_VALUE_FINDING_SPECS: tuple[DbtValueFindingSpec, ...] = (
    (
        "missing_policy_metrics",
        "dbt_missing_policy_metric",
        "Policy metric is missing from dbt semantic model",
        "metric {value} exists in policy but not in dbt metrics or measures",
        "manifest",
        FindingSeverity.WARNING,
        FindingConfidence.MEDIUM,
    ),
    (
        "stale_dbt_metrics",
        "dbt_stale_metric",
        "dbt semantic model exposes a stale metric",
        "metric {value} exists in dbt but not in the PolicyStrata policy",
        "manifest",
        FindingSeverity.WARNING,
        FindingConfidence.MEDIUM,
    ),
    (
        "missing_policy_dimensions",
        "dbt_missing_policy_dimension",
        "Policy dimension is missing from dbt semantic model",
        "dimension {value} exists in policy but not in dbt dimensions",
        "manifest",
        FindingSeverity.WARNING,
        FindingConfidence.MEDIUM,
    ),
    (
        "stale_dbt_dimensions",
        "dbt_stale_dimension",
        "dbt semantic model exposes a stale dimension",
        "dimension {value} exists in dbt but not in the PolicyStrata policy",
        "manifest",
        FindingSeverity.WARNING,
        FindingConfidence.MEDIUM,
    ),
    (
        "sensitive_metadata_missing",
        "dbt_sensitive_metadata_missing",
        "Sensitive dbt dimension lacks sensitivity metadata",
        "sensitive policy dimension {value} should be marked sensitive in dbt metadata",
        "manifest",
        FindingSeverity.WARNING,
        FindingConfidence.MEDIUM,
    ),
    (
        "models_missing_lineage",
        "dbt_missing_lineage",
        "dbt semantic model lacks lineage reference",
        "semantic model {value} has no model/ref lineage field",
        "manifest",
        FindingSeverity.INFO,
        FindingConfidence.LOW,
    ),
)


def load_scan_config(path: Path) -> ScanConfig:
    try:
        raw = load_yaml_mapping(path)
        return ScanConfig.model_validate(raw)
    except (TypeError, ValidationError) as exc:
        raise ValueError(f"invalid scan config {path}: {exc}") from exc


def run_scan(config_path: Path, out_dir: Path | None = None) -> ScanResult:
    config_path = config_path.resolve()
    config_dir = config_path.parent
    config = load_scan_config(config_path)
    output_dir = out_dir or resolve_optional_config_path(config_dir, config.output) or config_dir / "scan-out"
    output_dir.mkdir(parents=True, exist_ok=True)
    witness_dir = output_dir / "witnesses"
    witness_dir.mkdir(parents=True, exist_ok=True)

    domain_path = resolve_optional_config_path(config_dir, config.domain_path)
    policy = load_policy(config.domain, domain_path)
    load_surface_config(config.domain, domain_path)
    findings: list[ScanFinding] = []
    mutant_statuses: Counter[str] = Counter()

    findings.extend(required_input_findings(config, config_path))
    findings.extend(scan_dbt_inputs(config, config_path, domain_path))
    database_adapter, database_findings = prepare_database(config, config_path)
    findings.extend(database_findings)

    imported_traces, import_findings = load_scan_traces(config, config_path)
    findings.extend(import_findings)
    trace_findings, mutant_statuses = scan_imported_traces(
        config,
        config_path,
        policy,
        imported_traces,
        database_adapter,
    )
    findings.extend(trace_findings)
    if database_adapter is not None:
        findings.extend(scan_rls_checks(config, config_path, database_adapter))
        findings.extend(scan_state_assertions(config, config_path, database_adapter))

    findings = assign_witness_paths(findings, witness_dir, output_dir)
    gate = decide_gate(findings, config)
    summary = build_summary(
        findings,
        gate.outcome,
        mutant_statuses,
        exercised_evidence_levels(config, policy, imported_traces, database_adapter, mutant_statuses),
    )
    result = ScanResult(
        domain=config.domain,
        config_path=str(config_path),
        output_dir=str(output_dir),
        gate=gate,
        summary=summary,
        findings=findings,
        artifacts=dict(SCAN_OUTPUT_FILES),
    )
    write_scan_outputs(result, output_dir, config)
    return result


def load_scan_traces(
    config: ScanConfig,
    config_path: Path,
) -> tuple[list[ImportedTrace], list[ScanFinding]]:
    if not config.sql_traces.files:
        return [], []
    try:
        trace_paths = resolve_scan_input_paths(config_path.parent, config.sql_traces.files, "sql trace")
        return load_imported_traces(trace_paths), []
    except ValueError as exc:
        return [], [
            finding(
                "invalid_sql_trace_input",
                "Imported SQL trace was rejected",
                FindingSeverity.CRITICAL,
                FindingConfidence.HIGH,
                "grammar",
                WitnessClass.OVER_PERMISSIVE,
                EvidenceLevel.IMPORTED_TRACE,
                [str(exc)],
                config_path,
            )
        ]


def scan_imported_traces(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    imported_traces: list[ImportedTrace],
    database_adapter: PostgresAdapter | None,
) -> tuple[list[ScanFinding], Counter[str]]:
    findings: list[ScanFinding] = []
    mutant_statuses: Counter[str] = Counter()
    for trace in imported_traces:
        findings.extend(scan_imported_trace(config, config_path, policy, trace, database_adapter))
        if config.fuzz.enabled:
            fuzz_findings, fuzz_statuses = scan_fuzzed_trace(config, config_path, policy, trace)
            findings.extend(fuzz_findings)
            mutant_statuses.update(fuzz_statuses)
    return findings, mutant_statuses


def scan_fuzzed_trace(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    trace: ImportedTrace,
) -> tuple[list[ScanFinding], Counter[str]]:
    findings: list[ScanFinding] = []
    mutant_statuses: Counter[str] = Counter()
    fuzzed_traces = fuzz_imported_trace(
        trace,
        policy,
        config.fuzz.seed,
        config.fuzz.max_cases_per_trace,
    )
    for fuzzed in fuzzed_traces:
        status = MutantStatus(fuzzed["status"])
        mutant_statuses[status.value] += 1
        if status != MutantStatus.SURVIVED:
            continue
        findings.append(
            finding(
                f"fuzz_survived_{trace.id}_{fuzzed['mutation']}",
                "Generated fuzz mutant survived scanner checks",
                FindingSeverity.WARNING,
                FindingConfidence.MEDIUM,
                "validator",
                WitnessClass.CLEAN,
                EvidenceLevel.PROPERTY_GENERATED,
                [str(fuzzed["reason"])],
                config_path,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(fuzzed.get("semantic_ir")),
                sql=fuzzed.get("sql"),
                source=trace.source,
                mutation=str(fuzzed["mutation"]),
                mutant_status=status,
                regression_case=RegressionCase.FAIL_TO_PASS,
            )
        )
    return findings, mutant_statuses


def required_input_findings(config: ScanConfig, config_path: Path) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    required_inputs = set(config.gate.required_inputs)
    checks = {
        "dbt": bool(config.dbt.files),
        "sql_traces": bool(config.sql_traces.files),
        "database": bool(
            config.database.rls_checks
            or config.database.state_assertions
            or config.database.schema_path
            or config.database.seed
        ),
        "state_assertions": bool(config.database.state_assertions),
    }
    for input_name, present in checks.items():
        if input_name in required_inputs and not present:
            findings.append(
                finding(
                    f"missing_required_{input_name}",
                    f"Required scanner input is missing: {input_name}",
                    FindingSeverity.CRITICAL,
                    FindingConfidence.HIGH,
                    "manifest",
                    WitnessClass.OVER_RESTRICTIVE,
                    EvidenceLevel.DETERMINISTIC_FIXTURE,
                    [f"scan config marks {input_name} as required, but no input was configured"],
                    config_path,
                )
            )
    return findings


def scan_dbt_inputs(config: ScanConfig, config_path: Path, domain_path: Path | None) -> list[ScanFinding]:
    if not config.dbt.files:
        return []
    config_dir = config_path.parent
    findings: list[ScanFinding] = []
    for dbt_path in resolve_scan_input_paths(config_dir, config.dbt.files, "dbt semantic model"):
        result = inspect_dbt_semantic_model(config.domain, dbt_path, domain_path)
        source = str(dbt_path)
        for key, id_prefix, title, reason_template, surface, severity, confidence in DBT_VALUE_FINDING_SPECS:
            findings.extend(
                adapter_value_findings(
                    result[key],
                    id_prefix,
                    title,
                    reason_template,
                    source,
                    config_path,
                    surface,
                    severity=severity,
                    confidence=confidence,
                )
            )
        for mismatch in result["expression_mismatches"]:
            metric = str(mismatch["metric"])
            findings.append(
                adapter_finding(
                    f"dbt_expression_mismatch_{metric}",
                    "dbt measure expression differs from policy metric column",
                    [str(mismatch["reason"])],
                    source,
                    config_path,
                    "compiler",
                    witness_class=WitnessClass.SEMANTIC_DRIFT,
                    metadata=mismatch,
                )
            )
    return findings


def scan_imported_trace(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    trace: ImportedTrace,
    database_adapter: PostgresAdapter | None = None,
) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    oracle = PolicyOracle(policy)
    principal_decision, role_name = oracle.principal(trace.principal)
    if not principal_decision.allowed or role_name is None:
        findings.append(
            finding(
                f"trace_unknown_principal_{trace.id}",
                "Imported trace references an unknown principal",
                FindingSeverity.HIGH,
                FindingConfidence.HIGH,
                "validator",
                WitnessClass.OVER_PERMISSIVE,
                EvidenceLevel.IMPORTED_TRACE,
                principal_decision.reasons,
                config_path,
                principal=trace.principal,
                sql=trace.sql,
                source=trace.source,
                regression_case=trace.regression_case,
            )
        )
        return findings

    canonical = authorize_imported_trace(oracle, trace)
    findings.extend(scan_trace_authorization(config_path, trace, canonical))
    findings.extend(scan_trace_static_sql(config, config_path, policy, trace, canonical))
    if should_compare_trace_on_database(config, trace, canonical, database_adapter):
        assert database_adapter is not None
        findings.extend(
            scan_imported_trace_on_database(
                config,
                config_path,
                policy,
                trace,
                database_adapter,
            )
        )
    return findings


def authorize_imported_trace(oracle: PolicyOracle, trace: ImportedTrace) -> Decision | None:
    if trace.semantic_ir is None:
        return None
    return oracle.authorize(trace.principal, trace.semantic_ir)


def scan_trace_authorization(
    config_path: Path,
    trace: ImportedTrace,
    canonical: Decision | None,
) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    if canonical is not None and not canonical.allowed and trace.release_allowed is True:
        findings.append(
            imported_trace_finding(
                f"unsafe_release_{trace.id}",
                "Unauthorized semantic request was released",
                FindingSeverity.HIGH,
                FindingConfidence.HIGH,
                "release",
                WitnessClass.UNSAFE_RELEASE,
                canonical.reasons,
                config_path,
                trace,
            )
        )
    if canonical is None or canonical.allowed or trace.release_allowed is False:
        return findings
    findings.append(
        imported_trace_finding(
            f"unauthorized_trace_reached_sql_{trace.id}",
            "Unauthorized semantic request reached SQL trace",
            FindingSeverity.HIGH,
            FindingConfidence.HIGH,
            "validator",
            WitnessClass.OVER_PERMISSIVE,
            canonical.reasons,
            config_path,
            trace,
        )
    )
    return findings


def scan_trace_static_sql(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    trace: ImportedTrace,
    canonical: Decision | None,
) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    allow_rls_only = bool(trace.expected_policy.get("allow_rls_only"))
    if not allow_rls_only and not sql_preserves_tenant_scope(
        config.domain,
        policy,
        trace.principal,
        trace.sql,
    ):
        findings.append(
            imported_trace_finding(
                f"tenant_scope_missing_{trace.id}",
                "Imported SQL does not preserve the canonical tenant-scope predicate",
                FindingSeverity.HIGH,
                FindingConfidence.HIGH,
                "compiler",
                WitnessClass.LOWERING_VIOLATION,
                [tenant_scope_reason(config.domain, policy, trace.principal)],
                config_path,
                trace,
            )
        )

    if trace_missing_policy_metric(policy, trace, canonical):
        findings.append(
            imported_trace_finding(
                f"metric_expression_unobserved_{trace.id}",
                "Imported SQL does not visibly reference the canonical policy metric expression",
                FindingSeverity.WARNING,
                FindingConfidence.MEDIUM,
                "compiler",
                WitnessClass.SEMANTIC_DRIFT,
                ["static SQL inspection could not match the query to the canonical metric expression"],
                config_path,
                trace,
            )
        )
    return findings


def trace_missing_policy_metric(
    policy: Policy,
    trace: ImportedTrace,
    canonical: Decision | None,
) -> bool:
    return (
        canonical is not None
        and canonical.allowed
        and trace.semantic_ir is not None
        and not sql_mentions_policy_metric(policy, trace.semantic_ir.metric, trace.sql)
    )


def should_compare_trace_on_database(
    config: ScanConfig,
    trace: ImportedTrace,
    canonical: Decision | None,
    database_adapter: PostgresAdapter | None,
) -> bool:
    return (
        database_adapter is not None
        and config.database.execute_imported_sql
        and trace.semantic_ir is not None
        and canonical is not None
        and canonical.allowed
    )


def scan_imported_trace_on_database(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    trace: ImportedTrace,
    app: PostgresAdapter,
) -> list[ScanFinding]:
    if trace.semantic_ir is None:
        return []
    semantic_ir = trace.semantic_ir
    principal = policy.principals[trace.principal]
    tenant_id = imported_trace_tenant_id(trace, principal.tenant_ids)
    imported_rows, error = query_trace_sql(
        app,
        trace.sql,
        tenant_id,
        config,
        config_path,
        trace,
        semantic_ir,
        f"imported_sql_execution_error_{trace.id}",
        "Imported SQL could not be executed against the configured PostgreSQL fixture",
        metadata={"tenant_id": tenant_id},
    )
    if error is not None:
        return [error]

    canonical_sql = compile_query(
        policy,
        principal,
        semantic_ir,
        domain=config.domain,
    ).sql
    canonical_rows, error = query_trace_sql(
        app,
        canonical_sql,
        tenant_id,
        config,
        config_path,
        trace,
        semantic_ir,
        f"canonical_sql_execution_error_{trace.id}",
        "Canonical compiler SQL could not be executed against the configured PostgreSQL fixture",
        metadata={"tenant_id": tenant_id, "imported_sql": trace.sql},
    )
    if error is not None:
        return [error]

    if normalize_rows(imported_rows) == normalize_rows(canonical_rows):
        return []
    return [
        finding(
            f"real_db_semantic_drift_{trace.id}",
            "Imported SQL produced different rows than canonical policy SQL",
            FindingSeverity.HIGH,
            FindingConfidence.HIGH,
            "compiler",
            WitnessClass.SEMANTIC_DRIFT,
            EvidenceLevel.REAL_DB,
            [
                "real PostgreSQL execution differed between imported SQL and canonical compiler SQL",
                f"imported rows={len(imported_rows)}, canonical rows={len(canonical_rows)}",
            ],
            config_path,
            principal=trace.principal,
            semantic_ir=semantic_query_dump(semantic_ir),
            sql=trace.sql,
            source=trace.source,
            metadata={
                "tenant_id": tenant_id,
                "canonical_sql": canonical_sql,
                "imported_rows": normalize_rows(imported_rows),
                "canonical_rows": normalize_rows(canonical_rows),
            },
            regression_case=trace.regression_case,
        )
    ]


def query_trace_sql(
    app: PostgresAdapter,
    sql: str,
    tenant_id: str | None,
    config: ScanConfig,
    config_path: Path,
    trace: ImportedTrace,
    semantic_ir: SemanticQuery,
    error_id: str,
    error_title: str,
    metadata: dict[str, Any],
) -> tuple[list[dict[str, Any]], ScanFinding | None]:
    try:
        return app.query(sql, tenant_id=tenant_id), None
    except DATABASE_QUERY_EXCEPTIONS as exc:
        return [], database_error_finding(
            error_id,
            error_title,
            [str(exc)],
            config_path,
            required=config.database.required,
            principal=trace.principal,
            semantic_ir=semantic_query_dump(semantic_ir),
            sql=sql,
            source=trace.source,
            metadata=metadata,
            regression_case=trace.regression_case,
        )


def imported_trace_tenant_id(trace: ImportedTrace, principal_tenant_ids: list[str]) -> str | None:
    if trace.tenant_ids:
        return str(trace.tenant_ids[0])
    if principal_tenant_ids:
        return str(principal_tenant_ids[0])
    return None


def normalize_rows(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(row, sort_keys=True, default=str) for row in rows)


def prepare_database(
    config: ScanConfig,
    config_path: Path,
) -> tuple[PostgresAdapter | None, list[ScanFinding]]:
    if not should_prepare_database(config):
        return None, []
    findings: list[ScanFinding] = []
    config_dir = config_path.parent
    schema = resolve_optional_config_path(config_dir, config.database.schema_path)
    seed = resolve_optional_config_path(config_dir, config.database.seed)
    admin_url = config.database.admin_url or DEFAULT_DATABASE_URL
    app_url = config.database.app_url or DEFAULT_APP_DATABASE_URL

    try:
        if config.database.start_docker:
            start_docker_fixture(config, config_dir, admin_url)
        admin = PostgresAdapter(admin_url)
        admin.load_fixture(schema, seed)
        app = PostgresAdapter(app_url)
    except DATABASE_FIXTURE_EXCEPTIONS as exc:
        findings.append(
            database_error_finding(
                "postgres_fixture_unavailable",
                "PostgreSQL fixture could not be prepared",
                [str(exc)],
                config_path,
                required=config.database.required,
                confidence=database_fixture_confidence(config.database.required),
            )
        )
        return None, findings
    return app, findings


def should_prepare_database(config: ScanConfig) -> bool:
    return bool(
        config.database.required
        or config.database.schema_path
        or config.database.seed
        or config.database.rls_checks
        or config.database.state_assertions
        or (config.database.execute_imported_sql and config.sql_traces.files and config.database.app_url)
    )


def start_docker_fixture(config: ScanConfig, config_dir: Path, database_url: str) -> None:
    compose_file = resolve_optional_config_path(config_dir, config.database.compose_file)
    command = ["docker", "compose"]
    if compose_file is not None:
        command.extend(["-f", str(compose_file)])
    command.extend(["up", "-d", config.database.compose_service])
    subprocess.run(command, check=True, capture_output=True, text=True)
    wait_for_postgres(database_url, config.database.startup_timeout_seconds)


def wait_for_postgres(database_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(database_url, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
                return
        except POSTGRES_STARTUP_EXCEPTIONS as exc:
            last_error = exc
            time.sleep(0.5)
    if last_error is not None:
        raise TimeoutError(f"PostgreSQL did not become ready within {timeout_seconds}s: {last_error}")
    raise TimeoutError(f"PostgreSQL did not become ready within {timeout_seconds}s")


def scan_rls_checks(
    config: ScanConfig,
    config_path: Path,
    app: PostgresAdapter,
) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for check in config.database.rls_checks:
        try:
            assert_read_only_sql(check.sql)
            rows = app.query(check.sql, tenant_id=check.tenant_id)
        except DATABASE_QUERY_EXCEPTIONS as exc:
            findings.append(
                database_error_finding(
                    f"postgres_rls_check_error_{check.id}",
                    "PostgreSQL RLS check could not run",
                    [str(exc)],
                    config_path,
                    required=check.required or config.database.required,
                    sql=check.sql,
                )
            )
            continue

        observed_tenants = {str(row[check.tenant_column]) for row in rows if check.tenant_column in row}
        expected_tenants = set(check.expected_tenant_ids)
        row_count_matches = check.expected_rows is None or len(rows) == check.expected_rows
        tenants_match = not expected_tenants or observed_tenants == expected_tenants
        if not row_count_matches or not tenants_match:
            findings.append(
                finding(
                    f"postgres_rls_check_failed_{check.id}",
                    "PostgreSQL RLS check observed rows outside the expected policy scope",
                    FindingSeverity.HIGH,
                    FindingConfidence.HIGH,
                    "database",
                    WitnessClass.OVER_PERMISSIVE,
                    EvidenceLevel.REAL_DB,
                    [
                        f"expected rows={check.expected_rows}, observed rows={len(rows)}",
                        (
                            f"expected tenants={sorted(expected_tenants)}, "
                            f"observed tenants={sorted(observed_tenants)}"
                        ),
                    ],
                    config_path,
                    sql=check.sql,
                    metadata={"tenant_id": check.tenant_id, "rows": len(rows)},
                )
            )
    return findings


def scan_state_assertions(
    config: ScanConfig,
    config_path: Path,
    app: PostgresAdapter,
) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    for check in config.database.state_assertions:
        try:
            assert_read_only_sql(check.sql)
            rows = app.query(check.sql, tenant_id=check.tenant_id)
        except DATABASE_QUERY_EXCEPTIONS as exc:
            findings.append(
                database_error_finding(
                    f"postgres_state_assertion_error_{check.id}",
                    "PostgreSQL state assertion could not run",
                    [str(exc)],
                    config_path,
                    required=check.required or config.database.required,
                    sql=check.sql,
                    regression_case=check.regression_case,
                )
            )
            continue

        failures, witness_class = evaluate_state_assertion(check, rows)
        if failures:
            findings.append(
                finding(
                    f"postgres_state_assertion_failed_{check.id}",
                    "PostgreSQL state assertion failed",
                    FindingSeverity.HIGH,
                    FindingConfidence.HIGH,
                    "database",
                    witness_class,
                    EvidenceLevel.REAL_DB,
                    failures,
                    config_path,
                    sql=check.sql,
                    metadata={
                        "tenant_id": check.tenant_id,
                        "rows": len(rows),
                        "rows_sample": normalize_rows(rows[:20]),
                    },
                    regression_case=check.regression_case,
                )
            )
    return findings


def evaluate_state_assertion(
    check: StateAssertionConfig,
    rows: list[dict[str, Any]],
) -> tuple[list[str], WitnessClass]:
    failures: list[str] = []
    witness_class = WitnessClass.OVER_RESTRICTIVE
    observed_columns = {str(column) for row in rows for column in row}

    if check.expect_empty and rows:
        failures.append(f"expected no rows, observed rows={len(rows)}")
        witness_class = WitnessClass.OVER_PERMISSIVE
    if check.expected_rows is not None and len(rows) != check.expected_rows:
        failures.append(f"expected rows={check.expected_rows}, observed rows={len(rows)}")
        if len(rows) > check.expected_rows:
            witness_class = WitnessClass.OVER_PERMISSIVE

    missing_columns = sorted(set(check.require_columns) - observed_columns)
    if missing_columns:
        failures.append(f"required columns missing from result: {missing_columns}")

    forbidden_columns = sorted(set(check.forbidden_columns) & observed_columns)
    if forbidden_columns:
        failures.append(f"forbidden columns present in result: {forbidden_columns}")
        witness_class = WitnessClass.OVER_PERMISSIVE

    for column, allowed_values in check.allowed_values.items():
        allowed = {assertion_value_key(value) for value in allowed_values}
        observed = [
            row.get(column)
            for row in rows
            if column in row and assertion_value_key(row.get(column)) not in allowed
        ]
        if observed:
            failures.append(
                f"column {column} contained values outside the allowed set: {sorted(map(str, observed))}"
            )
            witness_class = WitnessClass.OVER_PERMISSIVE

    for column, forbidden_values in check.forbidden_values.items():
        forbidden = {assertion_value_key(value) for value in forbidden_values}
        observed = [
            row.get(column)
            for row in rows
            if column in row and assertion_value_key(row.get(column)) in forbidden
        ]
        if observed:
            failures.append(f"column {column} contained forbidden values: {sorted(map(str, observed))}")
            witness_class = WitnessClass.OVER_PERMISSIVE

    return failures, witness_class


def assertion_value_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def database_error_severity(required: bool) -> FindingSeverity:
    return FindingSeverity.CRITICAL if required else FindingSeverity.WARNING


def database_fixture_confidence(required: bool) -> FindingConfidence:
    return FindingConfidence.HIGH if required else FindingConfidence.MEDIUM


def database_error_finding(
    finding_id: str,
    title: str,
    reasons: list[str],
    config_path: Path,
    *,
    required: bool,
    confidence: FindingConfidence = FindingConfidence.HIGH,
    principal: str | None = None,
    semantic_ir: dict[str, Any] | None = None,
    sql: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    regression_case: RegressionCase | None = None,
) -> ScanFinding:
    return finding(
        finding_id,
        title,
        database_error_severity(required),
        confidence,
        "database",
        WitnessClass.OVER_RESTRICTIVE,
        EvidenceLevel.REAL_DB,
        reasons,
        config_path,
        principal=principal,
        semantic_ir=semantic_ir,
        sql=sql,
        source=source,
        metadata=metadata,
        regression_case=regression_case,
    )


def adapter_finding(
    finding_id: str,
    title: str,
    reasons: list[str],
    source: str,
    config_path: Path,
    surface: str,
    witness_class: WitnessClass = WitnessClass.OVER_PERMISSIVE,
    severity: FindingSeverity = FindingSeverity.WARNING,
    confidence: FindingConfidence = FindingConfidence.MEDIUM,
    metadata: dict[str, Any] | None = None,
) -> ScanFinding:
    return finding(
        finding_id,
        title,
        severity,
        confidence,
        surface,
        witness_class,
        EvidenceLevel.IMPORTED_TRACE,
        reasons,
        config_path,
        source=source,
        metadata=metadata or {},
    )


def adapter_value_findings(
    values: list[Any],
    id_prefix: str,
    title: str,
    reason_template: str,
    source: str,
    config_path: Path,
    surface: str,
    severity: FindingSeverity = FindingSeverity.WARNING,
    confidence: FindingConfidence = FindingConfidence.MEDIUM,
) -> list[ScanFinding]:
    return [
        adapter_finding(
            f"{id_prefix}_{value}",
            title,
            [reason_template.format(value=value)],
            source,
            config_path,
            surface,
            severity=severity,
            confidence=confidence,
        )
        for value in values
    ]


def imported_trace_finding(
    finding_id: str,
    title: str,
    severity: FindingSeverity,
    confidence: FindingConfidence,
    surface: str,
    witness_class: WitnessClass,
    reasons: list[str],
    config_path: Path,
    trace: ImportedTrace,
    metadata: dict[str, Any] | None = None,
) -> ScanFinding:
    return finding(
        finding_id,
        title,
        severity,
        confidence,
        surface,
        witness_class,
        EvidenceLevel.IMPORTED_TRACE,
        reasons,
        config_path,
        principal=trace.principal,
        semantic_ir=semantic_query_dump(trace.semantic_ir),
        sql=trace.sql,
        source=trace.source,
        regression_case=trace.regression_case,
        metadata=metadata,
    )


def finding(
    finding_id: str,
    title: str,
    severity: FindingSeverity,
    confidence: FindingConfidence,
    surface: str,
    witness_class: WitnessClass,
    evidence_level: EvidenceLevel,
    reasons: list[str],
    config_path: Path,
    principal: str | None = None,
    semantic_ir: dict[str, Any] | None = None,
    sql: str | None = None,
    source: str | None = None,
    mutation: str | None = None,
    mutant_status: MutantStatus | None = None,
    regression_case: RegressionCase | None = None,
    metadata: dict[str, Any] | None = None,
) -> ScanFinding:
    return ScanFinding(
        id=safe_identifier(finding_id),
        title=title,
        severity=severity,
        confidence=confidence,
        surface=cast(SurfaceName, surface),
        witness_class=witness_class,
        evidence_level=evidence_level,
        reasons=reasons,
        principal=principal,
        semantic_ir=semantic_ir,
        sql=sql,
        source=source,
        mutation=mutation,
        mutant_status=mutant_status,
        regression_case=regression_case,
        reproducible_command=f"policystrata scan --config {config_path}",
        metadata=metadata or {},
    )


def sql_preserves_tenant_scope(domain: str, policy: Policy, principal_id: str, sql: str) -> bool:
    principal = policy.principals.get(principal_id)
    if principal is None:
        return False
    lowered = normalize_sql(sql)
    scope_column = normalize_sql(tenant_column(domain))
    if scope_column not in lowered:
        return False
    return any(normalize_sql(str(tenant_id)) in lowered for tenant_id in principal.tenant_ids)


def tenant_scope_reason(domain: str, policy: Policy, principal_id: str) -> str:
    principal = policy.principals.get(principal_id)
    tenants = [] if principal is None else principal.tenant_ids
    return f"expected SQL to include {tenant_column(domain)} scoped to one of {tenants}"


def sql_mentions_policy_metric(policy: Policy, metric_or_alias: str, sql: str) -> bool:
    metric_name = PolicyOracle(policy).resolve_metric(metric_or_alias)
    metric = policy.metrics.get(metric_name)
    if metric is None:
        return False
    normalized_sql = normalize_sql(sql)
    if normalize_sql(metric.expression) in normalized_sql:
        return True
    return any(normalize_sql(column) in normalized_sql for column in metric.columns)


def normalize_sql(sql: str) -> str:
    return re.sub(r"[^a-z0-9_.]+", "", sql.lower())


def decide_gate(findings: list[ScanFinding], config: ScanConfig) -> GateDecision:
    failing: list[str] = []
    if config.gate.fail_on_high_confidence:
        for item in findings:
            if item.severity == FindingSeverity.CRITICAL and item.confidence == FindingConfidence.HIGH:
                failing.append(item.id)
                continue
            if (
                item.severity == FindingSeverity.HIGH
                and item.confidence == FindingConfidence.HIGH
                and item.witness_class
                in {
                    WitnessClass.OVER_PERMISSIVE,
                    WitnessClass.LOWERING_VIOLATION,
                    WitnessClass.SEMANTIC_DRIFT,
                    WitnessClass.UNSAFE_RELEASE,
                }
            ):
                failing.append(item.id)
    if failing:
        return GateDecision(
            outcome=GateOutcome.FAIL,
            reasons=["high-confidence policy drift findings exceed the configured gate"],
            failing_findings=failing,
        )
    if any(item.severity in {FindingSeverity.WARNING, FindingSeverity.HIGH} for item in findings):
        return GateDecision(outcome=GateOutcome.WARN, reasons=["scanner produced warning-level findings"])
    return GateDecision(outcome=GateOutcome.PASS, reasons=["no gateable findings"])


def build_summary(
    findings: list[ScanFinding],
    gate: GateOutcome,
    mutant_statuses: Counter[str],
    evidence_exercised: Counter[str] | None = None,
) -> ScanSummary:
    evidence_levels = Counter(item.evidence_level.value for item in findings)
    regression_cases = Counter(
        item.regression_case.value for item in findings if item.regression_case is not None
    )
    high_confidence_failures = sum(
        1
        for item in findings
        if item.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
        and item.confidence == FindingConfidence.HIGH
    )
    warnings = sum(1 for item in findings if item.severity == FindingSeverity.WARNING)
    infos = sum(1 for item in findings if item.severity == FindingSeverity.INFO)
    return ScanSummary(
        total_findings=len(findings),
        high_confidence_failures=high_confidence_failures,
        warnings=warnings,
        infos=infos,
        gate=gate,
        evidence_exercised=dict(sorted((evidence_exercised or Counter()).items())),
        evidence_levels=dict(sorted(evidence_levels.items())),
        mutant_statuses=dict(sorted(mutant_statuses.items())),
        regression_cases=dict(sorted(regression_cases.items())),
    )


def exercised_evidence_levels(
    config: ScanConfig,
    policy: Policy,
    imported_traces: list[ImportedTrace],
    database_adapter: PostgresAdapter | None,
    mutant_statuses: Counter[str],
) -> Counter[str]:
    exercised: Counter[str] = Counter()
    if config.dbt.files:
        exercised[EvidenceLevel.IMPORTED_TRACE.value] += len(config.dbt.files)
    if imported_traces:
        exercised[EvidenceLevel.IMPORTED_TRACE.value] += len(imported_traces)
    fuzz_count = sum(mutant_statuses.values())
    if fuzz_count:
        exercised[EvidenceLevel.PROPERTY_GENERATED.value] += fuzz_count
    if database_adapter is not None:
        real_db_checks = len(config.database.rls_checks) + len(config.database.state_assertions)
        real_db_checks += count_imported_trace_database_comparisons(config, policy, imported_traces)
        if real_db_checks:
            exercised[EvidenceLevel.REAL_DB.value] += real_db_checks
    return exercised


def count_imported_trace_database_comparisons(
    config: ScanConfig,
    policy: Policy,
    imported_traces: list[ImportedTrace],
) -> int:
    if not config.database.execute_imported_sql:
        return 0
    oracle = PolicyOracle(policy)
    return sum(
        1
        for trace in imported_traces
        if trace.semantic_ir is not None
        and (canonical := authorize_imported_trace(oracle, trace)) is not None
        and canonical.allowed
    )


def assign_witness_paths(
    findings: list[ScanFinding],
    witness_dir: Path,
    output_dir: Path,
) -> list[ScanFinding]:
    seen: Counter[str] = Counter()
    assigned: list[ScanFinding] = []
    for item in findings:
        seen[item.id] += 1
        unique_id = item.id if seen[item.id] == 1 else safe_identifier(f"{item.id}_{seen[item.id]}")
        path = witness_dir / f"{unique_id}.json"
        updated = item.model_copy(
            update={"id": unique_id, "witness_path": str(path.relative_to(output_dir))}
        )
        path.write_text(updated.model_dump_json(indent=2) + "\n", encoding="utf-8")
        assigned.append(updated)
    return assigned


def write_scan_outputs(result: ScanResult, output_dir: Path, config: ScanConfig) -> None:
    (output_dir / SCAN_OUTPUT_FILES["scan"]).write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / SCAN_OUTPUT_FILES["summary"]).write_text(
        result.summary.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / SCAN_OUTPUT_FILES["findings"]).open("w", encoding="utf-8") as handle:
        for item in result.findings:
            handle.write(item.model_dump_json() + "\n")
    (output_dir / SCAN_OUTPUT_FILES["report"]).write_text(render_report(result), encoding="utf-8")
    if config.sarif or config.database.sarif:
        (output_dir / "scan.sarif").write_text(
            json.dumps(render_sarif(result), indent=2) + "\n",
            encoding="utf-8",
        )


def render_report(result: ScanResult) -> str:
    exercised_rows = [
        [level, str(count)] for level, count in sorted(result.summary.evidence_exercised.items())
    ]
    if not exercised_rows:
        exercised_rows = [["-", "0"]]
    finding_rows = [
        [
            item.id,
            item.severity.value,
            item.confidence.value,
            item.surface,
            item.witness_class.value,
            item.evidence_level.value,
            "-" if item.regression_case is None else item.regression_case.value,
            item.title,
        ]
        for item in result.findings
    ]
    if not finding_rows:
        finding_rows = [["-", "-", "-", "-", "-", "-", "-", "No findings"]]
    sections = [
        "# PolicyStrata Scan Report",
        f"Gate: **{result.gate.outcome.value}**",
        "PolicyStrata is a scanner and release gate, not an authorization boundary.",
        "## Evidence Exercised",
        markdown_table(["Evidence level", "Checks"], exercised_rows),
        "## Findings",
        markdown_table(
            ["Finding", "Severity", "Confidence", "Surface", "Class", "Evidence", "Case", "Title"],
            finding_rows,
        ),
    ]
    return "\n\n".join(sections) + "\n"


def render_sarif(result: ScanResult) -> dict[str, Any]:
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {"driver": {"name": "PolicyStrata", "informationUri": "https://github.com/"}},
                "results": [
                    {
                        "ruleId": item.witness_class.value,
                        "level": sarif_level(item.severity),
                        "message": {"text": item.title},
                        "properties": item.model_dump(mode="json"),
                    }
                    for item in result.findings
                ],
            }
        ],
    }


def sarif_level(severity: FindingSeverity) -> str:
    if severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}:
        return "error"
    if severity == FindingSeverity.WARNING:
        return "warning"
    return "note"


def safe_identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._-")
    if not identifier:
        identifier = "finding"
    if not identifier[0].isalnum():
        identifier = f"f_{identifier}"
    return identifier[:128]

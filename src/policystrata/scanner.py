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
from policystrata.models import Policy, SurfaceName, WitnessClass
from policystrata.policy import PolicyOracle
from policystrata.scan_models import (
    EvidenceLevel,
    FindingConfidence,
    FindingSeverity,
    GateDecision,
    GateOutcome,
    MutantStatus,
    ScanConfig,
    ScanFinding,
    ScanResult,
    ScanSummary,
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

    imported_traces = []
    if config.sql_traces.files:
        try:
            trace_paths = resolve_scan_input_paths(config_dir, config.sql_traces.files, "sql trace")
            imported_traces = load_imported_traces(trace_paths)
        except ValueError as exc:
            findings.append(
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
            )

    for trace in imported_traces:
        findings.extend(scan_imported_trace(config, config_path, policy, trace, database_adapter))
        if config.fuzz.enabled:
            fuzzed_traces = fuzz_imported_trace(
                trace,
                policy,
                config.fuzz.seed,
                config.fuzz.max_cases_per_trace,
            )
            for fuzzed in fuzzed_traces:
                status = MutantStatus(fuzzed["status"])
                mutant_statuses[status.value] += 1
                if status == MutantStatus.SURVIVED:
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
                        )
                    )
    if database_adapter is not None:
        findings.extend(scan_rls_checks(config, config_path, database_adapter))

    findings = assign_witness_paths(findings, witness_dir, output_dir)
    gate = decide_gate(findings, config)
    summary = build_summary(findings, gate.outcome, mutant_statuses)
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


def required_input_findings(config: ScanConfig, config_path: Path) -> list[ScanFinding]:
    findings: list[ScanFinding] = []
    required_inputs = set(config.gate.required_inputs)
    checks = {
        "dbt": bool(config.dbt.files),
        "sql_traces": bool(config.sql_traces.files),
        "database": bool(
            config.database.rls_checks or config.database.schema_path or config.database.seed
        ),
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
        for metric in result["missing_policy_metrics"]:
            findings.append(
                adapter_finding(
                    f"dbt_missing_policy_metric_{metric}",
                    "Policy metric is missing from dbt semantic model",
                    [f"metric {metric} exists in policy but not in dbt metrics or measures"],
                    source,
                    config_path,
                    "manifest",
                )
            )
        for metric in result["stale_dbt_metrics"]:
            findings.append(
                adapter_finding(
                    f"dbt_stale_metric_{metric}",
                    "dbt semantic model exposes a stale metric",
                    [f"metric {metric} exists in dbt but not in the PolicyStrata policy"],
                    source,
                    config_path,
                    "manifest",
                )
            )
        for dimension in result["missing_policy_dimensions"]:
            findings.append(
                adapter_finding(
                    f"dbt_missing_policy_dimension_{dimension}",
                    "Policy dimension is missing from dbt semantic model",
                    [f"dimension {dimension} exists in policy but not in dbt dimensions"],
                    source,
                    config_path,
                    "manifest",
                )
            )
        for dimension in result["stale_dbt_dimensions"]:
            findings.append(
                adapter_finding(
                    f"dbt_stale_dimension_{dimension}",
                    "dbt semantic model exposes a stale dimension",
                    [f"dimension {dimension} exists in dbt but not in the PolicyStrata policy"],
                    source,
                    config_path,
                    "manifest",
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
        for dimension in result["sensitive_metadata_missing"]:
            findings.append(
                adapter_finding(
                    f"dbt_sensitive_metadata_missing_{dimension}",
                    "Sensitive dbt dimension lacks sensitivity metadata",
                    [f"sensitive policy dimension {dimension} should be marked sensitive in dbt metadata"],
                    source,
                    config_path,
                    "manifest",
                )
            )
        for model in result["models_missing_lineage"]:
            findings.append(
                adapter_finding(
                    f"dbt_missing_lineage_{model}",
                    "dbt semantic model lacks lineage reference",
                    [f"semantic model {model} has no model/ref lineage field"],
                    source,
                    config_path,
                    "manifest",
                    severity=FindingSeverity.INFO,
                    confidence=FindingConfidence.LOW,
                )
            )
    return findings


def scan_imported_trace(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    trace: Any,
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
            )
        )
        return findings

    canonical = (
        oracle.authorize(trace.principal, trace.semantic_ir)
        if trace.semantic_ir is not None
        else None
    )
    if canonical is not None and not canonical.allowed and trace.release_allowed is True:
        findings.append(
            finding(
                f"unsafe_release_{trace.id}",
                "Unauthorized semantic request was released",
                FindingSeverity.HIGH,
                FindingConfidence.HIGH,
                "release",
                WitnessClass.UNSAFE_RELEASE,
                EvidenceLevel.IMPORTED_TRACE,
                canonical.reasons,
                config_path,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(trace.semantic_ir),
                sql=trace.sql,
                source=trace.source,
            )
        )
    if canonical is not None and not canonical.allowed and trace.release_allowed is not False:
        findings.append(
            finding(
                f"unauthorized_trace_reached_sql_{trace.id}",
                "Unauthorized semantic request reached SQL trace",
                FindingSeverity.HIGH,
                FindingConfidence.HIGH,
                "validator",
                WitnessClass.OVER_PERMISSIVE,
                EvidenceLevel.IMPORTED_TRACE,
                canonical.reasons,
                config_path,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(trace.semantic_ir),
                sql=trace.sql,
                source=trace.source,
            )
        )

    allow_rls_only = bool(trace.expected_policy.get("allow_rls_only"))
    tenant_scope_missing = not sql_preserves_tenant_scope(
        config.domain,
        policy,
        trace.principal,
        trace.sql,
    )
    if not allow_rls_only and tenant_scope_missing:
        findings.append(
            finding(
                f"tenant_scope_missing_{trace.id}",
                "Imported SQL does not preserve the canonical tenant-scope predicate",
                FindingSeverity.HIGH,
                FindingConfidence.HIGH,
                "compiler",
                WitnessClass.LOWERING_VIOLATION,
                EvidenceLevel.IMPORTED_TRACE,
                [tenant_scope_reason(config.domain, policy, trace.principal)],
                config_path,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(trace.semantic_ir),
                sql=trace.sql,
                source=trace.source,
            )
        )

    if (
        canonical is not None
        and canonical.allowed
        and trace.semantic_ir is not None
        and not sql_mentions_policy_metric(policy, trace.semantic_ir.metric, trace.sql)
    ):
        findings.append(
            finding(
                f"metric_expression_unobserved_{trace.id}",
                "Imported SQL does not visibly reference the canonical policy metric expression",
                FindingSeverity.WARNING,
                FindingConfidence.MEDIUM,
                "compiler",
                WitnessClass.SEMANTIC_DRIFT,
                EvidenceLevel.IMPORTED_TRACE,
                ["static SQL inspection could not match the query to the canonical metric expression"],
                config_path,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(trace.semantic_ir),
                sql=trace.sql,
                source=trace.source,
            )
        )
    if (
        database_adapter is not None
        and config.database.execute_imported_sql
        and trace.semantic_ir is not None
        and canonical is not None
        and canonical.allowed
    ):
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


def scan_imported_trace_on_database(
    config: ScanConfig,
    config_path: Path,
    policy: Policy,
    trace: Any,
    app: PostgresAdapter,
) -> list[ScanFinding]:
    principal = policy.principals[trace.principal]
    tenant_id = imported_trace_tenant_id(trace, principal.tenant_ids)
    try:
        imported_rows = app.query(trace.sql, tenant_id=tenant_id)
    except DATABASE_QUERY_EXCEPTIONS as exc:
        return [
            database_error_finding(
                f"imported_sql_execution_error_{trace.id}",
                "Imported SQL could not be executed against the configured PostgreSQL fixture",
                [str(exc)],
                config_path,
                required=config.database.required,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(trace.semantic_ir),
                sql=trace.sql,
                source=trace.source,
                metadata={"tenant_id": tenant_id},
            )
        ]

    canonical_sql = compile_query(
        policy,
        principal,
        trace.semantic_ir,
        domain=config.domain,
    ).sql
    try:
        canonical_rows = app.query(canonical_sql, tenant_id=tenant_id)
    except DATABASE_QUERY_EXCEPTIONS as exc:
        return [
            database_error_finding(
                f"canonical_sql_execution_error_{trace.id}",
                "Canonical compiler SQL could not be executed against the configured PostgreSQL fixture",
                [str(exc)],
                config_path,
                required=config.database.required,
                principal=trace.principal,
                semantic_ir=semantic_query_dump(trace.semantic_ir),
                sql=canonical_sql,
                source=trace.source,
                metadata={"tenant_id": tenant_id, "imported_sql": trace.sql},
            )
        ]

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
            semantic_ir=semantic_query_dump(trace.semantic_ir),
            sql=trace.sql,
            source=trace.source,
            metadata={
                "tenant_id": tenant_id,
                "canonical_sql": canonical_sql,
                "imported_rows": normalize_rows(imported_rows),
                "canonical_rows": normalize_rows(canonical_rows),
            },
        )
    ]


def imported_trace_tenant_id(trace: Any, principal_tenant_ids: list[str]) -> str | None:
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
) -> ScanSummary:
    evidence_levels = Counter(item.evidence_level.value for item in findings)
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
        evidence_levels=dict(sorted(evidence_levels.items())),
        mutant_statuses=dict(sorted(mutant_statuses.items())),
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
    finding_rows = [
        [
            item.id,
            item.severity.value,
            item.confidence.value,
            item.surface,
            item.witness_class.value,
            item.evidence_level.value,
            item.title,
        ]
        for item in result.findings
    ]
    if not finding_rows:
        finding_rows = [["-", "-", "-", "-", "-", "-", "No findings"]]
    sections = [
        "# PolicyStrata Scan Report",
        f"Gate: **{result.gate.outcome.value}**",
        "PolicyStrata is a scanner and release gate, not an authorization boundary.",
        markdown_table(
            ["Finding", "Severity", "Confidence", "Surface", "Class", "Evidence", "Title"],
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

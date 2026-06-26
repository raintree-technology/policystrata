from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from policystrata.models import (
    MAX_SAFE_IDENTIFIER_LENGTH,
    SAFE_IDENTIFIER_PATTERN,
    SemanticQuery,
    SurfaceName,
    WitnessClass,
)


class EvidenceLevel(str, Enum):
    DETERMINISTIC_FIXTURE = "deterministic_fixture"
    PROPERTY_GENERATED = "property_generated"
    IMPORTED_TRACE = "imported_trace"
    REAL_DB = "real_db"
    BLINDED_SUITE = "blinded_suite"


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class FindingConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GateOutcome(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class MutantStatus(str, Enum):
    KILLED = "killed"
    SURVIVED = "survived"
    EQUIVALENT = "equivalent"
    STILLBORN = "stillborn"


class RegressionCase(str, Enum):
    FAIL_TO_PASS = "fail_to_pass"
    PASS_TO_PASS = "pass_to_pass"
    CONTAIN_TO_CONTAIN = "contain_to_contain"
    DENY_TO_DENY = "deny_to_deny"
    ALLOW_TO_ALLOW = "allow_to_allow"
    UNCLASSIFIED = "unclassified"


AssertionValue = str | int | float | bool | None


class DbtScanConfig(BaseModel):
    files: list[str] = Field(default_factory=list)
    required: bool = False


class SqlTraceConfig(BaseModel):
    files: list[str] = Field(default_factory=list)
    required: bool = False


class FileInputConfig(BaseModel):
    files: list[str] = Field(default_factory=list)
    required: bool = False


class TenancyScanConfig(BaseModel):
    canonical_predicates: list[str] = Field(default_factory=list)
    tenant_columns: list[str] = Field(default_factory=list)


class RlsCheckConfig(BaseModel):
    id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN, max_length=MAX_SAFE_IDENTIFIER_LENGTH)
    sql: str
    tenant_id: str | None = None
    expected_rows: int | None = Field(default=None, ge=0)
    expected_tenant_ids: list[str] = Field(default_factory=list)
    tenant_column: str = "tenant_id"
    required: bool = False


class StateAssertionConfig(BaseModel):
    id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN, max_length=MAX_SAFE_IDENTIFIER_LENGTH)
    sql: str
    tenant_id: str | None = None
    expected_rows: int | None = Field(default=None, ge=0)
    expect_empty: bool = False
    require_columns: list[str] = Field(default_factory=list)
    forbidden_columns: list[str] = Field(default_factory=list)
    allowed_values: dict[str, list[AssertionValue]] = Field(default_factory=dict)
    forbidden_values: dict[str, list[AssertionValue]] = Field(default_factory=dict)
    required: bool = False
    regression_case: RegressionCase = RegressionCase.PASS_TO_PASS


class DatabaseScanConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["postgres"] = "postgres"
    required: bool = False
    start_docker: bool = False
    compose_file: str | None = None
    compose_service: str = "postgres"
    startup_timeout_seconds: float = Field(default=30.0, gt=0)
    admin_url: str | None = None
    app_url: str | None = None
    schema_path: str | None = Field(default=None, alias="schema")
    seed: str | None = None
    execute_imported_sql: bool = True
    sarif: bool = False
    rls_checks: list[RlsCheckConfig] = Field(default_factory=list)
    state_assertions: list[StateAssertionConfig] = Field(default_factory=list)


class FuzzConfig(BaseModel):
    enabled: bool = True
    seed: int = 1729
    max_cases_per_trace: int = Field(default=8, ge=0, le=50)


class GateConfig(BaseModel):
    fail_on_high_confidence: bool = True
    required_inputs: list[Literal["dbt", "sql_traces", "database", "state_assertions"]] = Field(
        default_factory=list
    )


class ScanConfig(BaseModel):
    version: int = 1
    domain: str = "support_saas"
    domain_path: str | None = None
    output: str | None = None
    sarif: bool = False
    dbt: DbtScanConfig = Field(default_factory=DbtScanConfig)
    sql_traces: SqlTraceConfig = Field(default_factory=SqlTraceConfig)
    policy_docs: FileInputConfig = Field(default_factory=FileInputConfig)
    prompt_manifests: FileInputConfig = Field(default_factory=FileInputConfig)
    source_maps: FileInputConfig = Field(default_factory=FileInputConfig)
    tenancy: TenancyScanConfig = Field(default_factory=TenancyScanConfig)
    database: DatabaseScanConfig = Field(default_factory=DatabaseScanConfig)
    fuzz: FuzzConfig = Field(default_factory=FuzzConfig)
    gate: GateConfig = Field(default_factory=GateConfig)


class ImportedTrace(BaseModel):
    id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN, max_length=MAX_SAFE_IDENTIFIER_LENGTH)
    principal: str
    sql: str
    tenant_ids: list[str] = Field(default_factory=list)
    semantic_ir: SemanticQuery | None = None
    source: str = "imported_trace"
    timestamp: str | None = None
    release_allowed: bool | None = None
    evidence_level: EvidenceLevel = EvidenceLevel.IMPORTED_TRACE
    expected_policy: dict[str, Any] = Field(default_factory=dict)
    regression_case: RegressionCase = RegressionCase.UNCLASSIFIED


class ScanFinding(BaseModel):
    id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN, max_length=MAX_SAFE_IDENTIFIER_LENGTH)
    title: str
    severity: FindingSeverity
    confidence: FindingConfidence
    surface: SurfaceName
    witness_class: WitnessClass
    evidence_level: EvidenceLevel
    reasons: list[str] = Field(default_factory=list)
    principal: str | None = None
    semantic_ir: dict[str, Any] | None = None
    sql: str | None = None
    source: str | None = None
    mutation: str | None = None
    mutant_status: MutantStatus | None = None
    regression_case: RegressionCase | None = None
    reproducible_command: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    witness_path: str | None = None
    what_changed: str | None = None
    owner: SurfaceName | None = None
    probable_fix: str | None = None
    minimal_repro_trace: str | None = None
    ci_gate_command: str | None = None


class GateDecision(BaseModel):
    outcome: GateOutcome
    reasons: list[str] = Field(default_factory=list)
    failing_findings: list[str] = Field(default_factory=list)


class ScanSummary(BaseModel):
    total_findings: int
    high_confidence_failures: int
    warnings: int
    infos: int
    gate: GateOutcome
    evidence_exercised: dict[str, int] = Field(default_factory=dict)
    evidence_levels: dict[str, int]
    mutant_statuses: dict[str, int]
    regression_cases: dict[str, int] = Field(default_factory=dict)
    integration_readiness: dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    version: str = "scan.v1"
    domain: str
    config_path: str
    output_dir: str
    gate: GateDecision
    summary: ScanSummary
    findings: list[ScanFinding]
    artifacts: dict[str, str]

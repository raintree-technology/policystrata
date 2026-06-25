from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

SurfaceName = Literal["manifest", "grammar", "validator", "compiler", "database", "release"]
EvidenceLevelName = Literal[
    "deterministic_fixture",
    "property_generated",
    "imported_trace",
    "real_db",
    "blinded_suite",
]
SuiteProvenance = Literal[
    "hand_authored",
    "generated",
    "secondary_generated",
    "externally_authored",
    "incident_reconstruction",
]
SurfaceMode = Literal[
    "capability_exposure",
    "intent_space",
    "semantic_validation",
    "sql_lowering",
    "database_containment",
    "output_release",
]
SAFE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
MAX_SAFE_IDENTIFIER_LENGTH = 128


class WitnessClass(str, Enum):
    CLEAN = "clean"
    OVER_PERMISSIVE = "over_permissive"
    OVER_RESTRICTIVE = "over_restrictive"
    LOWERING_VIOLATION = "lowering_violation"
    SEMANTIC_DRIFT = "semantic_drift"
    UNSAFE_RELEASE = "unsafe_release"


class Decision(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)


class RolePolicy(BaseModel):
    allowed_metrics: list[str]
    allowed_dimensions: list[str]
    allowed_time_ranges: list[str]
    max_rows: int
    max_cost: int
    aggregate_only: bool = True


class Principal(BaseModel):
    id: str
    role: str
    tenant_ids: list[str]


class MetricPolicy(BaseModel):
    expression: str
    table: str
    columns: list[str]
    allowed_roles: list[str]
    aliases: list[str] = Field(default_factory=list)
    grain: str = "tenant"
    cost: int = 10


class DimensionPolicy(BaseModel):
    column: str
    allowed_roles: list[str]
    sensitive: bool = False
    cost: int = 1


class Policy(BaseModel):
    version: str
    principals: dict[str, Principal]
    roles: dict[str, RolePolicy]
    metrics: dict[str, MetricPolicy]
    dimensions: dict[str, DimensionPolicy]


class SurfaceVersions(BaseModel):
    manifest: str
    grammar: str
    validator: str
    compiler: str
    database: str
    release: str

    def as_dict(self) -> dict[str, str]:
        return self.model_dump()


class SurfaceContract(BaseModel):
    mode: SurfaceMode
    responsibilities: list[str]
    accepts_obligations: list[str] = Field(default_factory=list)
    emits_obligations: list[str] = Field(default_factory=list)


class SurfaceConfig(BaseModel):
    versions: SurfaceVersions
    contracts: dict[str, SurfaceContract]
    transition_obligations: list[str] = Field(default_factory=list)

    def version_dict(self) -> dict[str, str]:
        return self.versions.as_dict()

    def contract_dict(self) -> dict[str, dict[str, Any]]:
        return {name: contract.model_dump() for name, contract in self.contracts.items()}

    def responsibility_dict(self) -> dict[str, list[str]]:
        return {name: contract.responsibilities for name, contract in self.contracts.items()}


class SemanticQuery(BaseModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    time_range: str = "last_month"
    grain: str = "month"
    limit: int = Field(default=100, ge=1, strict=True)

    def normalized(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "dimensions": sorted(self.dimensions),
            "filters": dict(sorted(self.filters.items())),
            "time_range": self.time_range,
            "grain": self.grain,
            "limit": self.limit,
        }


class MutationSpec(BaseModel):
    id: str
    family: str
    affected_surface: SurfaceName
    witness_class: WitnessClass
    description: str
    containment_layer: SurfaceName | None = None
    requires_db_containment: bool = False


class Task(BaseModel):
    id: str = Field(pattern=SAFE_IDENTIFIER_PATTERN, max_length=MAX_SAFE_IDENTIFIER_LENGTH)
    domain: str = "support_saas"
    principal: str
    request: str
    policy_version: str
    surface_versions: SurfaceVersions
    mutation: str
    semantic_query: SemanticQuery
    expected_witness_class: WitnessClass
    expected_localized_surface: SurfaceName
    expected_containment_layer: SurfaceName | None = None


class SuiteMetadata(BaseModel):
    provenance: SuiteProvenance = "hand_authored"
    evidence_level: EvidenceLevelName = "deterministic_fixture"
    detector_frozen: bool = False
    detector_freeze_id: str | None = None
    authored_after_detector_freeze: bool = False
    notes: list[str] = Field(default_factory=list)


class CompileResult(BaseModel):
    sql: str
    estimated_cost: int
    includes_tenant_predicate: bool
    metric_expression: str
    join_grain: str
    time_semantics: str


class Trace(BaseModel):
    task_id: str
    domain: str
    request: str
    principal: str
    mutation: str
    semantic_ir: SemanticQuery
    policy_version: str
    surface_versions: dict[str, str]
    canonical_decision: Decision
    surface_decisions: dict[str, Decision]
    surface_contracts: dict[str, SurfaceContract] = Field(default_factory=dict)
    contract_decisions: dict[str, Decision] = Field(default_factory=dict)
    transition_obligations: list[str] = Field(default_factory=list)
    compiled_sql: str
    db_result: dict[str, Any]
    release_decision: Decision
    witness_class: WitnessClass
    expected_witness_class: WitnessClass
    localized_surface: SurfaceName
    expected_localized_surface: SurfaceName
    containment_layer: SurfaceName | None = None
    expected_containment_layer: SurfaceName | None = None
    semantic_difference: bool = False
    witness_path: str | None = None
    latency_ms: float = 0.0
    cost: dict[str, int | float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class Summary(BaseModel):
    total: int
    mutant_kill_rate: float
    over_permissive_rate: float
    over_restrictive_rate: float
    lowering_violation_rate: float
    semantic_drift_rate: float
    unsafe_release_rate: float
    containment_rate: float
    localization_accuracy: float
    expected_class_accuracy: float
    minimized_witness_count: int
    avg_latency_ms: float
    cost: dict[str, int | float]

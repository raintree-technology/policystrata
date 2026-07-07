from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field

from policystrata.models import CompatModel, InputModel, SafeIdentifier

RuntimeDecisionAction = Literal[
    "allow",
    "deny",
    "redact",
    "require_approval",
    "quarantine",
    "log_only",
]
PolicyLayer = Literal[
    "auth_context",
    "prompt",
    "plan",
    "retrieval",
    "memory",
    "tool_call",
    "browser_action",
    "code_execution",
    "sql",
    "database_rule",
    "schema_binding",
    "transformation",
    "output_filter",
    "egress",
    "trace",
]


class RuntimeActor(CompatModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_id: str | None = Field(default=None, alias="userId")
    tenant_id: str | None = Field(default=None, alias="tenantId")
    role: str | None = None
    scopes: list[str] = Field(default_factory=list)
    entitlements: list[str] = Field(default_factory=list)
    delegated_by: str | None = Field(default=None, alias="delegatedBy")
    service_account: str | None = Field(default=None, alias="serviceAccount")
    purpose: str | None = None
    region: str | None = None


class RuntimeResource(CompatModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    kind: str
    name: str
    id: str | None = None
    uri: str | None = None
    tenant_id: str | None = Field(default=None, alias="tenantId")
    tags: list[str] = Field(default_factory=list)
    entitlement: str | None = None
    required_entitlements: list[str] = Field(default_factory=list, alias="requiredEntitlements")
    version: str | None = None
    region: str | None = None


class RuntimeControl(CompatModel):
    id: SafeIdentifier
    mode: Literal["release_gate", "runtime_enforcement", "monitor"] | None = None
    objective: str | None = None


class RuntimeDecision(InputModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    action: RuntimeDecisionAction
    reason: str
    control: RuntimeControl | None = None
    policy_refs: list[str] = Field(default_factory=list, alias="policyRefs")
    redactions: list[str] = Field(default_factory=list)
    approval_ref: str | None = Field(default=None, alias="approvalRef")


class RuntimeExpectedDecision(InputModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    allowed: bool | None = None
    action: RuntimeDecisionAction | None = None
    control_id: SafeIdentifier | None = Field(default=None, alias="controlId")
    reason: str | None = None
    reason_includes: list[str] = Field(default_factory=list, alias="reasonIncludes")
    redactions: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list, alias="policyRefs")


class RuntimeAgent(InputModel):
    key: SafeIdentifier
    name: str | None = None
    kind: str | None = None
    version: str | None = None


class RuntimeEvent(InputModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion")
    event_id: SafeIdentifier = Field(alias="eventId")
    project: str
    observed_at: str = Field(alias="observedAt")
    agent: RuntimeAgent
    layer: PolicyLayer
    operation: str
    summary: str
    release_candidate: str | None = Field(default=None, alias="releaseCandidate")
    environment: str | None = None
    decision: RuntimeDecision | None = None
    expected_decision: RuntimeExpectedDecision | None = Field(default=None, alias="expectedDecision")
    actor: RuntimeActor | None = None
    resource: RuntimeResource | None = None
    data_classes: list[str] = Field(default_factory=list, alias="dataClasses")
    policy_refs: list[str] = Field(default_factory=list, alias="policyRefs")
    control: RuntimeControl | None = None
    trace_id: str | None = Field(default=None, alias="traceId")
    span_id: str | None = Field(default=None, alias="spanId")
    event_ref: str | None = Field(default=None, alias="eventRef")
    witness_refs: list[str] = Field(default_factory=list, alias="witnessRefs")
    payload_hash: str | None = Field(default=None, alias="payloadHash")
    artifact_refs: list[str] = Field(default_factory=list, alias="artifactRefs")
    finding_ids: list[str] = Field(default_factory=list, alias="findingIds")
    payload: dict[str, Any] = Field(default_factory=dict)


class RuntimeEventBatch(InputModel):
    events: list[RuntimeEvent]

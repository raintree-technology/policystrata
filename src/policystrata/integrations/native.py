from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

NativeIntegrationProvider = Literal[
    "github",
    "vercel",
    "datadog",
    "snowflake",
    "slack",
    "jira",
    "aws",
    "gcp",
    "azure",
]

NATIVE_INTEGRATION_PROVIDERS: tuple[NativeIntegrationProvider, ...] = (
    "github",
    "vercel",
    "datadog",
    "snowflake",
    "slack",
    "jira",
    "aws",
    "gcp",
    "azure",
)

ProviderLayer = Literal["trace", "egress", "sql"]
ProviderDecision = Literal[
    "allow",
    "deny",
    "redact",
    "require_approval",
    "quarantine",
    "log_only",
]
ProviderSeverity = Literal["info", "warning", "fail", "blocker"]
ProviderDefault = tuple[str, ProviderLayer, ProviderDecision, ProviderSeverity]


@dataclass(frozen=True)
class NativeIntegrationConnection:
    provider: NativeIntegrationProvider
    project: str
    connection_id: str
    display_name: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    secret_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeIntegrationEvidence:
    provider: NativeIntegrationProvider
    connection_id: str
    external_id: str
    event_type: str
    observed_at: str
    severity: ProviderSeverity
    decision: ProviderDecision
    layer: ProviderLayer
    operation: str
    summary: str
    evidence_refs: tuple[str, ...]
    payload: dict[str, Any]

    def to_runtime_event(self, project: str) -> dict[str, Any]:
        safe_event_id = self.external_id.replace(":", "-")
        return {
            "schemaVersion": "0.2.0",
            "eventId": f"integration-{safe_event_id}",
            "project": project,
            "observedAt": self.observed_at,
            "agent": {
                "key": f"{self.provider}-integration",
                "name": f"{self.provider} integration",
                "kind": "integration",
            },
            "layer": self.layer,
            "operation": self.operation,
            "summary": self.summary,
            "decision": {
                "action": self.decision,
                "reason": f"{self.provider} provider evidence",
                "control": {
                    "id": f"{self.provider}.native_integration",
                    "mode": "release_gate",
                    "objective": "Use native provider evidence in Clearance gates",
                },
            },
            "provider": self.provider,
            "integrationConnectionId": self.connection_id,
            "externalRefs": [
                {
                    "provider": self.provider,
                    "ref": ref,
                    "kind": "evidence",
                    "connectionId": self.connection_id,
                }
                for ref in self.evidence_refs
            ],
            "artifactRefs": list(self.evidence_refs),
            "payloadHash": _sha256_json(self.payload),
        }


_PROVIDER_DEFAULTS: dict[NativeIntegrationProvider, ProviderDefault] = {
    "github": ("github.check_gate", "trace", "allow", "info"),
    "vercel": ("vercel.deployment_gate", "egress", "allow", "info"),
    "datadog": ("datadog.monitor_signal", "trace", "require_approval", "warning"),
    "snowflake": ("snowflake.data_policy_signal", "sql", "require_approval", "warning"),
    "slack": ("slack.approval_channel", "trace", "require_approval", "info"),
    "jira": ("jira.workflow_gate", "trace", "require_approval", "info"),
    "aws": ("aws.control_plane_signal", "egress", "require_approval", "warning"),
    "gcp": ("gcp.control_plane_signal", "egress", "require_approval", "warning"),
    "azure": ("azure.control_plane_signal", "egress", "require_approval", "warning"),
}


def collect_native_integration_evidence(
    connection: NativeIntegrationConnection,
) -> list[NativeIntegrationEvidence]:
    event_type, layer, decision, severity = _PROVIDER_DEFAULTS[connection.provider]
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = {
        "storageMode": "metadata_only",
        "provider": connection.provider,
        "connectionId": connection.connection_id,
        "configKeys": sorted(connection.config),
        "secretKeys": sorted(connection.secret_keys),
        "displayName": connection.display_name,
    }
    external_id = f"{connection.provider}:{connection.connection_id}:{_sha256_json(payload)[:16]}"
    evidence_ref = f"integration://{connection.provider}/{connection.connection_id}"
    return [
        NativeIntegrationEvidence(
            provider=connection.provider,
            connection_id=connection.connection_id,
            external_id=external_id,
            event_type=event_type,
            observed_at=observed_at,
            severity=severity,
            decision=decision,
            layer=layer,
            operation=event_type,
            summary=f"{connection.provider} evidence synchronized for {connection.project}",
            evidence_refs=(evidence_ref,),
            payload=payload,
        )
    ]


def native_evidence_runtime_payload(
    connection: NativeIntegrationConnection,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "events": [
            evidence.to_runtime_event(connection.project)
            for evidence in collect_native_integration_evidence(connection)
        ]
    }


def _sha256_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

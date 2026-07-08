"""Optional adapters for external fixtures and native provider evidence."""

from policystrata.integrations.native import (
    NATIVE_INTEGRATION_PROVIDERS,
    NativeIntegrationConnection,
    NativeIntegrationEvidence,
    collect_native_integration_evidence,
    native_evidence_runtime_payload,
)

__all__ = [
    "NATIVE_INTEGRATION_PROVIDERS",
    "NativeIntegrationConnection",
    "NativeIntegrationEvidence",
    "collect_native_integration_evidence",
    "native_evidence_runtime_payload",
]

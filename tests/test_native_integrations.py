from __future__ import annotations

from policystrata.integrations.native import NativeIntegrationConnection, native_evidence_runtime_payload
from policystrata.runtime_models import RuntimeEventBatch


def test_native_integration_evidence_emits_runtime_events() -> None:
    payload = native_evidence_runtime_payload(
        NativeIntegrationConnection(
            provider="snowflake",
            project="governed-agent",
            connection_id="conn_snowflake",
            config={"accountUrl": "https://example.snowflakecomputing.com"},
            secret_keys=("privateKey",),
        )
    )

    batch = RuntimeEventBatch.model_validate(payload)
    event = batch.events[0]

    assert event.provider == "snowflake"
    assert event.integration_connection_id == "conn_snowflake"
    assert event.layer == "sql"
    assert event.decision is not None
    assert event.decision.action == "require_approval"
    assert event.external_refs[0].ref == "integration://snowflake/conn_snowflake"

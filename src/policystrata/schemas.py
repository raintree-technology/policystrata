from __future__ import annotations

from pydantic import BaseModel

from policystrata.models import Trace
from policystrata.runtime_models import RuntimeDecision, RuntimeEvent, RuntimeEventBatch
from policystrata.scan_models import ImportedTrace, ScanConfig, ScanResult

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_IDS = {
    "scan-config": "https://policystrata.dev/schemas/scan-config.schema.json",
    "imported-trace": "https://policystrata.dev/schemas/imported-trace.schema.json",
    "trace": "https://policystrata.dev/schemas/trace.schema.json",
    "scan-result": "https://policystrata.dev/schemas/scan-result.schema.json",
    "runtime-decision": "https://policystrata.dev/schemas/runtime-decision.schema.json",
    "runtime-event": "https://policystrata.dev/schemas/runtime-event.schema.json",
    "runtime-event-batch": "https://policystrata.dev/schemas/runtime-event-batch.schema.json",
}
SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "scan-config": ScanConfig,
    "imported-trace": ImportedTrace,
    "trace": Trace,
    "scan-result": ScanResult,
    "runtime-decision": RuntimeDecision,
    "runtime-event": RuntimeEvent,
    "runtime-event-batch": RuntimeEventBatch,
}
SCHEMA_KINDS = tuple(SCHEMA_MODELS)


def public_schema(kind: str) -> dict[str, object]:
    try:
        model = SCHEMA_MODELS[kind]
    except KeyError as exc:
        raise ValueError(f"unknown schema kind: {kind}") from exc
    schema = model.model_json_schema()
    schema["$schema"] = SCHEMA_DRAFT
    schema["$id"] = SCHEMA_IDS[kind]
    return schema

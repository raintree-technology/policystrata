import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from policystrata.clearance import ClearanceEvidencePack
from policystrata.scan_models import ImportedTrace
from policystrata.schemas import SCHEMA_KINDS, public_schema

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "schemas"
VERSIONED_SCHEMA_FIELDS = {
    "scan-config": ("version", 1),
    "scan-result": ("version", "scan.v1"),
    "runtime-manifest": ("schemaVersion", "policystrata.runtime_manifest.v1"),
    "runtime-event": ("schemaVersion", "0.2.0"),
    "clearance-runner-config": ("schemaVersion", "clearance.runner.v1"),
    "clearance-run": ("schemaVersion", "clearance.run.v1"),
    "clearance-evidence-pack": ("schemaVersion", "clearance.evidence_pack.v1"),
    "clearance-upload": ("schemaVersion", "clearance.upload.v1"),
}


@pytest.mark.parametrize("kind", SCHEMA_KINDS)
def test_public_schema_valid_fixture(kind: str) -> None:
    payload = json.loads((FIXTURE_ROOT / "valid" / f"{kind}.json").read_text(encoding="utf-8"))
    schema = public_schema(kind)

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


@pytest.mark.parametrize("kind", SCHEMA_KINDS)
def test_public_schema_invalid_fixture(kind: str) -> None:
    payload = json.loads((FIXTURE_ROOT / "invalid" / f"{kind}.json").read_text(encoding="utf-8"))
    schema = public_schema(kind)

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)


def test_schema_fixture_set_matches_public_schema_kinds() -> None:
    valid = {path.stem for path in (FIXTURE_ROOT / "valid").glob("*.json")}
    invalid = {path.stem for path in (FIXTURE_ROOT / "invalid").glob("*.json")}

    assert valid == set(SCHEMA_KINDS)
    assert invalid == set(SCHEMA_KINDS)


@pytest.mark.parametrize(("kind", "field", "expected"), [
    (kind, field, expected) for kind, (field, expected) in VERSIONED_SCHEMA_FIELDS.items()
])
def test_versioned_public_schemas_pin_version_field(kind: str, field: str, expected: object) -> None:
    schema = public_schema(kind)
    properties = schema["properties"]
    assert isinstance(properties, dict)
    field_schema = properties[field]
    assert isinstance(field_schema, dict)

    assert field_schema["const"] == expected


def test_forward_compatible_consumers_tolerate_unknown_fields() -> None:
    trace = ImportedTrace.model_validate(
        {
            "id": "trace_1",
            "principal": "analyst",
            "sql": "select 1",
            "futureField": "ignored",
        }
    )
    pack = ClearanceEvidencePack.model_validate(
        {
            "schemaVersion": "clearance.evidence_pack.v1",
            "runId": "clr_123",
            "storageMode": "metadata_only",
            "projectId": "support-bi",
            "runner": {},
            "run": {},
            "decision": {},
            "summary": {},
            "artifactRefs": [],
            "futureField": "ignored",
        }
    )

    assert trace.id == "trace_1"
    assert pack.run_id == "clr_123"

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from policystrata.runtime import (
    authorize,
    authorize_release,
    authorize_tool,
    create_policystrata_authorizer,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "packages/node/test/fixtures/runtime"
SCHEMA_PATH = ROOT / "packages/node/schema/runtime-manifest.schema.json"


def load_json(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_schema() -> object:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def decision_contract(decision: object) -> dict[str, object]:
    assert hasattr(decision, "to_dict")
    raw = decision.to_dict()
    return {
        "allowed": raw["allowed"],
        "reasons": raw["reasons"],
        "action": raw["action"],
        "resource": raw["resource"],
        "normalizedRoles": raw["normalizedRoles"],
        "manifestVersion": raw["manifestVersion"],
        "enforcementMode": raw["enforcementMode"],
    }


def test_runtime_conformance_manifest_validates_against_packaged_schema() -> None:
    manifest = load_json("manifest.json")
    schema = load_schema()
    assert isinstance(manifest, dict)
    assert isinstance(schema, dict)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    validator.validate(manifest)

    with pytest.raises(ValidationError, match="was expected"):
        validator.validate({**manifest, "defaultDecision": "allow"})


def test_runtime_conformance_fixtures_match_python_authorizer() -> None:
    manifest = load_json("manifest.json")
    cases = load_json("cases.json")
    assert isinstance(manifest, dict)
    assert isinstance(cases, list)
    authorizer = create_policystrata_authorizer(manifest)

    for fixture in cases:
        assert isinstance(fixture, dict)
        decision = authorizer.authorize(fixture["input"])
        expected = fixture["expected"]
        assert isinstance(expected, dict)
        assert decision.allowed is expected["allowed"], fixture["name"]
        assert decision.normalized_roles == expected["normalizedRoles"], fixture["name"]
        for expected_reason in expected["reasonIncludes"]:
            assert expected_reason in "\n".join(decision.reasons), fixture["name"]


def test_runtime_top_level_authorize_helper() -> None:
    manifest = load_json("manifest.json")
    cases = load_json("cases.json")
    assert isinstance(manifest, dict)
    assert isinstance(cases, list)

    decision = authorize(manifest, cases[0]["input"])

    assert decision.allowed is True
    assert decision.normalized_roles == ["household_viewer"]


def test_runtime_top_level_authorize_tool_helper() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)

    decision = authorize_tool(
        manifest,
        {
            "toolName": "categorizeTransaction",
            "userId": "user_1",
            "householdId": "household_1",
            "role": "admin",
            "toolKind": "write",
            "allowWriteTools": True,
            "approvalRequiredSatisfied": True,
            "semanticIr": {"metric": "transaction_spend", "dimensions": ["category"]},
            "mode": "enforce",
        },
    )

    assert decision.allowed is True
    assert decision.action == "write"
    assert decision.normalized_role == "household_admin"
    assert decision.enforcement_mode == "enforce"
    assert decision.tool_kind == "write"
    assert decision.user_id == "user_1"
    assert decision.household_id == "household_1"
    assert decision.write_state == "enabled"
    assert decision.approval_state == "satisfied"
    assert decision.decision_point == "execution"


def test_runtime_authorize_tool_exposes_approval_tools_pre_model() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)

    decision = authorize_tool(
        manifest,
        {
            "toolName": "generateTransactionExport",
            "role": "owner",
            "toolKind": "export",
            "decisionPoint": "pre_model",
            "approvalState": "pending",
            "userId": "user_1",
            "householdId": "household_1",
        },
    )

    assert decision.allowed is True
    assert decision.tool_kind == "export"
    assert decision.decision_point == "pre_model"
    assert decision.approval_state == "pending"
    assert decision.write_state == "disabled"
    assert decision.user_id == "user_1"
    assert decision.household_id == "household_1"


def test_runtime_authorize_tool_denies_tool_kind_mismatch() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)

    decision = authorize_tool(
        manifest,
        {
            "toolName": "searchTransactions",
            "role": "owner",
            "toolKind": "write",
        },
    )

    assert decision.allowed is False
    assert "tool kind context write" in "\n".join(decision.reasons)
    assert decision.tool_kind == "read"


def test_runtime_authorize_release_wraps_generic_authorizer() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)
    authorizer = create_policystrata_authorizer(manifest)

    decision = authorizer.authorize_release(
        {
            "subject": {"role": "viewer"},
            "resource": "searchTransactions",
            "boundary": "user",
            "result": {"kind": "aggregate", "rowCount": 12, "containsSensitiveValues": False},
            "lineage": {"sources": ["transactions"], "containsRawRows": False},
            "mode": "enforce",
        }
    )

    assert decision.allowed is True
    assert decision.action == "release"
    assert decision.boundary == "user"
    assert decision.enforcement_mode == "enforce"


def test_runtime_top_level_authorize_release_helper() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)

    decision = authorize_release(
        manifest,
        {
            "subject": {"role": "viewer"},
            "resource": "searchTransactions",
            "boundary": "llm_context",
            "result": {"kind": "aggregate", "rowCount": 12},
            "lineage": {"sources": ["transactions"]},
        },
    )

    assert decision.allowed is False
    assert "release boundary llm_context" in "\n".join(decision.reasons)


def test_runtime_authorize_tool_wraps_generic_authorizer_for_resource_manifests() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)
    authorizer = create_policystrata_authorizer(manifest)

    decision = authorizer.authorize_tool(
        {
            "toolName": "categorizeTransaction",
            "role": "admin",
            "allowWriteTools": True,
            "approvalRequiredSatisfied": True,
            "semanticIr": {"metric": "transaction_spend", "dimensions": ["category"]},
            "mode": "enforce",
        }
    )

    assert decision.allowed is True
    assert decision.action == "write"
    assert decision.normalized_role == "household_admin"
    assert decision.enforcement_mode == "enforce"


def test_runtime_manifests_must_default_to_deny() -> None:
    manifest = load_json("manifest.json")
    assert isinstance(manifest, dict)
    invalid = {**manifest, "defaultDecision": "allow"}

    with pytest.raises(ValueError, match="default to deny"):
        create_policystrata_authorizer(invalid)


def test_python_and_built_node_runtime_match_conformance_fixtures() -> None:
    if shutil.which("node") is None:
        pytest.skip("Node.js is not available for cross-runtime comparison")
    node_runtime = ROOT / "packages/node/dist/src/runtime.js"
    if not node_runtime.exists():
        pytest.skip("Node runtime has not been built; run the Node test/build first")

    manifest = load_json("manifest.json")
    cases = load_json("cases.json")
    assert isinstance(manifest, dict)
    assert isinstance(cases, list)
    authorizer = create_policystrata_authorizer(manifest)
    python_decisions = [
        decision_contract(authorizer.authorize(fixture["input"]))
        for fixture in cases
    ]

    script = f"""
import {{ readFileSync }} from "node:fs";
import {{ createPolicyStrataAuthorizer }} from {json.dumps(node_runtime.as_uri())};

const manifest = JSON.parse(readFileSync({json.dumps(str(FIXTURE_DIR / "manifest.json"))}, "utf8"));
const cases = JSON.parse(readFileSync({json.dumps(str(FIXTURE_DIR / "cases.json"))}, "utf8"));
const authorizer = createPolicyStrataAuthorizer(manifest);
const decisions = cases.map((fixture) => {{
  const decision = authorizer.authorize(fixture.input);
  return {{
    allowed: decision.allowed,
    reasons: decision.reasons,
    action: decision.action,
    resource: decision.resource,
    normalizedRoles: decision.normalizedRoles,
    manifestVersion: decision.manifestVersion,
    enforcementMode: decision.enforcementMode,
  }};
}});
console.log(JSON.stringify(decisions));
"""
    completed = subprocess.run(
        ["node", "--input-type=module"],
        input=script,
        text=True,
        check=True,
        capture_output=True,
    )
    node_decisions = json.loads(completed.stdout)

    assert node_decisions == python_decisions

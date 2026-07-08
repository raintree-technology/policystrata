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
    evaluate_runtime_event,
    evaluate_runtime_events,
    expected_runtime_decision_mismatches,
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


def governed_runtime_manifest() -> dict[str, object]:
    return {
        "schemaVersion": "policystrata.runtime_manifest.v1",
        "version": "runtime.v2.test",
        "defaultDecision": "deny",
        "resources": [
            {
                "name": "support_tickets",
                "type": "table",
                "actions": [{"name": "read", "allowedRoles": ["support_manager"]}],
            }
        ],
        "controls": {
            "authContext": {
                "requiredFields": ["userId", "tenantId", "role", "purpose"],
            },
            "retrieval": {"enabled": True},
            "tools": {
                "allowlist": ["workspace.search_tickets"],
                "approvalRequired": ["workspace.export_csv"],
            },
            "sql": {"tenantColumn": "tenant_id"},
            "schemaBinding": {"currentVersions": {"customer_health_score": "v2"}},
            "memory": {"enabled": True},
            "egress": {
                "allowedDestinations": ["https://approved.example/webhook"],
                "approvalRequired": True,
            },
            "data": {
                "redactClasses": ["pii"],
                "secretClasses": ["credential"],
            },
            "dataResidency": {
                "enabled": True,
                "allowedRegions": ["us"],
            },
            "taint": {
                "blockPromptInjection": True,
                "blockTaintedToolResults": True,
            },
        },
    }


def runtime_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "schemaVersion": "0.2.0",
        "eventId": "evt_test",
        "project": "support-bi",
        "observedAt": "2026-07-06T15:58:52Z",
        "agent": {"key": "support-bi-copilot"},
        "layer": "sql",
        "operation": "read",
        "summary": "runtime event",
        "actor": {
            "userId": "user_1",
            "tenantId": "tenant_a",
            "role": "support_manager",
            "purpose": "support",
            "region": "us",
        },
        "resource": {"kind": "table", "name": "support_tickets"},
        "dataClasses": [],
        "payload": {"sql": "select * from support_tickets where tenant_id = 'tenant_a'"},
    }
    event.update(overrides)
    return event


def test_evaluate_runtime_event_allows_clean_sql_metadata() -> None:
    decision = evaluate_runtime_event(governed_runtime_manifest(), runtime_event())

    assert decision.allowed is True
    assert decision.action == "allow"
    assert decision.reason == "runtime policy allowed action"


def test_evaluate_runtime_event_denies_when_kill_switch_is_enabled() -> None:
    manifest = governed_runtime_manifest()
    controls = manifest["controls"]
    assert isinstance(controls, dict)
    controls["runtime"] = {"killSwitch": True}

    decision = evaluate_runtime_event(manifest, runtime_event())

    assert decision.allowed is False
    assert decision.action == "deny"
    assert decision.control_id == "runtime_kill_switch"


def test_expected_runtime_decision_metadata_is_asserted_outside_evaluation() -> None:
    event = runtime_event(expectedDecision={"allowed": True, "action": "allow"})
    decision = evaluate_runtime_event(governed_runtime_manifest(), event)

    assert decision.allowed is True
    assert expected_runtime_decision_mismatches(event, decision) == []

    mismatch_event = runtime_event(expectedDecision={"allowed": True, "action": "allow"})
    mismatch = evaluate_runtime_event(
        governed_runtime_manifest(),
        {**mismatch_event, "payload": {"sql": "select * from support_tickets"}},
    )

    assert expected_runtime_decision_mismatches(mismatch_event, mismatch) == [
        "expected allowed=True, got allowed=False",
        "expected action=allow, got action=deny",
    ]


def test_evaluate_runtime_event_denies_missing_auth_context() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(actor={"userId": "user_1", "role": "support_manager"}),
    )

    assert decision.allowed is False
    assert decision.action == "deny"
    assert "missing auth context fields" in decision.reason


def test_evaluate_runtime_event_denies_cross_tenant_retrieval() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(
            layer="retrieval",
            operation="retrieve",
            resource={
                "kind": "chunk",
                "name": "refund_policy_enterprise",
                "tenantId": "tenant_b",
                "requiredEntitlements": ["refund_policy:enterprise"],
            },
        ),
    )

    assert decision.allowed is False
    assert decision.action == "deny"
    assert "retrieval resource tenant" in "\n".join(decision.reasons)
    assert "missing retrieval entitlements" in "\n".join(decision.reasons)


def test_evaluate_runtime_event_requires_approval_for_unapproved_tool() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(
            layer="tool_call",
            operation="call_tool",
            resource={"kind": "mcp_tool", "name": "workspace.export_csv"},
        ),
    )

    assert decision.allowed is False
    assert decision.action == "require_approval"
    assert "not in the runtime allowlist" in decision.reason


def test_evaluate_runtime_event_denies_sql_without_tenant_predicate() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(payload={"sql": "select * from support_tickets where status = 'open'"}),
    )

    assert decision.allowed is False
    assert decision.action == "deny"
    assert "missing tenant predicate tenant_id" in decision.reason


def test_evaluate_runtime_event_does_not_accept_tenant_column_substring() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(payload={"sql": "select tenant_id from support_tickets where status = 'open'"}),
    )

    assert decision.allowed is False
    assert "missing tenant predicate tenant_id" in decision.reason


def test_evaluate_runtime_event_classifies_sql_query_risk_and_row_limit() -> None:
    manifest = governed_runtime_manifest()
    controls = manifest["controls"]
    assert isinstance(controls, dict)
    controls["sql"] = {
        "tenantColumn": "tenant_id",
        "allowedQueryRisks": ["read"],
        "maxRows": 100,
    }

    export_decision = evaluate_runtime_event(
        manifest,
        runtime_event(payload={"sql": "copy support_tickets to stdout where tenant_id = 'tenant_a'"}),
    )
    row_decision = evaluate_runtime_event(
        manifest,
        runtime_event(
            payload={
                "sql": "select * from support_tickets where tenant_id = 'tenant_a'",
                "limit": 500,
            }
        ),
    )

    assert export_decision.allowed is False
    assert export_decision.query_risk == "export"
    assert "SQL query risk export" in "\n".join(export_decision.reasons)
    assert row_decision.allowed is False
    assert row_decision.query_risk == "read"
    assert "exceeds maxRows 100" in "\n".join(row_decision.reasons)


def test_evaluate_runtime_event_denies_unparameterized_sql_when_required() -> None:
    manifest = governed_runtime_manifest()
    controls = manifest["controls"]
    assert isinstance(controls, dict)
    controls["sql"] = {
        "tenantColumn": "tenant_id",
        "requireParameterized": True,
    }

    decision = evaluate_runtime_event(
        manifest,
        runtime_event(payload={"sql": "select * from support_tickets where tenant_id = 'tenant_a'"}),
    )

    assert decision.allowed is False
    assert decision.control_id == "sql_parameterization_required"
    assert "string_literal" in decision.reason


def test_evaluate_runtime_event_denies_rls_drift() -> None:
    manifest = governed_runtime_manifest()
    controls = manifest["controls"]
    assert isinstance(controls, dict)
    controls["databaseRule"] = {"requireRls": True}

    decision = evaluate_runtime_event(
        manifest,
        runtime_event(
            layer="database_rule",
            operation="rls_drift",
            resource={"kind": "table", "name": "support_tickets"},
            rlsExpected=True,
            rlsEnabled=False,
        ),
    )

    assert decision.allowed is False
    assert decision.action == "deny"
    assert decision.control_id == "rls_drift"


def test_evaluate_runtime_event_logs_stale_schema_binding() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(
            layer="schema_binding",
            operation="bind_metric",
            resource={"kind": "metric", "name": "customer_health_score", "version": "v1"},
        ),
    )

    assert decision.allowed is True
    assert decision.action == "log_only"
    assert "expected v2" in decision.reason


def test_evaluate_runtime_event_denies_unapproved_egress() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(
            layer="egress",
            operation="export",
            resource={"kind": "webhook", "name": "external", "uri": "https://bad.example/webhook"},
            approvalRequiredSatisfied=False,
        ),
    )

    assert decision.allowed is False
    assert decision.action == "deny"
    assert "egress destination" in decision.reason


def test_evaluate_runtime_event_denies_unapproved_egress_destination_class() -> None:
    manifest = governed_runtime_manifest()
    controls = manifest["controls"]
    assert isinstance(controls, dict)
    controls["egress"] = {"allowedDestinationClasses": ["approved_vendor"]}

    decision = evaluate_runtime_event(
        manifest,
        runtime_event(
            layer="egress",
            operation="export",
            resource={
                "kind": "webhook",
                "name": "external",
                "uri": "https://analytics.example/webhook",
                "destinationClass": "public_internet",
            },
        ),
    )

    assert decision.allowed is False
    assert decision.action == "deny"
    assert "destination class public_internet" in decision.reason


def test_evaluate_runtime_event_quarantines_cross_tenant_memory() -> None:
    decision = evaluate_runtime_event(
        governed_runtime_manifest(),
        runtime_event(
            layer="memory",
            operation="read_memory",
            resource={"kind": "memory", "name": "prior_summary", "tenantId": "tenant_b"},
        ),
    )

    assert decision.allowed is False
    assert decision.action == "quarantine"
    assert "memory item tenant" in decision.reason


def test_evaluate_runtime_events_supports_batches_and_event_output() -> None:
    decisions = evaluate_runtime_events(
        governed_runtime_manifest(),
        [
            runtime_event(eventId="evt_allowed"),
            runtime_event(eventId="evt_denied", payload={"sql": "select * from support_tickets"}),
        ],
    )

    assert [decision.event_id for decision in decisions] == ["evt_allowed", "evt_denied"]
    assert decisions[1].to_event(runtime_event(eventId="evt_denied"))["decision"]["action"] == "deny"


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

import json
from pathlib import Path

import pytest

from policystrata.runtime import authorize, authorize_release, create_policystrata_authorizer

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "packages/node/test/fixtures/runtime"


def load_json(name: str) -> object:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


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

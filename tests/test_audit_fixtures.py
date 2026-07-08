import json
from pathlib import Path

from policystrata.clearance import scan_metadata_boundary

AUDIT_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "audit" / "audit-fixtures.json"

EXPECTED_AUDIT_CASES = {
    "metadata_only_enforcement",
    "redaction_audit",
    "tenant_isolation_audit",
    "runner_token_abuse",
    "evidence_integrity_audit",
    "release_decision_audit",
    "waiver_audit",
    "runtime_event_audit",
    "sql_rls_audit",
    "retrieval_audit",
    "pii_audit",
    "egress_audit",
    "mcp_tool_audit",
    "ci_gate_audit",
    "export_audit",
}


def test_audit_fixture_catalog_covers_expected_cases() -> None:
    catalog = json.loads(AUDIT_FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = catalog["cases"]

    assert catalog["schemaVersion"] == "policystrata.audit_fixtures.v1"
    assert {case["id"] for case in cases} == EXPECTED_AUDIT_CASES
    assert all(case["metadataOnly"] is True for case in cases)
    assert next(case for case in cases if case["id"] == "waiver_audit")["hostedWorkflow"] is False


def test_audit_fixture_catalog_is_metadata_only() -> None:
    catalog = json.loads(AUDIT_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert scan_metadata_boundary(catalog) == []


def test_audit_fixture_catalog_defines_reviewer_feedback_and_quality_tracking() -> None:
    catalog = json.loads(AUDIT_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert catalog["reviewerFeedbackFormat"]["schemaVersion"] == "policystrata.reviewer_feedback.v1"
    assert "disposition" in catalog["reviewerFeedbackFormat"]["fields"]
    assert "falseNegatives" in catalog["qualityTracking"]
    assert "noisyFalsePositives" in catalog["qualityTracking"]

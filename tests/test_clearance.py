import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from policystrata.clearance import (
    ClearanceRunnerExitCode,
    assert_metadata_boundary,
    build_clearance_evidence_pack,
    build_clearance_upload_payload,
    clearance_exit_code_for_pack,
    load_clearance_runner_config,
    scan_metadata_boundary,
    upload_clearance_payload,
    validate_clearance_upload_payload,
)
from policystrata.cli import main
from policystrata.runner import run_suite


def test_run_suite_writes_clearance_metadata_contract(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_suite("support_saas", "seeded", run_dir)

    run_contract = json.loads((run_dir / ".clearance" / "clearance-run.json").read_text(encoding="utf-8"))
    evidence_pack = json.loads((run_dir / ".clearance" / "evidence-pack.json").read_text(encoding="utf-8"))

    assert run_contract["schemaVersion"] == "clearance.run.v1"
    assert run_contract["runId"].startswith("clr_")
    assert run_contract["uploadArtifacts"] is False
    assert run_contract["uploadMode"] == "metadata_only"
    assert run_contract["runner"]["name"] == "policystrata"
    assert run_contract["runner"]["policystrataVersion"]
    assert run_contract["exitCodes"]["blocked"] == int(ClearanceRunnerExitCode.BLOCKED)
    assert evidence_pack["schemaVersion"] == "clearance.evidence_pack.v1"
    assert evidence_pack["runId"] == run_contract["runId"]
    assert evidence_pack["storageMode"] == "metadata_only"
    assert evidence_pack["runner"]["policystrataVersion"]
    assert evidence_pack["decision"]["state"] == "passed"
    assert evidence_pack["summary"]["total"] == 50
    assert {artifact["path"] for artifact in evidence_pack["artifactRefs"]} >= {
        "metadata.json",
        "summary.json",
        "traces.jsonl",
    }
    assert all(artifact["upload"] is False for artifact in evidence_pack["artifactRefs"])


def test_clearance_runner_config_defaults_to_metadata_only(tmp_path: Path) -> None:
    config_path = tmp_path / "clearance.runner.yaml"
    config_path.write_text(
        """
schemaVersion: clearance.runner.v1
organizationId: org_demo
projectId: support-bi
environment: prod
releaseCandidate: rc-2026-07-08
apiUrl: https://clearance.example
engines: [policystrata]
gates:
  - id: tenant_scope
    mode: block
""".lstrip(),
        encoding="utf-8",
    )

    config = load_clearance_runner_config(config_path)

    assert config.organization_id == "org_demo"
    assert config.project_id == "support-bi"
    assert config.upload_mode == "metadata_only"
    assert config.upload_artifacts is False
    assert config.fail_mode == "fail_closed"


def test_clearance_runner_config_rejects_escaping_output_dir(tmp_path: Path) -> None:
    config_path = tmp_path / "clearance.runner.yaml"
    config_path.write_text("projectId: support-bi\noutputDir: ../escaped\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_clearance_runner_config(config_path)


def test_clearance_runner_config_rejects_unsafe_project_id(tmp_path: Path) -> None:
    config_path = tmp_path / "clearance.runner.yaml"
    config_path.write_text("projectId: '../escaped'\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_clearance_runner_config(config_path)


def test_metadata_boundary_scanner_rejects_raw_prompts_and_secrets() -> None:
    payload = {
        "eventId": "evt_1",
        "rawPrompt": "user asked for alice@example.com",
        "sampledRows": [{"customer_email": "alice@example.com"}],
        "summary": "Authorization: Bearer tokenfixturevalue",
    }

    findings = scan_metadata_boundary(payload)

    assert any(finding.path == "$.rawPrompt" for finding in findings)
    assert any(finding.path == "$.sampledRows" for finding in findings)
    assert any("bearer token" in finding.reason for finding in findings)
    with pytest.raises(ValueError, match="metadata-only boundary violation"):
        assert_metadata_boundary(payload)


def test_clearance_evidence_pack_uses_config_and_exit_code(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text(
        """
projectId: support-bi
organizationId: org_demo
environment: prod
releaseCandidate: commit-abc123
""".lstrip(),
        encoding="utf-8",
    )

    pack = build_clearance_evidence_pack(run_dir, load_clearance_runner_config(config_path))

    assert pack["organizationId"] == "org_demo"
    assert pack["projectId"] == "support-bi"
    assert pack["environment"] == "prod"
    assert pack["releaseCandidate"] == "commit-abc123"
    assert clearance_exit_code_for_pack(pack) == ClearanceRunnerExitCode.PASS_OR_REVIEW_ONLY


def test_clearance_evidence_pack_has_stable_run_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_suite("support_saas", "seeded", run_dir)

    first = build_clearance_evidence_pack(run_dir)
    second = build_clearance_evidence_pack(run_dir)

    assert first["runId"] == second["runId"]


def test_clearance_artifact_refs_reject_symlink_escape(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_suite("support_saas", "seeded", run_dir)
    escaped = tmp_path / "outside.json"
    escaped.write_text("{}", encoding="utf-8")
    link = run_dir / "witnesses" / "escaped.json"
    link.symlink_to(escaped)

    with pytest.raises(ValueError, match="escapes run directory"):
        build_clearance_evidence_pack(run_dir)


def test_clearance_evidence_pack_references_optional_local_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_suite("support_saas", "seeded", run_dir)
    (run_dir / "policystrata").mkdir()
    (run_dir / "docpull").mkdir()
    (run_dir / "policystrata" / "findings.json").write_text("[]\n", encoding="utf-8")
    (run_dir / "witnesses.redacted.json").write_text('{"witnesses":[]}\n', encoding="utf-8")
    (run_dir / "runtime-events.json").write_text('{"events":[]}\n', encoding="utf-8")
    (run_dir / "docpull" / "summary.json").write_text(
        '{"docPullVersion":"0.4.1","documents":3}\n',
        encoding="utf-8",
    )

    pack = build_clearance_evidence_pack(run_dir)
    refs = {item["path"]: item for item in pack["artifactRefs"]}

    assert "policystrata/findings.json" in refs
    assert "witnesses.redacted.json" in refs
    assert "runtime-events.json" in refs
    assert "docpull/summary.json" in refs
    assert refs["runtime-events.json"]["sha256"]
    assert pack["run"]["docPull"] == {
        "summaryRef": "docpull/summary.json",
        "version": "0.4.1",
    }


def test_cli_run_accepts_clearance_metadata_and_output_dir(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"

    assert (
        main(
            [
                "run",
                "--domain",
                "support_saas",
                "--suite",
                "seeded",
                "--out",
                str(run_dir),
                "--project-id",
                "support-bi",
                "--organization-id",
                "org_demo",
                "--environment",
                "prod",
                "--release-candidate",
                "rc-2026-07-08",
                "--commit-sha",
                "abc123",
                "--clearance-output-dir",
                "clearance-out",
                "--offline",
            ]
        )
        == 0
    )

    evidence_pack = json.loads((run_dir / "clearance-out" / "evidence-pack.json").read_text(encoding="utf-8"))
    run_contract = json.loads((run_dir / "clearance-out" / "clearance-run.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))

    assert evidence_pack["projectId"] == "support-bi"
    assert evidence_pack["organizationId"] == "org_demo"
    assert evidence_pack["environment"] == "prod"
    assert evidence_pack["releaseCandidate"] == "rc-2026-07-08"
    assert evidence_pack["commitSha"] == "abc123"
    assert run_contract["offline"] is True
    assert metadata["project_id"] == "support-bi"
    assert metadata["organization_id"] == "org_demo"


def test_cli_schema_includes_clearance_contracts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schema", "--kind", "clearance-runner-config"]) == 0
    config_schema = json.loads(capsys.readouterr().out)
    assert config_schema["$id"] == "https://policystrata.dev/schemas/clearance.runner.schema.json"

    assert main(["schema", "--kind", "clearance-run"]) == 0
    run_schema = json.loads(capsys.readouterr().out)
    assert run_schema["$id"] == "https://policystrata.dev/schemas/clearance-run.schema.json"

    assert main(["schema", "--kind", "clearance-evidence-pack"]) == 0
    pack_schema = json.loads(capsys.readouterr().out)
    assert pack_schema["$id"] == "https://policystrata.dev/schemas/clearance-evidence-pack.schema.json"

    assert main(["schema", "--kind", "clearance-upload"]) == 0
    upload_schema = json.loads(capsys.readouterr().out)
    assert upload_schema["$id"] == "https://policystrata.dev/schemas/clearance-upload.schema.json"


def test_clearance_upload_payload_strips_runtime_payload_and_expected_decision(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text("projectId: support-bi\norganizationId: org_demo\n", encoding="utf-8")

    payload = build_clearance_upload_payload(
        run_dir,
        load_clearance_runner_config(config_path),
        runtime_events={
            "events": [
                {
                    "schemaVersion": "0.2.0",
                    "eventId": "evt_1",
                    "project": "support-bi",
                    "observedAt": "2026-07-06T15:58:52Z",
                    "agent": {"key": "support-bi-copilot"},
                    "layer": "sql",
                    "operation": "read",
                    "summary": "metadata only",
                    "payload": {"sql": "select * from support_tickets"},
                    "expectedDecision": {"allowed": False},
                }
            ]
        },
    )

    assert payload["uploadId"].startswith("clu_")
    assert payload["uploadMode"] == "metadata_only"
    assert "payload" not in payload["runtimeEvents"][0]
    assert "expectedDecision" not in payload["runtimeEvents"][0]
    validate_clearance_upload_payload(payload)


def test_clearance_upload_payload_rejects_boundary_violation_and_size(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text("projectId: support-bi\n", encoding="utf-8")
    payload = build_clearance_upload_payload(run_dir, load_clearance_runner_config(config_path))

    with pytest.raises(ValueError, match="too large"):
        validate_clearance_upload_payload(payload, max_bytes=1)
    with pytest.raises(ValueError, match="metadata-only boundary violation"):
        validate_clearance_upload_payload({**payload, "runtimeEvents": [{"rawPrompt": "hello"}]})


def test_clearance_upload_payload_validates_nested_contracts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text("projectId: support-bi\norganizationId: org_demo\n", encoding="utf-8")
    payload = build_clearance_upload_payload(run_dir, load_clearance_runner_config(config_path))
    broken_run = dict(payload["clearanceRun"])
    broken_run.pop("runner")

    with pytest.raises(ValidationError):
        validate_clearance_upload_payload({**payload, "clearanceRun": broken_run})


def test_upload_clearance_payload_posts_metadata_contract(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text("projectId: support-bi\norganizationId: org_demo\n", encoding="utf-8")
    payload = build_clearance_upload_payload(
        run_dir,
        load_clearance_runner_config(config_path),
        idempotency_key="upload-once",
    )
    received: dict[str, Any] = {}
    server = _start_upload_server(received, status=202)

    try:
        result = upload_clearance_payload(
            payload,
            api_url=f"http://127.0.0.1:{server.server_port}",
            token="runner_token",
            organization_id="org_demo",
            max_bytes=1_000_000,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result.ok is True
    assert result.status == 202
    assert received["path"] == "/v1/runner/uploads"
    assert received["authorization"] == "Bearer runner_token"
    assert received["organization"] == "org_demo"
    assert received["idempotency"] == "upload-once"
    assert received["body"]["uploadId"] == payload["uploadId"]


def test_cli_clearance_runner_upload_requires_runner_token(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text("projectId: support-bi\napiUrl: http://127.0.0.1:9\n", encoding="utf-8")
    monkeypatch.delenv("CLEARANCE_RUNNER_TOKEN", raising=False)

    assert main(["clearance-runner", "upload", "--run-dir", str(run_dir), "--config", str(config_path)]) == 4

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["error"] == "missing_runner_token"


def test_cli_clearance_runner_upload_returns_exit_code_four_on_auth_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    server = _start_upload_server({}, status=401)
    config_path.write_text(
        f"projectId: support-bi\norganizationId: org_demo\napiUrl: http://127.0.0.1:{server.server_port}\n",
        encoding="utf-8",
    )

    try:
        assert (
            main(
                [
                    "clearance-runner",
                    "upload",
                    "--run-dir",
                    str(run_dir),
                    "--config",
                    str(config_path),
                    "--token",
                    "runner_token",
                ]
            )
            == 4
        )
    finally:
        server.shutdown()
        server.server_close()

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["status"] == 401
    assert output["error"] == "HTTPError"


def test_cli_clearance_runner_local_only_fails_closed_on_protected_branch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text(
        "projectId: support-bi\napiUrl: http://127.0.0.1:9\nuploadMode: local_only\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    assert main(["clearance-runner", "upload", "--run-dir", str(run_dir), "--config", str(config_path)]) == 4

    output = json.loads(capsys.readouterr().out)
    assert output["error"] == "protected_branch_local_only_blocked"


def test_cli_clearance_runner_local_only_override_records_audit_note(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text(
        "projectId: support-bi\napiUrl: http://127.0.0.1:9\nuploadMode: local_only\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    assert (
        main(
            [
                "clearance-runner",
                "upload",
                "--run-dir",
                str(run_dir),
                "--config",
                str(config_path),
                "--local-override-note",
                "approved break-glass local evidence run",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    run_contract = json.loads((run_dir / ".clearance" / "clearance-run.json").read_text(encoding="utf-8"))
    assert output["uploadMode"] == "local_only"
    assert output["localOverrideNote"] == "approved break-glass local evidence run"
    assert run_contract["localOverrideNote"] == "approved break-glass local evidence run"


def test_cli_clearance_runner_validate_audit_and_evidence_pack(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_dir = tmp_path / "run"
    config_path = tmp_path / "clearance.runner.yaml"
    payload_path = tmp_path / "runtime-event.json"
    out_path = tmp_path / "evidence-pack.json"
    run_suite("support_saas", "seeded", run_dir)
    config_path.write_text("projectId: support-bi\norganizationId: org_demo\n", encoding="utf-8")
    payload_path.write_text(json.dumps({"eventId": "evt_1", "summary": "metadata only"}), encoding="utf-8")

    assert main(["clearance-runner", "validate", "--config", str(config_path)]) == 0
    assert json.loads(capsys.readouterr().out)["uploadArtifacts"] is False

    assert main(["clearance-runner", "audit-payload", "--payload", str(payload_path)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    assert (
        main(
            [
                "clearance-runner",
                "evidence-pack",
                "--run-dir",
                str(run_dir),
                "--config",
                str(config_path),
                "--out",
                str(out_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {
        "blocked": False,
        "exitCode": 0,
        "needsReview": False,
        "out": str(out_path),
        "state": "passed",
    }
    pack = json.loads(out_path.read_text(encoding="utf-8"))
    assert pack["projectId"] == "support-bi"
    assert pack["localArtifacts"]["evidence_pack"].endswith("evidence-pack.json")


def test_cli_clearance_runner_validate_returns_exit_code_three_for_invalid_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "clearance.runner.yaml"
    config_path.write_text("projectId: ../bad\n", encoding="utf-8")

    assert main(["clearance-runner", "validate", "--config", str(config_path)]) == 3

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["error"] == "invalid_config"


def test_cli_clearance_runner_audit_payload_fails_for_secret(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload_path = tmp_path / "runtime-event.json"
    payload_path.write_text(json.dumps({"token": "tokenfixturevalue"}), encoding="utf-8")

    assert main(["clearance-runner", "audit-payload", "--payload", str(payload_path)]) == 1

    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False
    assert result["findings"][0]["path"] == "$.token"


def _start_upload_server(received: dict[str, Any], *, status: int) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            received["path"] = self.path
            received["authorization"] = self.headers.get("authorization")
            received["organization"] = self.headers.get("x-clearance-organization-id")
            received["idempotency"] = self.headers.get("idempotency-key")
            received["body"] = body
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}\n')

        def log_message(self, format_: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

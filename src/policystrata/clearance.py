from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from enum import IntEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ConfigDict, Field, field_validator

from policystrata import __version__
from policystrata.models import CompatModel, InputModel, SafeIdentifier
from policystrata.summary import summarize_run


class ClearanceRunnerExitCode(IntEnum):
    PASS_OR_REVIEW_ONLY = 0
    FAIL = 1
    BLOCKED = 2
    INVALID_CONFIG = 3
    UPLOAD_AUTH_FAILURE = 4


UploadMode = Literal["local_only", "metadata_only", "redacted_artifacts"]
FailMode = Literal["fail_closed", "fail_open"]
DEFAULT_UPLOAD_PATH = "/v1/runner/uploads"
DEFAULT_UPLOAD_MAX_BYTES = 1_000_000


class ClearanceGateConfig(InputModel):
    id: SafeIdentifier
    mode: Literal["block", "review", "log"] = "block"


class ClearanceRunnerConfig(InputModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schema_version: Literal["clearance.runner.v1"] = Field(
        default="clearance.runner.v1",
        alias="schemaVersion",
    )
    organization_id: SafeIdentifier | None = Field(default=None, alias="organizationId")
    project_id: SafeIdentifier = Field(alias="projectId")
    environment: SafeIdentifier = "dev"
    release_candidate: str | None = Field(default=None, alias="releaseCandidate")
    api_url: str | None = Field(default=None, alias="apiUrl")
    output_dir: str = Field(default=".clearance", alias="outputDir")
    upload_mode: UploadMode = Field(default="metadata_only", alias="uploadMode")
    upload_artifacts: bool = Field(default=False, alias="uploadArtifacts")
    offline: bool = False
    fail_mode: FailMode = Field(default="fail_closed", alias="failMode")
    local_override_note: str | None = Field(default=None, alias="localOverrideNote")
    protected_branches: list[str] = Field(
        default_factory=lambda: ["main", "master"],
        alias="protectedBranches",
    )
    engines: list[SafeIdentifier] = Field(default_factory=list)
    gateway_events: list[str] = Field(default_factory=list, alias="gatewayEvents")
    gates: list[ClearanceGateConfig] = Field(default_factory=list)

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            raise ValueError("outputDir must be relative to the run directory")
        if ".." in path.parts:
            raise ValueError("outputDir must not escape the run directory")
        return value


class ClearanceArtifactRef(CompatModel):
    path: str
    sha256: str
    bytes: int
    redacted: bool = False
    upload: bool = False


class ClearanceEvidencePack(CompatModel):
    schema_version: Literal["clearance.evidence_pack.v1"] = Field(
        default="clearance.evidence_pack.v1",
        alias="schemaVersion",
    )
    run_id: str = Field(alias="runId")
    storage_mode: Literal["metadata_only"] = Field(default="metadata_only", alias="storageMode")
    organization_id: str | None = Field(default=None, alias="organizationId")
    project_id: str = Field(alias="projectId")
    environment: str | None = None
    release_candidate: str | None = Field(default=None, alias="releaseCandidate")
    commit_sha: str | None = Field(default=None, alias="commitSha")
    upload_artifacts: bool = Field(default=False, alias="uploadArtifacts")
    runner: dict[str, Any]
    run: dict[str, Any]
    decision: dict[str, Any]
    summary: dict[str, Any]
    artifact_refs: list[ClearanceArtifactRef] = Field(alias="artifactRefs")


class ClearanceRunContract(CompatModel):
    schema_version: Literal["clearance.run.v1"] = Field(default="clearance.run.v1", alias="schemaVersion")
    run_id: str = Field(alias="runId")
    storage_mode: Literal["metadata_only"] = Field(default="metadata_only", alias="storageMode")
    upload_mode: UploadMode = Field(default="metadata_only", alias="uploadMode")
    upload_artifacts: bool = Field(default=False, alias="uploadArtifacts")
    offline: bool = False
    fail_mode: FailMode = Field(default="fail_closed", alias="failMode")
    local_override_note: str | None = Field(default=None, alias="localOverrideNote")
    runner: dict[str, Any]
    exit_codes: dict[str, int] = Field(alias="exitCodes")
    evidence_pack_ref: str = Field(alias="evidencePackRef")
    artifact_refs: list[ClearanceArtifactRef] = Field(alias="artifactRefs")


class ClearanceUploadPayload(CompatModel):
    schema_version: Literal["clearance.upload.v1"] = Field(
        default="clearance.upload.v1",
        alias="schemaVersion",
    )
    upload_id: str = Field(alias="uploadId")
    idempotency_key: str = Field(alias="idempotencyKey")
    upload_mode: UploadMode = Field(alias="uploadMode")
    local_override_note: str | None = Field(default=None, alias="localOverrideNote")
    organization_id: str | None = Field(default=None, alias="organizationId")
    project_id: str = Field(alias="projectId")
    run_id: str = Field(alias="runId")
    evidence_pack: ClearanceEvidencePack = Field(alias="evidencePack")
    clearance_run: ClearanceRunContract = Field(alias="clearanceRun")
    runtime_events: list[dict[str, Any]] = Field(default_factory=list, alias="runtimeEvents")


class ClearanceUploadResult(CompatModel):
    ok: bool
    status: int
    body: object | None = None
    error: str | None = None


class BoundaryFinding(CompatModel):
    path: str
    reason: str
    severity: Literal["high", "critical"] = "high"


SENSITIVE_KEY_RE = re.compile(
    r"(?:^|[_\-.])("
    r"api[_\-.]?key|authorization|bearer|cookie|credential|customer[_\-.]?rows|"
    r"doc[_\-.]?text|documents?|full[_\-.]?trace|input[_\-.]?schema|output[_\-.]?schema|"
    r"password|passwd|private[_\-.]?schema|prompt|raw[_\-.]?docs?|raw[_\-.]?documents?|"
    r"raw[_\-.]?payload|raw[_\-.]?prompt|rows|sampled[_\-.]?rows|secret|"
    r"source[_\-.]?credentials|token|"
    r"tool[_\-.]?(?:input|output|payload|request|response)"
    r")(?:$|[_\-.])",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b", re.IGNORECASE), "bearer token"),
    (
        re.compile(r"\b(?:api[_-]?key|password|passwd|secret|token)\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
        "secret assignment",
    ),
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), "JWT"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "email address"),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "possible payment card"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "API key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "API key"),
    (
        re.compile(r"https?://[^\s?#]+[^\s]*[?&](?:api[_-]?key|token|secret|password)=[^&\s]+", re.I),
        "secret in URL",
    ),
)
SENSITIVE_PATH_PART_RE = re.compile(
    r"(?:^|[_\-.])("
    r"api[_\-.]?key|authorization|bearer|credential|password|passwd|secret|token"
    r")(?:$|[_\-.])",
    re.IGNORECASE,
)
METADATA_ONLY_ARTIFACTS = (
    "metadata.json",
    "summary.json",
    "traces.jsonl",
    "benchmark_manifest.json",
    "policystrata/findings.json",
    "witnesses.redacted.json",
    "runtime-events.json",
    "docpull/summary.json",
)


def load_clearance_runner_config(path: Path) -> ClearanceRunnerConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError(f"Clearance runner config must be an object: {path}")
    return ClearanceRunnerConfig.model_validate(raw)


def scan_metadata_boundary(payload: object) -> list[BoundaryFinding]:
    findings: list[BoundaryFinding] = []
    for path, value in _walk_payload(payload):
        key = path.rsplit(".", 1)[-1]
        if SENSITIVE_KEY_RE.search(key):
            findings.append(
                BoundaryFinding(path=path, reason=f"sensitive field name: {key}", severity="critical")
            )
        if isinstance(value, str):
            for pattern, label in SECRET_VALUE_PATTERNS:
                if pattern.search(value):
                    findings.append(
                        BoundaryFinding(path=path, reason=f"possible {label}", severity="critical")
                    )
    return findings


def assert_metadata_boundary(payload: object) -> None:
    findings = scan_metadata_boundary(payload)
    if findings:
        first = findings[0]
        raise ValueError(f"metadata-only boundary violation at {first.path}: {first.reason}")


def redacted_runtime_event_for_upload(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in event.items()
        if key not in {"payload", "expectedDecision", "expected_decision"}
    }


def redacted_runtime_events_for_upload(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping) and isinstance(payload.get("events"), list):
        items = payload["events"]
    else:
        items = [payload]
    events = [redacted_runtime_event_for_upload(item) for item in items if isinstance(item, Mapping)]
    if len(events) != len(items):
        raise ValueError("runtime upload payload must be an event object or {events:[...]}")
    return events


def clearance_artifact_manifest(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for relative in METADATA_ONLY_ARTIFACTS:
        path = run_dir / relative
        if path.exists():
            artifacts.append(_artifact_ref(run_dir, path))
    witness_dir = run_dir / "witnesses"
    if witness_dir.exists():
        for path in sorted(witness_dir.glob("*.json")):
            artifacts.append(_artifact_ref(run_dir, path, redacted=True))
    return artifacts


def build_clearance_evidence_pack(
    run_dir: Path,
    config: ClearanceRunnerConfig | None = None,
) -> dict[str, Any]:
    summary = summarize_run(run_dir)
    metadata = _load_json_object(run_dir / "metadata.json")
    docpull_metadata = docpull_summary_metadata(run_dir)
    artifact_refs = clearance_artifact_manifest(run_dir)
    run_id = stable_clearance_run_id(metadata, summary.model_dump(), artifact_refs, config)
    organization_id = config.organization_id if config else metadata.get("organization_id")
    project_id = config.project_id if config else metadata.get("project_id") or metadata.get("domain")
    environment = config.environment if config else metadata.get("environment")
    release_candidate = config.release_candidate if config else metadata.get("release_candidate")
    pack = {
        "schemaVersion": "clearance.evidence_pack.v1",
        "runId": run_id,
        "storageMode": "metadata_only",
        "organizationId": organization_id,
        "projectId": project_id,
        "environment": environment,
        "releaseCandidate": release_candidate,
        "commitSha": metadata.get("commit_sha"),
        "uploadArtifacts": config.upload_artifacts if config else False,
        "localOverrideNote": config.local_override_note if config else None,
        "runner": {
            "name": "policystrata",
            "policystrataVersion": __version__,
            "contract": "clearance.runner.v1",
        },
        "run": {
            "domain": metadata.get("domain"),
            "suite": metadata.get("suite"),
            "generatedCount": metadata.get("generated_count"),
            "generatedSeed": metadata.get("generated_seed"),
            "policyVersion": metadata.get("policy_version"),
            "traceCount": metadata.get("trace_count", summary.total),
            "evidenceLevel": metadata.get("evidence_level"),
            "suiteProvenance": metadata.get("suite_provenance"),
            "detectorFrozen": metadata.get("detector_frozen", False),
            "docPull": docpull_metadata or None,
        },
        "decision": {
            "state": _release_state(summary),
            "failed": summary.survived > 0 or summary.false_positives > 0,
            "blocked": summary.survived > 0,
            "needsReview": summary.false_positives > 0,
        },
        "summary": summary.model_dump(),
        "artifactRefs": artifact_refs,
    }
    assert_metadata_boundary(pack)
    return pack


def docpull_summary_metadata(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "docpull" / "summary.json"
    if not path.exists():
        return {}
    summary = _load_json_object(path)
    version = (
        summary.get("docPullVersion")
        or summary.get("docpullVersion")
        or summary.get("version")
        or summary.get("toolVersion")
    )
    metadata = {
        "version": version,
        "summaryRef": "docpull/summary.json",
    }
    return {key: value for key, value in metadata.items() if value is not None}


def write_clearance_contract_outputs(
    run_dir: Path,
    config: ClearanceRunnerConfig | None = None,
) -> dict[str, str]:
    clearance_dir = run_dir / (config.output_dir if config else ".clearance")
    clearance_dir.mkdir(parents=True, exist_ok=True)
    evidence_pack = build_clearance_evidence_pack(run_dir, config)
    run_contract = {
        "schemaVersion": "clearance.run.v1",
        "runId": evidence_pack["runId"],
        "storageMode": "metadata_only",
        "uploadMode": config.upload_mode if config else "metadata_only",
        "uploadArtifacts": config.upload_artifacts if config else False,
        "offline": config.offline if config else False,
        "failMode": config.fail_mode if config else "fail_closed",
        "localOverrideNote": config.local_override_note if config else None,
        "runner": {
            "name": "policystrata",
            "policystrataVersion": __version__,
            "contract": "clearance.run.v1",
        },
        "exitCodes": {item.name.lower(): int(item) for item in ClearanceRunnerExitCode},
        "evidencePackRef": "evidence-pack.json",
        "artifactRefs": evidence_pack["artifactRefs"],
    }
    assert_metadata_boundary(run_contract)
    evidence_path = clearance_dir / "evidence-pack.json"
    run_path = clearance_dir / "clearance-run.json"
    evidence_path.write_text(json.dumps(evidence_pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run_path.write_text(json.dumps(run_contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "clearance_run": str(run_path),
        "evidence_pack": str(evidence_path),
    }


def build_clearance_upload_payload(
    run_dir: Path,
    config: ClearanceRunnerConfig,
    *,
    runtime_events: object | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    evidence_pack = build_clearance_evidence_pack(run_dir, config)
    outputs = write_clearance_contract_outputs(run_dir, config)
    clearance_run = _load_json_object(Path(outputs["clearance_run"]))
    redacted_events = redacted_runtime_events_for_upload(runtime_events) if runtime_events is not None else []
    upload_id = stable_clearance_upload_id(evidence_pack, clearance_run, redacted_events)
    payload = {
        "schemaVersion": "clearance.upload.v1",
        "uploadId": upload_id,
        "idempotencyKey": idempotency_key or upload_id,
        "uploadMode": config.upload_mode,
        "localOverrideNote": config.local_override_note,
        "organizationId": config.organization_id,
        "projectId": config.project_id,
        "runId": evidence_pack["runId"],
        "evidencePack": evidence_pack,
        "clearanceRun": clearance_run,
        "runtimeEvents": redacted_events,
    }
    validate_clearance_upload_payload(payload)
    return payload


def stable_clearance_upload_id(
    evidence_pack: Mapping[str, Any],
    clearance_run: Mapping[str, Any],
    runtime_events: list[dict[str, Any]],
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "schemaVersion": "clearance.upload.v1",
                "runId": evidence_pack.get("runId"),
                "evidencePack": evidence_pack,
                "clearanceRun": clearance_run,
                "runtimeEvents": runtime_events,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return f"clu_{digest.hexdigest()[:32]}"


def validate_clearance_upload_payload(
    payload: Mapping[str, Any],
    *,
    max_bytes: int = DEFAULT_UPLOAD_MAX_BYTES,
) -> None:
    ClearanceUploadPayload.model_validate(payload)
    assert_metadata_boundary(payload)
    size = len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if size > max_bytes:
        raise ValueError(f"clearance upload payload is too large: {size} bytes exceeds {max_bytes}")


def upload_clearance_payload(
    payload: Mapping[str, Any],
    *,
    api_url: str,
    token: str | None = None,
    organization_id: str | None = None,
    path: str = DEFAULT_UPLOAD_PATH,
    max_bytes: int = DEFAULT_UPLOAD_MAX_BYTES,
) -> ClearanceUploadResult:
    validate_clearance_upload_payload(payload, max_bytes=max_bytes)
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        _join_url(api_url, path),
        data=payload_bytes,
        method="POST",
        headers=_upload_headers(
            token=token or os.environ.get("CLEARANCE_RUNNER_TOKEN"),
            organization_id=organization_id,
            idempotency_key=str(payload.get("idempotencyKey", "")),
        ),
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return ClearanceUploadResult(
                ok=200 <= response.status < 300,
                status=response.status,
                body=_decode_response_body(response.read()),
            )
    except urllib.error.HTTPError as exc:
        return ClearanceUploadResult(
            ok=False,
            status=exc.code,
            body=_decode_response_body(exc.read()),
            error=_safe_upload_error(exc),
        )
    except urllib.error.URLError as exc:
        return ClearanceUploadResult(ok=False, status=0, error=_safe_upload_error(exc))


def protected_branch_upload_blocker(
    config: ClearanceRunnerConfig,
    *,
    branch: str | None = None,
) -> str | None:
    current_branch = branch or current_git_branch()
    if (
        config.upload_mode == "local_only"
        and config.fail_mode == "fail_closed"
        and current_branch in set(config.protected_branches)
        and not config.local_override_note
    ):
        return (
            f"protected branch {current_branch} requires upload or an explicit local override audit note"
        )
    return None


def current_git_branch() -> str | None:
    for name in ("GITHUB_REF_NAME", "CI_COMMIT_BRANCH", "BUILDKITE_BRANCH", "BRANCH_NAME"):
        value = os.environ.get(name)
        if value:
            return value
    try:
        completed = subprocess.run(
            ["git", "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    branch = completed.stdout.strip()
    return branch or None


def clearance_exit_code_for_pack(pack: Mapping[str, Any]) -> ClearanceRunnerExitCode:
    decision = pack.get("decision")
    if not isinstance(decision, Mapping):
        return ClearanceRunnerExitCode.INVALID_CONFIG
    if decision.get("blocked") is True:
        return ClearanceRunnerExitCode.BLOCKED
    if decision.get("failed") is True:
        return ClearanceRunnerExitCode.FAIL
    return ClearanceRunnerExitCode.PASS_OR_REVIEW_ONLY


def stable_clearance_run_id(
    metadata: Mapping[str, Any],
    summary: Mapping[str, Any],
    artifact_refs: list[dict[str, Any]],
    config: ClearanceRunnerConfig | None = None,
) -> str:
    payload = {
        "schemaVersion": "clearance.run.v1",
        "policystrataVersion": __version__,
        "organizationId": config.organization_id if config else metadata.get("organization_id"),
        "projectId": config.project_id if config else metadata.get("project_id") or metadata.get("domain"),
        "environment": config.environment if config else metadata.get("environment"),
        "releaseCandidate": config.release_candidate if config else metadata.get("release_candidate"),
        "commitSha": metadata.get("commit_sha"),
        "domain": metadata.get("domain"),
        "suite": metadata.get("suite"),
        "generatedCount": metadata.get("generated_count"),
        "generatedSeed": metadata.get("generated_seed"),
        "policyVersion": metadata.get("policy_version"),
        "traceCount": metadata.get("trace_count"),
        "summary": summary,
        "artifactRefs": artifact_refs,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return f"clr_{digest.hexdigest()[:32]}"


def _artifact_ref(run_dir: Path, path: Path, *, redacted: bool = False) -> dict[str, Any]:
    _assert_artifact_target_within_run_dir(run_dir, path)
    relative = path.relative_to(run_dir).as_posix()
    assert_metadata_boundary({"artifactRef": relative})
    for part in Path(relative).parts:
        if SENSITIVE_PATH_PART_RE.search(part):
            raise ValueError(f"metadata-only boundary violation at artifactRef: sensitive filename: {part}")
    data = path.read_bytes()
    return {
        "path": relative,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "redacted": redacted,
        "upload": False,
    }


def _release_state(summary: Any) -> str:
    if summary.survived > 0:
        return "blocked"
    if summary.false_positives > 0:
        return "needs_review"
    return "passed"


def _load_json_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected JSON object: {path}")
    return raw


def _join_url(api_url: str, path: str) -> str:
    return f"{api_url.rstrip('/')}/{path.lstrip('/')}"


def _upload_headers(
    *,
    token: str | None,
    organization_id: str | None,
    idempotency_key: str,
) -> dict[str, str]:
    headers = {
        "content-type": "application/json",
        "idempotency-key": idempotency_key,
    }
    if token:
        headers["authorization"] = f"Bearer {token}"
    if organization_id:
        headers["x-clearance-organization-id"] = organization_id
    return headers


def _decode_response_body(data: bytes) -> object | None:
    if not data:
        return None
    text = data.decode("utf-8", errors="replace")
    try:
        parsed: object = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        return text


def _safe_upload_error(error: BaseException) -> str:
    return error.__class__.__name__


def _assert_artifact_target_within_run_dir(run_dir: Path, path: Path) -> None:
    run_root = run_dir.resolve(strict=True)
    target = path.resolve(strict=True)
    try:
        target.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(f"artifact ref escapes run directory: {path}") from exc


def _walk_payload(value: object, prefix: str = "$") -> Iterable[tuple[str, object]]:
    yield prefix, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if isinstance(key, str) else f"{prefix}.[key]"
            yield from _walk_payload(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_payload(child, f"{prefix}[{index}]")

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from policystrata.domain import load_policy, load_surface_config
from policystrata.evidence import markdown_table
from policystrata.models import Policy, SurfaceConfig
from policystrata.policy import PolicyOracle
from policystrata.scan_models import FileInputConfig, ImportedTrace, ScanConfig
from policystrata.scanner import load_scan_config, tenant_columns_for_scope_check
from policystrata.trace_import import (
    load_imported_traces,
    resolve_optional_config_path,
    resolve_scan_input_paths,
)

DOCTOR_VERSION = "doctor.v1"
EXPECTED_SURFACES = ("manifest", "grammar", "validator", "compiler", "database", "release")
SENSITIVE_COLUMN_HINTS = ("email", "phone", "ssn", "social_security", "address", "name")
REQUIRED_POLICY_DOC_TYPES = ("privacy_policy", "terms_of_service")
RECOMMENDED_POLICY_DOC_TYPES = ("data_processing_agreement", "internal_policy", "security_policy")
POLICY_DOC_TYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "privacy_policy": (
        "privacy policy",
        "privacy notice",
        "personal information",
        "personal data",
    ),
    "terms_of_service": (
        "terms of service",
        "terms and conditions",
        "terms of use",
        "tos",
        "acceptable use",
        "service terms",
    ),
    "data_processing_agreement": (
        "data processing agreement",
        "dpa",
        "controller",
        "processor",
        "subprocessor",
    ),
    "internal_policy": (
        "internal policy",
        "employee access",
        "least privilege",
        "role-based access",
    ),
    "security_policy": (
        "security policy",
        "security controls",
        "encryption",
        "safeguards",
    ),
    "retention_policy": (
        "retention policy",
        "retention schedule",
        "delete data",
        "deletion request",
    ),
}
POLICY_OBLIGATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "personal_data_minimization": (
        "minimum necessary",
        "only collect",
        "limited to what is necessary",
        "personal data",
        "personal information",
    ),
    "purpose_limited_processing": (
        "purpose",
        "provide the service",
        "process data to",
        "use your information to",
    ),
    "notice_or_consent": (
        "notice",
        "consent",
        "privacy policy",
        "privacy notice",
    ),
    "data_subject_rights": (
        "access your",
        "correct your",
        "delete your",
        "data subject",
        "privacy rights",
    ),
    "retention_and_deletion": (
        "retain",
        "retention",
        "delete",
        "deletion",
    ),
    "third_party_sharing": (
        "third party",
        "share",
        "disclose",
        "service provider",
    ),
    "subprocessor_controls": (
        "subprocessor",
        "processor",
        "controller",
        "data processing agreement",
    ),
    "security_controls": (
        "security",
        "encryption",
        "safeguards",
        "access control",
        "least privilege",
    ),
    "tenant_isolation": (
        "tenant",
        "customer data",
        "segregation",
        "authorized users",
        "account data",
    ),
}


def environment_doctor() -> dict[str, object]:
    return {
        "python": sys.version.split()[0],
        "uv": shutil.which("uv") is not None,
        "docker": shutil.which("docker") is not None,
        "requires_llm_api_key": False,
        "requires_host_psql": False,
    }


def run_config_doctor(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config_dir = config_path.parent
    config = load_scan_config(config_path)
    domain_path = resolve_optional_config_path(config_dir, config.domain_path)
    policy, policy_error = load_policy_for_doctor(config, domain_path)
    surfaces, surfaces_error = load_surfaces_for_doctor(config, domain_path)
    sql_traces = inspect_trace_inputs(config, config_path, policy)
    dbt_files = inspect_declared_files(config_dir, config.dbt.files, "dbt semantic model", confined=True)
    policy_docs = inspect_policy_documents(config_dir, config.policy_docs, policy)
    prompt_manifests = inspect_prompt_manifests(config_dir, config.prompt_manifests, policy)
    source_maps = inspect_file_config(config_dir, config.source_maps, "source map", confined=False)
    schema = inspect_schema(config, config_dir, policy)
    coverage = build_coverage_accounting(config, sql_traces, policy_docs, prompt_manifests)
    stack = build_stack_checks(
        config,
        config_path,
        policy,
        policy_error,
        surfaces,
        surfaces_error,
        dbt_files,
        sql_traces,
        policy_docs,
        prompt_manifests,
        source_maps,
        schema,
        coverage,
    )
    remediation = build_remediation(config, config_path, stack)
    return {
        "version": DOCTOR_VERSION,
        "environment": environment_doctor(),
        "config_path": str(config_path),
        "domain": config.domain,
        "domain_path": str(domain_path) if domain_path is not None else f"builtin:{config.domain}",
        "policy": policy_inventory(config, domain_path, policy, policy_error),
        "policy_documents": policy_docs,
        "surfaces": surface_inventory(config, domain_path, surfaces, surfaces_error),
        "stack": stack,
        "coverage_accounting": coverage,
        "database_introspection": schema,
        "remediation": remediation,
        "golden_templates": golden_templates(),
        "commands": {
            "doctor": f"uv run policystrata doctor --config {config_path}",
            "scan": f"uv run policystrata scan --config {config_path}",
            "ci_gate": f"uv run policystrata scan --config {config_path}",
        },
    }


def load_policy_for_doctor(
    config: ScanConfig,
    domain_path: Path | None,
) -> tuple[Policy | None, str | None]:
    try:
        return load_policy(config.domain, domain_path), None
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        return None, str(exc)


def load_surfaces_for_doctor(
    config: ScanConfig,
    domain_path: Path | None,
) -> tuple[SurfaceConfig | None, str | None]:
    try:
        return load_surface_config(config.domain, domain_path), None
    except (OSError, TypeError, ValueError, ValidationError) as exc:
        return None, str(exc)


def inspect_file_config(
    config_dir: Path,
    config: FileInputConfig,
    input_name: str,
    *,
    confined: bool,
) -> dict[str, Any]:
    return inspect_declared_files(config_dir, config.files, input_name, confined=confined) | {
        "required": config.required
    }


def inspect_policy_documents(
    config_dir: Path,
    config: FileInputConfig,
    policy: Policy | None,
) -> dict[str, Any]:
    files = inspect_file_config(config_dir, config, "policy document", confined=False)
    documents: list[dict[str, Any]] = []
    detected_types: set[str] = set()
    detected_obligations: set[str] = set()
    referenced_sensitive_columns: set[str] = set()
    if files["existing_files"]:
        sensitive_columns = policy_sensitive_columns(policy)
        for raw_path in files["existing_files"]:
            path = Path(str(raw_path))
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                files["errors"].append(f"policy document could not be read: {path}: {exc}")
                continue
            doc_types = classify_policy_document(path, text)
            obligations = extract_policy_obligations(text, sensitive_columns)
            sensitive_refs = sensitive_columns_referenced(text, sensitive_columns)
            detected_types.update(doc_types)
            detected_obligations.update(obligations)
            referenced_sensitive_columns.update(sensitive_refs)
            documents.append(
                {
                    "path": str(path),
                    "types": doc_types,
                    "obligations": obligations,
                    "referenced_sensitive_columns": sensitive_refs,
                }
            )
    files["documents"] = documents
    files["detected_types"] = sorted(detected_types)
    files["detected_obligations"] = sorted(detected_obligations)
    files["referenced_sensitive_columns"] = sorted(referenced_sensitive_columns)
    files["missing_required_types"] = [
        doc_type for doc_type in REQUIRED_POLICY_DOC_TYPES if doc_type not in detected_types
    ]
    files["missing_recommended_types"] = [
        doc_type for doc_type in RECOMMENDED_POLICY_DOC_TYPES if doc_type not in detected_types
    ]
    files["missing_expected_obligations"] = missing_expected_policy_obligations(
        detected_obligations,
        policy,
    )
    if files["status"] == "wired":
        files["status"] = policy_documents_status(files)
    return files


def classify_policy_document(path: Path, text: str) -> list[str]:
    searchable = f"{path.name} {text}".lower()
    doc_types = [
        doc_type
        for doc_type, patterns in POLICY_DOC_TYPE_PATTERNS.items()
        if any(pattern in searchable for pattern in patterns)
    ]
    return sorted(doc_types or ["policy_document"])


def extract_policy_obligations(text: str, sensitive_columns: set[str]) -> list[str]:
    lowered = text.lower()
    obligations = {
        obligation
        for obligation, patterns in POLICY_OBLIGATION_PATTERNS.items()
        if any(pattern in lowered for pattern in patterns)
    }
    if sensitive_columns and ("sensitive" in lowered or "personal data" in lowered):
        obligations.add("sensitive_data_controls")
    return sorted(obligations)


def sensitive_columns_referenced(text: str, sensitive_columns: set[str]) -> list[str]:
    lowered = text.lower()
    referenced = []
    for column in sensitive_columns:
        _, name = column.rsplit(".", 1)
        if name.lower() in lowered or name.replace("_", " ").lower() in lowered:
            referenced.append(column)
    return sorted(referenced)


def missing_expected_policy_obligations(
    detected_obligations: set[str],
    policy: Policy | None,
) -> list[str]:
    expected = {
        "personal_data_minimization",
        "purpose_limited_processing",
        "notice_or_consent",
        "retention_and_deletion",
        "third_party_sharing",
        "security_controls",
    }
    if policy_sensitive_columns(policy):
        expected.add("sensitive_data_controls")
    return sorted(expected - detected_obligations)


def policy_documents_status(policy_docs: dict[str, Any]) -> str:
    if policy_docs.get("errors"):
        return "invalid"
    if not policy_docs.get("existing_files"):
        return "missing"
    if policy_docs.get("missing_required_types") or policy_docs.get("missing_expected_obligations"):
        return "partial"
    return "wired"


def policy_documents_detail(policy_docs: dict[str, Any]) -> str:
    detected_types = ", ".join(policy_docs.get("detected_types", [])) or "none"
    detected_obligations = ", ".join(policy_docs.get("detected_obligations", [])) or "none"
    missing_types = ", ".join(policy_docs.get("missing_required_types", [])) or "none"
    missing_recommended = ", ".join(policy_docs.get("missing_recommended_types", [])) or "none"
    missing_obligations = ", ".join(policy_docs.get("missing_expected_obligations", [])) or "none"
    return (
        f"{len(policy_docs['existing_files'])} documents; types={detected_types}; "
        f"obligations={detected_obligations}; missing_types={missing_types}; "
        f"missing_recommended={missing_recommended}; "
        f"missing_obligations={missing_obligations}"
    )


def inspect_prompt_manifests(
    config_dir: Path,
    config: FileInputConfig,
    policy: Policy | None,
) -> dict[str, Any]:
    files = inspect_file_config(config_dir, config, "prompt or manifest file", confined=False)
    files["manifest_records"] = []
    files["exposed_metrics"] = []
    files["exposed_dimensions"] = []
    files["exposed_tools"] = []
    files["unauthorized_metrics"] = []
    files["unauthorized_dimensions"] = []
    files["sensitive_dimensions_exposed"] = []
    if files["existing_files"]:
        exposed_metrics: set[str] = set()
        exposed_dimensions: set[str] = set()
        exposed_tools: set[str] = set()
        for raw_path in files["existing_files"]:
            path = Path(str(raw_path))
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                files["errors"].append(f"prompt or manifest file could not be read: {path}: {exc}")
                continue
            payload, error = load_prompt_manifest_payload(path, text)
            if error:
                files["errors"].append(error)
                continue
            signals = extract_prompt_manifest_signals(payload)
            exposed_metrics.update(signals["metrics"])
            exposed_dimensions.update(signals["dimensions"])
            exposed_tools.update(signals["tools"])
            files["manifest_records"].append(
                {
                    "path": str(path),
                    "metrics": sorted(signals["metrics"]),
                    "dimensions": sorted(signals["dimensions"]),
                    "tools": sorted(signals["tools"]),
                }
            )
        policy_metrics = set(policy.metrics) if policy is not None else set()
        policy_dimensions = set(policy.dimensions) if policy is not None else set()
        sensitive_dimensions = {
            name for name, dimension in policy.dimensions.items() if dimension.sensitive
        } if policy is not None else set()
        files["exposed_metrics"] = sorted(exposed_metrics)
        files["exposed_dimensions"] = sorted(exposed_dimensions)
        files["exposed_tools"] = sorted(exposed_tools)
        files["unauthorized_metrics"] = sorted(exposed_metrics - policy_metrics) if policy is not None else []
        files["unauthorized_dimensions"] = (
            sorted(exposed_dimensions - policy_dimensions) if policy is not None else []
        )
        files["sensitive_dimensions_exposed"] = sorted(exposed_dimensions & sensitive_dimensions)
    files["status"] = prompt_manifest_status(files)
    return files


def load_prompt_manifest_payload(path: Path, text: str) -> tuple[Any, str | None]:
    if path.suffix == ".json":
        try:
            return json.loads(text), None
        except json.JSONDecodeError as exc:
            return None, f"prompt or manifest JSON could not be parsed: {path}: {exc}"
    if path.suffix in {".yaml", ".yml"}:
        try:
            return yaml.safe_load(text), None
        except yaml.YAMLError as exc:
            return None, f"prompt or manifest YAML could not be parsed: {path}: {exc}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return text, None


def extract_prompt_manifest_signals(payload: Any) -> dict[str, set[str]]:
    signals: dict[str, set[str]] = {"metrics": set(), "dimensions": set(), "tools": set()}
    collect_prompt_manifest_signals(payload, None, signals)
    return signals


def collect_prompt_manifest_signals(
    value: Any,
    context: str | None,
    signals: dict[str, set[str]],
) -> None:
    if isinstance(value, dict):
        if context in signals:
            for key in ("name", "id", "metric", "dimension", "tool"):
                raw_name = value.get(key)
                if isinstance(raw_name, str):
                    signals[context].update(identifier_tokens(raw_name))
        for key, child in value.items():
            child_context = prompt_manifest_context(str(key), context)
            if child_context in signals:
                signals[child_context].update(identifiers_from_manifest_value(child))
            collect_prompt_manifest_signals(child, child_context, signals)
        return
    if isinstance(value, list):
        for item in value:
            collect_prompt_manifest_signals(item, context, signals)
        return
    if isinstance(value, str) and context in signals:
        signals[context].update(identifier_tokens(value))


def prompt_manifest_context(key: str, context: str | None) -> str | None:
    lowered = key.lower().replace("-", "_")
    if "metric" in lowered or lowered in {"measure", "measures"}:
        return "metrics"
    if "dimension" in lowered or lowered in {"field", "fields"}:
        return "dimensions"
    if (
        "tool" in lowered
        or "capability" in lowered
        or "function" in lowered
        or "component" in lowered
    ):
        return "tools"
    return context


def identifiers_from_manifest_value(value: Any) -> set[str]:
    identifiers: set[str] = set()
    if isinstance(value, str):
        identifiers.update(identifier_tokens(value))
    elif isinstance(value, list):
        for item in value:
            identifiers.update(identifiers_from_manifest_value(item))
    elif isinstance(value, dict):
        for key in ("name", "id", "metric", "dimension", "tool"):
            raw_name = value.get(key)
            if isinstance(raw_name, str):
                identifiers.update(identifier_tokens(raw_name))
    return identifiers


def identifier_tokens(value: str) -> set[str]:
    return set(re.findall(r"[A-Za-z][A-Za-z0-9_]*", value))


def prompt_manifest_status(prompt_manifests: dict[str, Any]) -> str:
    if prompt_manifests.get("errors") or prompt_manifests.get("status") == "invalid":
        return "invalid"
    if not prompt_manifests.get("existing_files"):
        return "missing"
    if prompt_manifests.get("unauthorized_metrics") or prompt_manifests.get(
        "unauthorized_dimensions"
    ):
        return "partial"
    recognized = (
        len(prompt_manifests.get("exposed_metrics", []))
        + len(prompt_manifests.get("exposed_dimensions", []))
        + len(prompt_manifests.get("exposed_tools", []))
    )
    return "wired" if recognized else "partial"


def prompt_manifest_detail(prompt_manifests: dict[str, Any]) -> str:
    unauthorized_metrics = ", ".join(prompt_manifests.get("unauthorized_metrics", [])) or "none"
    unauthorized_dimensions = ", ".join(prompt_manifests.get("unauthorized_dimensions", [])) or "none"
    sensitive_dimensions = ", ".join(prompt_manifests.get("sensitive_dimensions_exposed", [])) or "none"
    return (
        f"{len(prompt_manifests['existing_files'])} files; "
        f"metrics={len(prompt_manifests.get('exposed_metrics', []))}; "
        f"dimensions={len(prompt_manifests.get('exposed_dimensions', []))}; "
        f"tools={len(prompt_manifests.get('exposed_tools', []))}; "
        f"unauthorized_metrics={unauthorized_metrics}; "
        f"unauthorized_dimensions={unauthorized_dimensions}; "
        f"sensitive_dimensions={sensitive_dimensions}"
    )


def inspect_declared_files(
    config_dir: Path,
    values: list[str],
    input_name: str,
    *,
    confined: bool,
) -> dict[str, Any]:
    if not values:
        return {
            "status": "missing",
            "files": [],
            "existing_files": [],
            "missing_files": [],
            "errors": [],
        }
    try:
        if confined:
            resolved_paths = resolve_scan_input_paths(config_dir, values, input_name)
        else:
            resolved_paths = []
            for value in values:
                path = resolve_optional_config_path(config_dir, value)
                if path is not None:
                    resolved_paths.append(path)
    except ValueError as exc:
        return {
            "status": "invalid",
            "files": values,
            "existing_files": [],
            "missing_files": [],
            "errors": [str(exc)],
        }
    existing = [path for path in resolved_paths if path.exists()]
    missing = [path for path in resolved_paths if not path.exists()]
    return {
        "status": "wired" if not missing else "invalid",
        "files": [str(path) for path in resolved_paths],
        "existing_files": [str(path) for path in existing],
        "missing_files": [str(path) for path in missing],
        "errors": [f"{input_name} file does not exist: {path}" for path in missing],
    }


def inspect_trace_inputs(
    config: ScanConfig,
    config_path: Path,
    policy: Policy | None,
) -> dict[str, Any]:
    files = inspect_declared_files(
        config_path.parent,
        config.sql_traces.files,
        "sql trace",
        confined=True,
    )
    files["required"] = config.sql_traces.required
    files["records"] = 0
    files["release_decisions"] = 0
    files["release_denials"] = 0
    files["unsafe_release_records"] = 0
    files["semantic_ir_records"] = 0
    files["tenant_scoped_records"] = 0
    files["raw_record_types"] = {}
    files["sources"] = {}
    files["read_tools"] = 0
    files["exports"] = 0
    if files["status"] not in {"wired", "invalid"} or not files["existing_files"]:
        return files

    paths = [Path(str(path)) for path in files["existing_files"]]
    try:
        traces = load_imported_traces(paths)
    except ValueError as exc:
        files["status"] = "invalid"
        files["errors"] = [*files["errors"], str(exc)]
        traces = []
    raw_coverage = trace_raw_coverage(paths)
    files["records"] = len(traces)
    files["release_decisions"] = sum(1 for trace in traces if trace.release_allowed is not None)
    files["release_denials"] = sum(1 for trace in traces if trace.release_allowed is False)
    files["unsafe_release_records"] = count_unsafe_release_records(policy, traces)
    files["semantic_ir_records"] = sum(1 for trace in traces if trace.semantic_ir is not None)
    files["tenant_scoped_records"] = sum(1 for trace in traces if trace.tenant_ids)
    files["sources"] = dict(sorted(Counter(trace.source for trace in traces).items()))
    files.update(raw_coverage)
    return files


def count_unsafe_release_records(policy: Policy | None, traces: list[ImportedTrace]) -> int:
    if policy is None:
        return 0
    oracle = PolicyOracle(policy)
    count = 0
    for trace in traces:
        if trace.release_allowed is not True or trace.semantic_ir is None:
            continue
        if not oracle.authorize(trace.principal, trace.semantic_ir).allowed:
            count += 1
    return count


def trace_raw_coverage(paths: list[Path]) -> dict[str, Any]:
    record_types: Counter[str] = Counter()
    read_tools = 0
    exports = 0
    parse_errors: list[str] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    parse_errors.append(f"{path}:{line_number}: {exc}")
                    continue
                if not isinstance(raw, dict):
                    continue
                record_type = str(raw.get("record_type", "sql_trace"))
                record_types[record_type] += 1
                tool = raw.get("tool")
                tool_kind = str(tool.get("kind", "")) if isinstance(tool, dict) else ""
                source = str(raw.get("source", ""))
                lowered = f"{record_type} {tool_kind} {source}".lower()
                if tool_kind == "read" or "read" in lowered or isinstance(tool, dict):
                    read_tools += 1
                if "export" in lowered or tool_kind == "export":
                    exports += 1
    return {
        "raw_record_types": dict(sorted(record_types.items())),
        "read_tools": read_tools,
        "exports": exports,
        "raw_parse_errors": parse_errors,
    }


def build_coverage_accounting(
    config: ScanConfig,
    sql_traces: dict[str, Any],
    policy_docs: dict[str, Any],
    prompt_manifests: dict[str, Any],
) -> dict[str, Any]:
    tenant_checks = bool(config.tenancy.canonical_predicates or config.tenancy.tenant_columns)
    database_checks = len(config.database.rls_checks) + len(config.database.state_assertions)
    return {
        "dbt_semantic_files": len(config.dbt.files),
        "sql_trace_files": len(config.sql_traces.files),
        "sql_trace_records": int(sql_traces.get("records", 0)),
        "semantic_ir_records": int(sql_traces.get("semantic_ir_records", 0)),
        "tenant_scoped_records": int(sql_traces.get("tenant_scoped_records", 0)),
        "release_decisions": int(sql_traces.get("release_decisions", 0)),
        "release_denials": int(sql_traces.get("release_denials", 0)),
        "unsafe_release_records": int(sql_traces.get("unsafe_release_records", 0)),
        "read_tool_records": int(sql_traces.get("read_tools", 0)),
        "export_records": int(sql_traces.get("exports", 0)),
        "configured_tenant_checks": tenant_checks,
        "configured_rls_checks": len(config.database.rls_checks),
        "configured_state_assertions": len(config.database.state_assertions),
        "database_checks": database_checks,
        "policy_doc_files": len(config.policy_docs.files),
        "policy_doc_types": list(policy_docs.get("detected_types", [])),
        "policy_doc_obligations": list(policy_docs.get("detected_obligations", [])),
        "missing_policy_doc_types": list(policy_docs.get("missing_required_types", [])),
        "missing_recommended_policy_doc_types": list(
            policy_docs.get("missing_recommended_types", [])
        ),
        "missing_policy_obligations": list(policy_docs.get("missing_expected_obligations", [])),
        "prompt_manifest_files": len(config.prompt_manifests.files),
        "prompt_manifest_exposed_metrics": list(prompt_manifests.get("exposed_metrics", [])),
        "prompt_manifest_exposed_dimensions": list(prompt_manifests.get("exposed_dimensions", [])),
        "prompt_manifest_exposed_tools": list(prompt_manifests.get("exposed_tools", [])),
        "prompt_manifest_unauthorized_metrics": list(
            prompt_manifests.get("unauthorized_metrics", [])
        ),
        "prompt_manifest_unauthorized_dimensions": list(
            prompt_manifests.get("unauthorized_dimensions", [])
        ),
        "source_map_files": len(config.source_maps.files),
        "fuzz_enabled": config.fuzz.enabled,
        "ci_gate_enabled": config.gate.fail_on_high_confidence,
        "required_inputs": list(config.gate.required_inputs),
    }


def policy_inventory(
    config: ScanConfig,
    domain_path: Path | None,
    policy: Policy | None,
    error: str | None,
) -> dict[str, Any]:
    path = domain_path / "policy.yaml" if domain_path is not None else f"builtin:{config.domain}/policy.yaml"
    if policy is None:
        return {"status": "invalid", "path": str(path), "error": error}
    return {
        "status": "wired",
        "path": str(path),
        "version": policy.version,
        "roles": len(policy.roles),
        "principals": len(policy.principals),
        "metrics": len(policy.metrics),
        "dimensions": len(policy.dimensions),
        "sensitive_dimensions": sorted(
            name for name, dimension in policy.dimensions.items() if dimension.sensitive
        ),
        "sensitive_columns": sorted(policy_sensitive_columns(policy)),
        "max_rows": sorted({role.max_rows for role in policy.roles.values()}),
        "max_cost": sorted({role.max_cost for role in policy.roles.values()}),
    }


def surface_inventory(
    config: ScanConfig,
    domain_path: Path | None,
    surfaces: SurfaceConfig | None,
    error: str | None,
) -> dict[str, Any]:
    path = (
        domain_path / "surfaces.yaml"
        if domain_path is not None
        else f"builtin:{config.domain}/surfaces.yaml"
    )
    if surfaces is None:
        return {"status": "invalid", "path": str(path), "error": error}
    contracts = set(surfaces.contracts)
    return {
        "status": "wired" if not set(EXPECTED_SURFACES) - contracts else "partial",
        "path": str(path),
        "versions": surfaces.version_dict(),
        "contracts": sorted(surfaces.contracts),
        "missing_contracts": sorted(set(EXPECTED_SURFACES) - contracts),
        "transition_obligations": list(surfaces.transition_obligations),
    }


def inspect_schema(
    config: ScanConfig,
    config_dir: Path,
    policy: Policy | None,
) -> dict[str, Any]:
    schema_path = resolve_optional_config_path(config_dir, config.database.schema_path)
    if schema_path is None:
        return {
            "status": "missing",
            "mode": "not_configured",
            "schema_path": None,
            "tables": [],
            "rls_tables": [],
            "force_rls_tables": [],
            "policies": [],
            "grants": [],
            "views": [],
            "indexes": [],
            "tenant_columns": [],
            "sensitive_columns": [],
        }
    if not schema_path.exists():
        return {
            "status": "invalid",
            "mode": "schema_sql",
            "schema_path": str(schema_path),
            "error": f"schema file does not exist: {schema_path}",
        }
    text = schema_path.read_text(encoding="utf-8")
    table_columns = parse_table_columns(text)
    rls_tables = sorted(parse_alter_table_targets(text, "enable row level security"))
    force_rls_tables = sorted(parse_alter_table_targets(text, "force row level security"))
    policies = parse_policies(text)
    grants = parse_grants(text)
    indexes = parse_indexes(text)
    views = parse_views(text)
    configured_tenant_columns = tenant_columns_for_scope_check(config)
    tenant_columns = sorted(
        {
            *configured_tenant_columns,
            *[
                f"{table}.{column}"
                for table, columns in table_columns.items()
                for column in columns
                if "tenant" in column.lower()
            ],
        }
    )
    sensitive_columns = sorted(
        {
            *policy_sensitive_columns(policy),
            *[
                f"{table}.{column}"
                for table, columns in table_columns.items()
                for column in columns
                if column_has_sensitive_hint(column)
            ],
        }
    )
    return {
        "status": "wired",
        "mode": "schema_sql",
        "schema_path": str(schema_path),
        "tables": sorted(table_columns),
        "columns_by_table": table_columns,
        "rls_tables": rls_tables,
        "force_rls_tables": force_rls_tables,
        "policies": policies,
        "grants": grants,
        "views": views,
        "indexes": indexes,
        "tenant_columns": tenant_columns,
        "sensitive_columns": sensitive_columns,
        "tables_without_rls": sorted(set(table_columns) - set(rls_tables)),
        "tenant_columns_without_indexes": tenant_columns_without_indexes(tenant_columns, indexes),
    }


def parse_table_columns(sql: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    pattern = re.compile(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?P<table>[A-Za-z_][A-Za-z0-9_.\"]*)\s*"
        r"\((?P<body>.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(sql):
        table = normalize_identifier(match.group("table"))
        columns: list[str] = []
        for raw_line in match.group("body").splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.startswith("--") or table_constraint_line(line):
                continue
            column = normalize_identifier(line.split()[0])
            columns.append(column)
        tables[table] = columns
    return dict(sorted(tables.items()))


def table_constraint_line(line: str) -> bool:
    first = line.split()[0].lower()
    return first in {"constraint", "primary", "foreign", "unique", "check", "exclude"}


def parse_alter_table_targets(sql: str, clause: str) -> set[str]:
    pattern = re.compile(
        rf"alter\s+table\s+(?P<table>[A-Za-z_][A-Za-z0-9_.\"]*)\s+{re.escape(clause)}",
        re.IGNORECASE,
    )
    return {normalize_identifier(match.group("table")) for match in pattern.finditer(sql)}


def parse_policies(sql: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"create\s+policy\s+(?P<name>[A-Za-z_][A-Za-z0-9_.\"]*)\s+on\s+"
        r"(?P<table>[A-Za-z_][A-Za-z0-9_.\"]*)\s+(?P<body>.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    policies = []
    for match in pattern.finditer(sql):
        body = normalize_space(match.group("body"))
        policies.append(
            {
                "name": normalize_identifier(match.group("name")),
                "table": normalize_identifier(match.group("table")),
                "uses_current_setting": "current_setting" in body.lower(),
                "mentions_tenant": "tenant" in body.lower(),
            }
        )
    return sorted(policies, key=lambda item: (str(item["table"]), str(item["name"])))


def parse_grants(sql: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"grant\s+(?P<privileges>.*?)\s+on\s+(?:(?P<object_type>schema|table)\s+)?"
        r"(?P<object>[A-Za-z_][A-Za-z0-9_.\"]*)\s+to\s+(?P<role>[A-Za-z_][A-Za-z0-9_.\"]*)",
        re.IGNORECASE,
    )
    grants = []
    for match in pattern.finditer(sql):
        grants.append(
            {
                "privileges": normalize_space(match.group("privileges")).upper(),
                "object_type": (match.group("object_type") or "table").lower(),
                "object": normalize_identifier(match.group("object")),
                "role": normalize_identifier(match.group("role")),
            }
        )
    return sorted(grants, key=lambda item: (item["role"], item["object"], item["privileges"]))


def parse_views(sql: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"create\s+(?:or\s+replace\s+)?(?P<kind>materialized\s+view|view)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_.\"]*)\s+as",
        re.IGNORECASE,
    )
    return [
        {"name": normalize_identifier(match.group("name")), "kind": normalize_space(match.group("kind"))}
        for match in pattern.finditer(sql)
    ]


def parse_indexes(sql: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"create\s+(?P<unique>unique\s+)?index\s+(?:if\s+not\s+exists\s+)?"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_.\"]*)\s+on\s+"
        r"(?P<table>[A-Za-z_][A-Za-z0-9_.\"]*)\s*\((?P<columns>.*?)\)",
        re.IGNORECASE | re.DOTALL,
    )
    indexes = []
    for match in pattern.finditer(sql):
        indexes.append(
            {
                "name": normalize_identifier(match.group("name")),
                "table": normalize_identifier(match.group("table")),
                "columns": normalize_space(match.group("columns")),
                "unique": "true" if match.group("unique") else "false",
            }
        )
    return sorted(indexes, key=lambda item: (item["table"], item["name"]))


def tenant_columns_without_indexes(
    tenant_columns: list[str],
    indexes: list[dict[str, str]],
) -> list[str]:
    missing: list[str] = []
    for column in tenant_columns:
        table = column.rsplit(".", 1)[0] if "." in column else None
        name = column.rsplit(".", 1)[-1]
        has_index = any(
            (table is None or index["table"] == table) and name in index["columns"]
            for index in indexes
        )
        if not has_index:
            missing.append(column)
    return missing


def policy_sensitive_columns(policy: Policy | None) -> set[str]:
    if policy is None:
        return set()
    columns: set[str] = set()
    for dimension in policy.dimensions.values():
        if not dimension.sensitive:
            continue
        match = re.fullmatch(
            r"\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*",
            dimension.column,
        )
        if match:
            columns.add(f"{match.group(1)}.{match.group(2)}")
    return columns


def column_has_sensitive_hint(column: str) -> bool:
    lowered = column.lower()
    return any(hint in lowered for hint in SENSITIVE_COLUMN_HINTS)


def normalize_identifier(value: str) -> str:
    return value.strip().strip('"')


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def build_stack_checks(
    config: ScanConfig,
    config_path: Path,
    policy: Policy | None,
    policy_error: str | None,
    surfaces: SurfaceConfig | None,
    surfaces_error: str | None,
    dbt_files: dict[str, Any],
    sql_traces: dict[str, Any],
    policy_docs: dict[str, Any],
    prompt_manifests: dict[str, Any],
    source_maps: dict[str, Any],
    schema: dict[str, Any],
    coverage: dict[str, Any],
) -> list[dict[str, Any]]:
    config_file = str(config_path)
    stack = [
        stack_item(
            "policy_domain",
            "Policy/domain YAML",
            "wired" if policy is not None else "invalid",
            "manifest",
            [config_file],
            "roles, principals, metrics, dimensions, sensitive fields, max rows, and max cost",
            error=policy_error,
        ),
        stack_item(
            "surface_contracts",
            "Surface contracts",
            surface_status(surfaces),
            "manifest",
            [config_file],
            "manifest, grammar, validator, compiler, database, and release contract inventory",
            error=surfaces_error,
        ),
        stack_item(
            "dbt_semantic_adapter",
            "dbt semantic adapter",
            str(dbt_files["status"]),
            "manifest",
            [config_file, *dbt_files["files"]],
            f"{len(dbt_files['existing_files'])} dbt semantic files configured",
            error=join_errors(dbt_files),
        ),
        stack_item(
            "app_sql_traces",
            "App SQL/tool traces",
            trace_status(sql_traces),
            "validator",
            [config_file, *sql_traces["files"]],
            f"{sql_traces['records']} SQL records, {sql_traces['semantic_ir_records']} with semantic IR",
            error=join_errors(sql_traces),
        ),
        stack_item(
            "tenancy",
            "Tenant-scope checks",
            tenancy_status(config, sql_traces, schema),
            "compiler",
            [config_file],
            tenant_detail(config, sql_traces, schema),
        ),
        stack_item(
            "database_fixture",
            "PostgreSQL fixture",
            database_fixture_status(config, schema),
            "database",
            database_files(config, config_path.parent),
            database_fixture_detail(config, schema),
            error=str(schema.get("error")) if schema.get("status") == "invalid" else None,
        ),
        stack_item(
            "rls_policies",
            "RLS policies and checks",
            rls_status(config, schema),
            "database",
            database_files(config, config_path.parent),
            f"{len(schema.get('policies', []))} schema policies, {len(config.database.rls_checks)} checks",
        ),
        stack_item(
            "state_assertions",
            "Database state assertions",
            "wired" if config.database.state_assertions else "missing",
            "database",
            [config_file],
            f"{len(config.database.state_assertions)} configured assertions",
        ),
        stack_item(
            "release_layer_tests",
            "Release-layer tests",
            release_status(coverage),
            "release",
            [config_file, *sql_traces["files"]],
            (
                f"{coverage['release_decisions']} traces with release decisions; "
                f"{coverage['release_denials']} denial/withhold cases; "
                f"{coverage['unsafe_release_records']} unsafe-release cases"
            ),
        ),
        stack_item(
            "policy_docs_ingestion",
            "Policy/TOS document ingestion",
            policy_documents_status(policy_docs),
            "manifest",
            [config_file, *policy_docs["files"]],
            policy_documents_detail(policy_docs),
            error=join_errors(policy_docs),
        ),
        stack_item(
            "prompt_manifest_checks",
            "Prompt/tool manifest checks",
            str(prompt_manifests["status"]),
            "grammar",
            [config_file, *prompt_manifests["files"]],
            prompt_manifest_detail(prompt_manifests),
            error=join_errors(prompt_manifests),
        ),
        stack_item(
            "source_mapping",
            "Source mapping",
            source_mapping_status(source_maps, sql_traces),
            "compiler",
            [config_file, *source_maps["files"]],
            source_mapping_detail(source_maps, sql_traces),
            error=join_errors(source_maps),
        ),
        stack_item(
            "export_coverage",
            "Export coverage",
            "wired" if int(coverage["export_records"]) > 0 else "missing",
            "release",
            [config_file, *sql_traces["files"]],
            f"{coverage['export_records']} export records, {coverage['read_tool_records']} read-tool records",
        ),
        stack_item(
            "ci_gate",
            "CI gate command",
            ci_gate_status(config),
            "release",
            [config_file],
            (
                f"fail_on_high_confidence={config.gate.fail_on_high_confidence}; "
                f"required_inputs={config.gate.required_inputs}"
            ),
        ),
    ]
    return stack


def stack_item(
    item_id: str,
    title: str,
    status: str,
    owner: str,
    files: list[str],
    detail: str,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": item_id,
        "title": title,
        "status": status,
        "owner": owner,
        "files": files,
        "detail": detail,
    }
    if error:
        item["error"] = error
    return item


def surface_status(surfaces: SurfaceConfig | None) -> str:
    if surfaces is None:
        return "invalid"
    missing = set(EXPECTED_SURFACES) - set(surfaces.contracts)
    return "wired" if not missing else "partial"


def trace_status(sql_traces: dict[str, Any]) -> str:
    if sql_traces["status"] == "invalid":
        return "invalid"
    return "wired" if int(sql_traces.get("records", 0)) > 0 else "missing"


def tenancy_status(
    config: ScanConfig,
    sql_traces: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    configured = bool(config.tenancy.canonical_predicates or config.tenancy.tenant_columns)
    traced = int(sql_traces.get("tenant_scoped_records", 0)) > 0
    introspected = bool(schema.get("tenant_columns"))
    if configured and (traced or introspected):
        return "wired"
    if configured or traced or introspected:
        return "partial"
    return "missing"


def tenant_detail(config: ScanConfig, sql_traces: dict[str, Any], schema: dict[str, Any]) -> str:
    predicates = len(config.tenancy.canonical_predicates)
    columns = len(config.tenancy.tenant_columns)
    schema_columns = len(schema.get("tenant_columns", []))
    return (
        f"{predicates} canonical predicates, {columns} configured tenant columns, "
        f"{schema_columns} schema tenant columns, {sql_traces['tenant_scoped_records']} scoped traces"
    )


def database_fixture_status(config: ScanConfig, schema: dict[str, Any]) -> str:
    configured = bool(
        config.database.schema_path
        or config.database.seed
        or config.database.app_url
        or config.database.admin_url
        or config.database.rls_checks
        or config.database.state_assertions
    )
    if schema.get("status") == "invalid":
        return "invalid"
    return "wired" if configured else "missing"


def database_fixture_detail(config: ScanConfig, schema: dict[str, Any]) -> str:
    return (
        f"schema={bool(config.database.schema_path)}, seed={bool(config.database.seed)}, "
        f"rls_checks={len(config.database.rls_checks)}, "
        f"state_assertions={len(config.database.state_assertions)}, "
        f"introspected_tables={len(schema.get('tables', []))}"
    )


def rls_status(config: ScanConfig, schema: dict[str, Any]) -> str:
    has_schema_policies = bool(schema.get("policies"))
    has_checks = bool(config.database.rls_checks)
    if has_schema_policies and has_checks:
        return "wired"
    if has_schema_policies or has_checks:
        return "partial"
    return "missing"


def release_status(coverage: dict[str, Any]) -> str:
    if int(coverage["release_denials"]) > 0 or int(coverage["unsafe_release_records"]) > 0:
        return "wired"
    if int(coverage["release_decisions"]) > 0:
        return "partial"
    return "missing"


def source_mapping_status(source_maps: dict[str, Any], sql_traces: dict[str, Any]) -> str:
    if source_maps["status"] == "wired":
        return "wired"
    if sql_traces.get("sources"):
        return "partial"
    return str(source_maps["status"])


def source_mapping_detail(source_maps: dict[str, Any], sql_traces: dict[str, Any]) -> str:
    sources = ", ".join(str(source) for source in sql_traces.get("sources", {})) or "none"
    return f"{len(source_maps['existing_files'])} source map files; trace source labels: {sources}"


def ci_gate_status(config: ScanConfig) -> str:
    if config.gate.fail_on_high_confidence and config.gate.required_inputs:
        return "wired"
    if config.gate.fail_on_high_confidence:
        return "partial"
    return "missing"


def database_files(config: ScanConfig, config_dir: Path) -> list[str]:
    files = []
    for value in (config.database.schema_path, config.database.seed):
        path = resolve_optional_config_path(config_dir, value)
        if path is not None:
            files.append(str(path))
    return files


def join_errors(item: dict[str, Any]) -> str | None:
    errors = [str(error) for error in item.get("errors", []) if error]
    return "; ".join(errors) if errors else None


def build_remediation(
    config: ScanConfig,
    config_path: Path,
    stack: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    todos: list[dict[str, Any]] = []
    by_id = {item["id"]: item for item in stack}
    add_todo_if_needed(
        todos,
        by_id,
        "app_sql_traces",
        "Add automatic app trace recording for real read-tool SQL.",
        "validator",
        [str(config_path), "docs/trace-adapters.md", "packages/node/README.md"],
        [
            "uv run policystrata doctor --config {config}",
            "uv run policystrata scan --config {config}",
        ],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "tenancy",
        "Declare canonical tenant predicates and tenant columns for the application schema.",
        "compiler",
        [str(config_path)],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "database_fixture",
        "Add a disposable PostgreSQL schema/seed fixture or sanitized clone connection.",
        "database",
        [str(config_path), "domain/schema.sql", "domain/seed.sql"],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "rls_policies",
        "Add schema RLS policies and at least one configured RLS assertion.",
        "database",
        [str(config_path), "domain/schema.sql"],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "state_assertions",
        "Add database state assertions for expected tenant isolation and release-safe result shape.",
        "database",
        [str(config_path)],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "release_layer_tests",
        "Add traces for denied or contained requests where the release layer must withhold results.",
        "release",
        [str(config_path), "traces.release.jsonl"],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "policy_docs_ingestion",
        "Register privacy policy, terms of service, DPA, security, and internal policy documents.",
        "manifest",
        [
            str(config_path),
            "docs/privacy.md",
            "docs/terms.md",
            "docs/data-processing.md",
            "docs/internal-policy.md",
        ],
        ["uv run policystrata doctor --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "prompt_manifest_checks",
        "Export model-visible prompts, tool manifests, and UI components for policy comparison.",
        "grammar",
        [str(config_path), "policystrata/prompts.json"],
        ["uv run policystrata doctor --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "source_mapping",
        "Attach trace records to code paths, tools, or query builders that produced the SQL.",
        "compiler",
        [str(config_path), "policystrata/source-map.json"],
        ["uv run policystrata doctor --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "export_coverage",
        "Add export/download traces so release gates cover bulk data paths, not just read tools.",
        "release",
        [str(config_path), "traces.exports.jsonl"],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    add_todo_if_needed(
        todos,
        by_id,
        "ci_gate",
        "Require scanner inputs and run the scan command in CI.",
        "release",
        [str(config_path), ".github/workflows/policystrata.yml"],
        ["uv run policystrata scan --config {config}"],
        config_path,
    )
    if config.dbt.files == []:
        todos.append(
            remediation_todo(
                "wire_dbt_semantic_adapter",
                "Add dbt Semantic Layer YAML if this stack uses dbt metrics or measures.",
                "manifest",
                [str(config_path), "semantic_models.yml"],
                [
                    "uv run policystrata check-integration dbt-semantic --domain "
                    f"{config.domain} --path semantic_models.yml",
                    "uv run policystrata scan --config {config}",
                ],
                config_path,
            )
        )
    return todos


def add_todo_if_needed(
    todos: list[dict[str, Any]],
    checks: dict[str, dict[str, Any]],
    check_id: str,
    title: str,
    owner: str,
    files: list[str],
    expected_tests: list[str],
    config_path: Path,
) -> None:
    item = checks.get(check_id)
    if item is None or item["status"] == "wired":
        return
    todos.append(
        remediation_todo(
            f"fix_{check_id}",
            title,
            owner,
            files,
            expected_tests,
            config_path,
            reason=str(item["detail"]),
        )
    )


def remediation_todo(
    todo_id: str,
    title: str,
    owner: str,
    files: list[str],
    expected_tests: list[str],
    config_path: Path,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    formatted_tests = [command.format(config=config_path) for command in expected_tests]
    return {
        "id": todo_id,
        "title": title,
        "owner": owner,
        "files": files,
        "reason": reason,
        "expected_tests": formatted_tests,
        "ci_gate_command": f"uv run policystrata scan --config {config_path}",
    }


def golden_templates() -> list[dict[str, str]]:
    return [
        {
            "name": "basic scanner scaffold",
            "command": "uv run policystrata init-scan --out policystrata",
            "covers": "validator, compiler, imported SQL trace, CI gate starter",
        },
        {
            "name": "Postgres/dbt scanner example",
            "command": "uv run policystrata init-scan postgres_dbt --out policystrata-example",
            "covers": "dbt adapter, trace fixtures, RLS assertions, state assertions",
        },
        {
            "name": "trace recorder recipes",
            "path": "docs/trace-adapters.md",
            "covers": "Next.js, Drizzle, Prisma, SQLAlchemy, Rails, dbt, OpenTelemetry",
        },
        {
            "name": "Node trace SDK",
            "path": "packages/node/README.md",
            "covers": "first-party JSONL records compatible with policystrata scan",
        },
        {
            "name": "GitHub Action gate",
            "path": "docs/github-action.md",
            "covers": "CI command and artifact upload wiring",
        },
    ]


def render_doctor_report(report: dict[str, Any]) -> str:
    stack_rows = [
        [
            str(item["title"]),
            str(item["status"]),
            str(item["owner"]),
            str(item["detail"]),
        ]
        for item in report["stack"]
    ]
    coverage = report["coverage_accounting"]
    coverage_rows = [[key, str(value)] for key, value in coverage.items()]
    policy_documents = report["policy_documents"]
    policy_doc_rows = [
        ["Status", str(policy_documents.get("status"))],
        ["Document types", ", ".join(policy_documents.get("detected_types", [])) or "none"],
        ["Obligations", ", ".join(policy_documents.get("detected_obligations", [])) or "none"],
        ["Missing required types", ", ".join(policy_documents.get("missing_required_types", [])) or "none"],
        [
            "Missing recommended types",
            ", ".join(policy_documents.get("missing_recommended_types", [])) or "none",
        ],
        [
            "Missing obligations",
            ", ".join(policy_documents.get("missing_expected_obligations", [])) or "none",
        ],
        [
            "Referenced sensitive columns",
            ", ".join(policy_documents.get("referenced_sensitive_columns", [])) or "none",
        ],
    ]
    schema = report["database_introspection"]
    db_rows = [
        ["Schema path", str(schema.get("schema_path"))],
        ["Tables", str(len(schema.get("tables", [])))],
        ["RLS tables", ", ".join(schema.get("rls_tables", [])) or "none"],
        ["Policies", str(len(schema.get("policies", [])))],
        ["Tenant columns", ", ".join(schema.get("tenant_columns", [])) or "none"],
        ["Sensitive columns", ", ".join(schema.get("sensitive_columns", [])) or "none"],
    ]
    todo_rows = [
        [
            str(todo["id"]),
            str(todo["owner"]),
            str(todo["title"]),
            str(todo["ci_gate_command"]),
        ]
        for todo in report["remediation"]
    ]
    sections = [
        "# PolicyStrata Doctor",
        f"Config: `{report['config_path']}`",
        f"Domain: `{report['domain']}`",
        "## Stack",
        markdown_table(["Component", "Status", "Owner", "Detail"], stack_rows),
        "## Coverage Accounting",
        markdown_table(["Signal", "Value"], coverage_rows),
        "## Policy Documents",
        markdown_table(["Signal", "Value"], policy_doc_rows),
        "## Database Introspection",
        markdown_table(["Signal", "Value"], db_rows),
        "## Remediation",
        markdown_table(["Todo", "Owner", "Task", "CI gate"], todo_rows)
        if todo_rows
        else "No missing or partial stack wiring detected.",
    ]
    return "\n\n".join(sections) + "\n"

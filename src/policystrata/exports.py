from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal, cast

from policystrata.models import Trace
from policystrata.summary import accounting_status, load_traces, summarize_traces

ExportFormat = Literal["inspect", "benchflow", "policystrata-json"]


def export_run(run_dir: Path, export_format: ExportFormat, out_path: Path) -> dict[str, Any]:
    traces = load_traces(run_dir)
    if export_format == "inspect":
        content = render_inspect_jsonl(traces)
    elif export_format == "benchflow":
        content = render_benchflow_json(traces)
    elif export_format == "policystrata-json":
        content = render_policystrata_json(run_dir, traces)
    else:
        raise ValueError(f"unsupported export format: {export_format}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return {"format": export_format, "records": len(traces), "out": str(out_path)}


def render_policystrata_json(run_dir: Path, traces: list[Trace]) -> str:
    summary = summarize_traces(traces)
    metadata = load_run_metadata(run_dir)
    payload = {
        "version": "policystrata.evidence_export.v1",
        "metadata": {
            "adapter": "policystrata.json.v1",
            "source": "policystrata",
            "requires_llm_api_key": False,
            "authorization_boundary": False,
            "run": metadata,
        },
        "summary": summary.model_dump(mode="json"),
        "counts": {
            "witnessClasses": dict(sorted(Counter(trace.witness_class.value for trace in traces).items())),
            "accountingStatuses": dict(sorted(Counter(accounting_status(trace) for trace in traces).items())),
            "domains": dict(sorted(Counter(trace.domain for trace in traces).items())),
        },
        "traces": [policystrata_evidence_record(trace) for trace in traces],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def load_run_metadata(run_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        return {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        return {}
    return cast(dict[str, Any], metadata)


def policystrata_evidence_record(trace: Trace) -> dict[str, Any]:
    return {
        "id": trace.task_id,
        "domain": trace.domain,
        "principal": trace.principal,
        "mutation": trace.mutation,
        "policyVersion": trace.policy_version,
        "surfaceVersions": trace.surface_versions,
        "semanticIr": trace.semantic_ir.model_dump(mode="json"),
        "expected": {
            "witnessClass": trace.expected_witness_class.value,
            "localizedSurface": trace.expected_localized_surface,
            "containmentLayer": trace.expected_containment_layer,
        },
        "observed": {
            "witnessClass": trace.witness_class.value,
            "localizedSurface": trace.localized_surface,
            "containmentLayer": trace.containment_layer,
            "releaseAllowed": trace.release_decision.allowed,
            "semanticDifference": trace.semantic_difference,
        },
        "accounting": {
            "status": accounting_status(trace),
            "reason": trace.accounting_reason,
        },
        "decisions": {
            "canonicalAllowed": trace.canonical_decision.allowed,
            "releaseAllowed": trace.release_decision.allowed,
            "releaseReasons": trace.release_decision.reasons,
        },
        "artifacts": {
            "witnessPath": trace.witness_path,
            "compiledSqlPresent": bool(trace.compiled_sql),
            "databaseResultKeys": sorted(trace.db_result.keys()),
        },
        "metrics": {
            "latencyMs": trace.latency_ms,
            "cost": trace.cost,
        },
    }


def render_inspect_jsonl(traces: list[Trace]) -> str:
    return "".join(json.dumps(inspect_record(trace), sort_keys=True) + "\n" for trace in traces)


def inspect_record(trace: Trace) -> dict[str, Any]:
    return {
        "id": trace.task_id,
        "input": trace.request,
        "target": {
            "witness_class": trace.expected_witness_class.value,
            "localized_surface": trace.expected_localized_surface,
            "containment_layer": trace.expected_containment_layer,
        },
        "metadata": {
            "adapter": "policystrata.inspect.v1",
            "domain": trace.domain,
            "principal": trace.principal,
            "mutation": trace.mutation,
            "policy_version": trace.policy_version,
            "surface_versions": trace.surface_versions,
            "semantic_ir": trace.semantic_ir.model_dump(mode="json"),
            "compiled_sql": trace.compiled_sql,
            "observed": {
                "witness_class": trace.witness_class.value,
                "localized_surface": trace.localized_surface,
                "containment_layer": trace.containment_layer,
                "release_allowed": trace.release_decision.allowed,
            },
            "scorer": "policystrata_deterministic_trace_contract",
        },
    }


def render_benchflow_json(traces: list[Trace]) -> str:
    payload = {
        "version": "policystrata.benchflow.adapter.v1",
        "environment": {
            "name": "policystrata",
            "kind": "deterministic_policy_regression",
            "requires_llm_api_key": False,
            "authorization_boundary": False,
        },
        "tasks": [benchflow_task(trace) for trace in traces],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def benchflow_task(trace: Trace) -> dict[str, Any]:
    return {
        "id": trace.task_id,
        "scenario": {
            "domain": trace.domain,
            "principal": trace.principal,
            "request": trace.request,
            "semantic_ir": trace.semantic_ir.model_dump(mode="json"),
            "surface_versions": trace.surface_versions,
        },
        "rollout": {
            "compiled_sql": trace.compiled_sql,
            "db_result": trace.db_result,
            "release_decision": trace.release_decision.model_dump(mode="json"),
        },
        "verifier": {
            "type": "policystrata_trace_contract",
            "expected": {
                "witness_class": trace.expected_witness_class.value,
                "localized_surface": trace.expected_localized_surface,
                "containment_layer": trace.expected_containment_layer,
            },
            "observed": {
                "witness_class": trace.witness_class.value,
                "localized_surface": trace.localized_surface,
                "containment_layer": trace.containment_layer,
            },
        },
    }

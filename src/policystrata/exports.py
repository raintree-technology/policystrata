from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from policystrata.models import Trace
from policystrata.summary import load_traces

ExportFormat = Literal["inspect", "benchflow"]


def export_run(run_dir: Path, export_format: ExportFormat, out_path: Path) -> dict[str, Any]:
    traces = load_traces(run_dir)
    if export_format == "inspect":
        content = render_inspect_jsonl(traces)
    elif export_format == "benchflow":
        content = render_benchflow_json(traces)
    else:
        raise ValueError(f"unsupported export format: {export_format}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return {"format": export_format, "records": len(traces), "out": str(out_path)}


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

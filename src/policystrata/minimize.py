from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from policystrata.models import Trace


def minimize_trace(trace: Trace) -> dict[str, Any]:
    return {
        "task_id": trace.task_id,
        "witness_class": trace.witness_class,
        "localized_surface": trace.localized_surface,
        "containment_layer": trace.containment_layer,
        "principal": trace.principal,
        "request": trace.request,
        "semantic_ir": trace.semantic_ir.normalized(),
        "surface_versions": trace.surface_versions,
        "surface_responsibilities": {
            name: contract.responsibilities for name, contract in trace.surface_contracts.items()
        },
        "contract_decisions": {
            name: decision.model_dump() for name, decision in trace.contract_decisions.items()
        },
        "transition_obligations": trace.transition_obligations,
        "compiled_sql": trace.compiled_sql,
        "db_result": trace.db_result,
        "release_allowed": trace.release_decision.allowed,
        "reasons": trace.reasons,
    }


def minimize_witness_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and {"semantic_ir", "compiled_sql", "witness_class"} <= raw.keys():
        return cast(dict[str, Any], raw)
    trace = Trace.model_validate(raw)
    return minimize_trace(trace)

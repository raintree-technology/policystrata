from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from policystrata.models import SemanticQuery, Trace, WitnessClass

DEFAULT_LIMIT = 100
MAX_REDUCTION_ATTEMPTS = 32
TraceReplay = Callable[[SemanticQuery], Trace]


@dataclass(frozen=True)
class ReductionResult:
    trace: Trace
    attempts: int
    accepted: int


def minimize_trace(trace: Trace, replay: TraceReplay | None = None) -> dict[str, Any]:
    if replay is not None and trace.witness_class != WitnessClass.CLEAN:
        trace = reduce_semantic_ir(trace, replay).trace
    return witness_from_trace(trace)


def witness_from_trace(trace: Trace) -> dict[str, Any]:
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


def reduce_semantic_ir(trace: Trace, replay: TraceReplay) -> ReductionResult:
    current = trace
    attempts = 0
    accepted = 0

    while attempts < MAX_REDUCTION_ATTEMPTS:
        changed = False
        for candidate in semantic_reduction_candidates(current.semantic_ir):
            if attempts >= MAX_REDUCTION_ATTEMPTS:
                break
            attempts += 1
            replayed = replay(candidate)
            if preserves_witness(trace, replayed):
                current = replayed
                accepted += 1
                changed = True
                break
        if not changed:
            break

    return ReductionResult(trace=current, attempts=attempts, accepted=accepted)


def semantic_reduction_candidates(query: SemanticQuery) -> list[SemanticQuery]:
    candidates: list[SemanticQuery] = []

    dimensions = list(query.dimensions)
    for index in range(len(dimensions)):
        without_dimension = dimensions[:index] + dimensions[index + 1 :]
        candidates.append(query.model_copy(update={"dimensions": without_dimension}))

    for key in sorted(query.filters):
        filters = dict(query.filters)
        filters.pop(key, None)
        candidates.append(query.model_copy(update={"filters": filters}))

    if query.limit != DEFAULT_LIMIT:
        candidates.append(query.model_copy(update={"limit": DEFAULT_LIMIT}))

    return candidates


def preserves_witness(original: Trace, candidate: Trace) -> bool:
    if candidate.witness_class != original.witness_class:
        return False
    if candidate.localized_surface != original.localized_surface:
        return False
    if candidate.containment_layer != original.containment_layer:
        return False
    if candidate.release_decision.allowed != original.release_decision.allowed:
        return False

    original_contract = original.contract_decisions.get(original.localized_surface)
    candidate_contract = candidate.contract_decisions.get(candidate.localized_surface)
    if original_contract is None or candidate_contract is None:
        return False
    if original_contract.allowed or candidate_contract.allowed:
        return False

    if original.semantic_difference and not candidate.semantic_difference:
        return False
    if original.db_result.get("blocked_by_database") is True:
        return candidate.db_result.get("blocked_by_database") is True

    return True


def minimize_witness_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and {"semantic_ir", "compiled_sql", "witness_class"} <= raw.keys():
        return cast(dict[str, Any], raw)
    trace = Trace.model_validate(raw)
    return minimize_trace(trace)

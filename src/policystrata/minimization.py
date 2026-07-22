"""Post-hoc quantification of witness minimization.

The evidence table reports a single aggregate ("median witness bytes"), which
says nothing about how much the minimizer actually removed or whether the result
is irreducible. This module re-derives, for each non-clean trace in a completed
run, the reduction it went through and reports:

* pre/post witness bytes and the reduction ratio;
* how many dimensions/filters were dropped and whether the limit was reset;
* 1-minimality - whether any single further reduction still preserves the
  witness (if none does, the witness is 1-minimal / irreducible under the
  reducer's move set);
* wall-clock reduction time.

It reconstructs the replay closure exactly as
:func:`policystrata.runner.write_witness_if_needed` does, so the numbers match
what the run produced. It reads a completed run directory and writes a separate
report; it does not change trace serialization or the witness files.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import median
from typing import Any

from policystrata.domain import load_policy, load_surface_config
from policystrata.minimize import (
    reduce_semantic_ir,
    semantic_reduction_candidates,
    witness_from_trace,
)
from policystrata.models import (
    InputModel,
    Policy,
    SemanticQuery,
    SurfaceConfig,
    SurfaceVersions,
    Task,
    Trace,
    WitnessClass,
)
from policystrata.summary import load_traces


class WitnessMinimization(InputModel):
    task_id: str
    witness_class: WitnessClass
    original_bytes: int
    minimized_bytes: int
    reduction_ratio: float
    # Reduction restricted to the semantic IR the reducer actually targets;
    # the full-witness ratio above is diluted by fixed contract scaffolding.
    original_ir_bytes: int
    minimized_ir_bytes: int
    ir_reduction_ratio: float
    dimensions_removed: int
    filters_removed: int
    limit_reset: bool
    attempts: int
    accepted: int
    one_minimal: bool
    reduction_ms: float


class MinimizationReport(InputModel):
    run_dir: str
    domain: str
    total_witnesses: int
    median_reduction_ratio: float
    mean_reduction_ratio: float
    median_ir_reduction_ratio: float
    mean_ir_reduction_ratio: float
    one_minimal_count: int
    one_minimal_rate: float
    median_original_bytes: int
    median_minimized_bytes: int
    total_reduction_ms: float
    witnesses: list[WitnessMinimization]


def _task_from_trace(trace: Trace) -> Task:
    return Task(
        id=trace.task_id,
        domain=trace.domain,
        principal=trace.principal,
        request=trace.request,
        policy_version=trace.policy_version,
        surface_versions=SurfaceVersions.model_validate(trace.surface_versions),
        mutation=trace.mutation,
        semantic_query=trace.semantic_ir,
        expected_witness_class=trace.expected_witness_class,
        expected_localized_surface=trace.expected_localized_surface,
        expected_containment_layer=trace.expected_containment_layer,
    )


def _witness_bytes(witness: dict[str, Any]) -> int:
    return len(json.dumps(witness, sort_keys=True).encode("utf-8"))


def measure_trace(
    policy: Policy,
    surface_config: SurfaceConfig,
    trace: Trace,
) -> WitnessMinimization | None:
    if trace.witness_class == WitnessClass.CLEAN:
        return None

    from policystrata.runner import evaluate_task

    task = _task_from_trace(trace)

    def replay(query: SemanticQuery) -> Trace:
        return evaluate_task(policy, task.model_copy(update={"semantic_query": query}), surface_config)

    original_witness = witness_from_trace(trace)
    original_query = trace.semantic_ir

    started = time.perf_counter()
    result = reduce_semantic_ir(trace, replay)
    reduction_ms = (time.perf_counter() - started) * 1000
    reduced = result.trace
    minimized_witness = witness_from_trace(reduced)

    original_bytes = _witness_bytes(original_witness)
    minimized_bytes = _witness_bytes(minimized_witness)
    ratio = 1.0 - (minimized_bytes / original_bytes) if original_bytes else 0.0

    original_ir_bytes = _witness_bytes(original_query.normalized())
    reduced_ir_bytes = _witness_bytes(reduced.semantic_ir.normalized())
    ir_ratio = 1.0 - (reduced_ir_bytes / original_ir_bytes) if original_ir_bytes else 0.0

    reduced_query = reduced.semantic_ir
    dimensions_removed = len(original_query.dimensions) - len(reduced_query.dimensions)
    filters_removed = len(original_query.filters) - len(reduced_query.filters)
    limit_reset = original_query.limit != reduced_query.limit

    one_minimal = _is_one_minimal(trace, reduced, replay)

    return WitnessMinimization(
        task_id=trace.task_id,
        witness_class=trace.witness_class,
        original_bytes=original_bytes,
        minimized_bytes=minimized_bytes,
        reduction_ratio=ratio,
        original_ir_bytes=original_ir_bytes,
        minimized_ir_bytes=reduced_ir_bytes,
        ir_reduction_ratio=ir_ratio,
        dimensions_removed=dimensions_removed,
        filters_removed=filters_removed,
        limit_reset=limit_reset,
        attempts=result.attempts,
        accepted=result.accepted,
        one_minimal=one_minimal,
        reduction_ms=reduction_ms,
    )


def _is_one_minimal(original: Trace, reduced: Trace, replay: Any) -> bool:
    """A witness is 1-minimal when no single further reduction preserves it."""
    from policystrata.minimize import preserves_witness

    for candidate in semantic_reduction_candidates(reduced.semantic_ir):
        replayed = replay(candidate)
        if preserves_witness(original, replayed):
            return False
    return True


def minimization_report(run_dir: Path, base_path: Path | None = None) -> MinimizationReport:
    traces = load_traces(run_dir)
    domain = _run_domain(run_dir)
    policy = load_policy(domain, base_path)
    surface_config = load_surface_config(domain, base_path)

    measured: list[WitnessMinimization] = []
    for trace in traces:
        entry = measure_trace(policy, surface_config, trace)
        if entry is not None:
            measured.append(entry)

    ratios = [entry.reduction_ratio for entry in measured]
    ir_ratios = [entry.ir_reduction_ratio for entry in measured]
    originals = [entry.original_bytes for entry in measured]
    minimizeds = [entry.minimized_bytes for entry in measured]
    one_minimal = sum(1 for entry in measured if entry.one_minimal)
    total = len(measured)

    return MinimizationReport(
        run_dir=str(run_dir),
        domain=domain,
        total_witnesses=total,
        median_reduction_ratio=median(ratios) if ratios else 0.0,
        mean_reduction_ratio=sum(ratios) / total if total else 0.0,
        median_ir_reduction_ratio=median(ir_ratios) if ir_ratios else 0.0,
        mean_ir_reduction_ratio=sum(ir_ratios) / total if total else 0.0,
        one_minimal_count=one_minimal,
        one_minimal_rate=one_minimal / total if total else 0.0,
        median_original_bytes=int(median(originals)) if originals else 0,
        median_minimized_bytes=int(median(minimizeds)) if minimizeds else 0,
        total_reduction_ms=sum(entry.reduction_ms for entry in measured),
        witnesses=measured,
    )


def _run_domain(run_dir: Path) -> str:
    metadata_path = run_dir / "metadata.json"
    if metadata_path.is_file():
        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
        domain = raw.get("domain")
        if isinstance(domain, str):
            return domain
    # Fall back to the domain recorded on the first trace.
    traces = load_traces(run_dir)
    if traces:
        return traces[0].domain
    raise ValueError(f"cannot determine domain for run: {run_dir}")

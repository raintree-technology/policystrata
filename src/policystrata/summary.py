from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from policystrata.models import Summary, Trace, WitnessClass


def load_traces(run_dir: Path) -> list[Trace]:
    traces_path = run_dir / "traces.jsonl"
    with traces_path.open("r", encoding="utf-8") as handle:
        return [Trace.model_validate(json.loads(line)) for line in handle if line.strip()]


def summarize_run(run_dir: Path) -> Summary:
    return summarize_traces(load_traces(run_dir))


def summarize_traces(traces: list[Trace]) -> Summary:
    total = len(traces)
    if total == 0:
        return empty_summary()

    witness_counts = Counter(trace.witness_class for trace in traces)
    return Summary(
        total=total,
        mutant_kill_rate=1.0 - witness_counts[WitnessClass.CLEAN] / total,
        over_permissive_rate=class_rate(witness_counts, WitnessClass.OVER_PERMISSIVE, total),
        over_restrictive_rate=class_rate(witness_counts, WitnessClass.OVER_RESTRICTIVE, total),
        lowering_violation_rate=class_rate(witness_counts, WitnessClass.LOWERING_VIOLATION, total),
        semantic_drift_rate=class_rate(witness_counts, WitnessClass.SEMANTIC_DRIFT, total),
        unsafe_release_rate=class_rate(witness_counts, WitnessClass.UNSAFE_RELEASE, total),
        containment_rate=trace_rate(traces, lambda trace: trace.containment_layer is not None),
        localization_accuracy=trace_rate(
            traces,
            lambda trace: trace.localized_surface == trace.expected_localized_surface,
        ),
        expected_class_accuracy=trace_rate(
            traces,
            lambda trace: trace.witness_class == trace.expected_witness_class,
        ),
        minimized_witness_count=sum(1 for trace in traces if trace.witness_path),
        avg_latency_ms=sum(trace.latency_ms for trace in traces) / total,
        cost=cost_totals(traces),
    )


def empty_summary() -> Summary:
    return Summary(
        total=0,
        mutant_kill_rate=0.0,
        over_permissive_rate=0.0,
        over_restrictive_rate=0.0,
        lowering_violation_rate=0.0,
        semantic_drift_rate=0.0,
        unsafe_release_rate=0.0,
        containment_rate=0.0,
        localization_accuracy=0.0,
        expected_class_accuracy=0.0,
        minimized_witness_count=0,
        avg_latency_ms=0.0,
        cost={"estimated": 0, "tokens": 0, "usd": 0.0},
    )


def class_rate(counts: Counter[WitnessClass], witness_class: WitnessClass, total: int) -> float:
    return counts[witness_class] / total


def trace_rate(traces: list[Trace], predicate: Callable[[Trace], bool]) -> float:
    return sum(1 for trace in traces if predicate(trace)) / len(traces)


def cost_totals(traces: list[Trace]) -> dict[str, int | float]:
    return {
        "estimated": sum(int(trace.cost.get("estimated", 0)) for trace in traces),
        "tokens": sum(int(trace.cost.get("tokens", 0)) for trace in traces),
        "usd": sum(float(trace.cost.get("usd", 0.0)) for trace in traces),
    }

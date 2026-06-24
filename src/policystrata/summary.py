from __future__ import annotations

import json
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

    return Summary(
        total=total,
        mutant_kill_rate=rate([trace.witness_class != WitnessClass.CLEAN for trace in traces]),
        over_permissive_rate=rate([trace.witness_class == WitnessClass.OVER_PERMISSIVE for trace in traces]),
        over_restrictive_rate=rate(
            [trace.witness_class == WitnessClass.OVER_RESTRICTIVE for trace in traces]
        ),
        lowering_violation_rate=rate(
            [trace.witness_class == WitnessClass.LOWERING_VIOLATION for trace in traces]
        ),
        semantic_drift_rate=rate([trace.witness_class == WitnessClass.SEMANTIC_DRIFT for trace in traces]),
        unsafe_release_rate=rate([trace.witness_class == WitnessClass.UNSAFE_RELEASE for trace in traces]),
        containment_rate=rate([trace.containment_layer is not None for trace in traces]),
        localization_accuracy=rate(
            [trace.localized_surface == trace.expected_localized_surface for trace in traces]
        ),
        expected_class_accuracy=rate(
            [trace.witness_class == trace.expected_witness_class for trace in traces]
        ),
        minimized_witness_count=sum(1 for trace in traces if trace.witness_path),
        avg_latency_ms=sum(trace.latency_ms for trace in traces) / total,
        cost={
            "estimated": sum(int(trace.cost.get("estimated", 0)) for trace in traces),
            "tokens": sum(int(trace.cost.get("tokens", 0)) for trace in traces),
            "usd": sum(float(trace.cost.get("usd", 0.0)) for trace in traces),
        },
    )


def rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value) / len(values)

from __future__ import annotations

from pathlib import Path

from policystrata.models import Trace, WitnessClass
from policystrata.runner import run_suite
from policystrata.summary import summarize_traces

DEMO_DOMAIN = "support_saas"
DEMO_SUITE = "seeded"


def run_demo(out_dir: Path) -> str:
    traces = run_suite(DEMO_DOMAIN, DEMO_SUITE, out_dir)
    return render_demo_output(traces, out_dir)


def render_demo_output(traces: list[Trace], out_dir: Path) -> str:
    summary = summarize_traces(traces)
    drift_count = sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN)
    example = representative_trace(traces)

    lines = [
        "PolicyStrata demo",
        f"- Loaded built-in domain: {DEMO_DOMAIN}",
        f"- Ran {summary.total} deterministic cases with no LLM API key",
        f"- Detected {drift_count} policy-drift witnesses",
        f"- Drift classes: {format_witness_class_counts(witness_class_counts(traces))}",
    ]
    if example is not None:
        localized_contract = example.contract_decisions.get(example.localized_surface)
        contract_reason = (
            localized_contract.reasons[0]
            if localized_contract is not None and localized_contract.reasons
            else "declared surface responsibility failed"
        )
        versions = ", ".join(
            f"{surface}={version}" for surface, version in example.surface_versions.items()
        )
        intended = example.db_result.get("intended_value")
        actual = example.db_result.get("actual_value")
        lines.extend(
            [
                "",
                "Worked example: stale tenant-key lowering",
                f"- Request: {example.request}",
                f"- Principal: {example.principal}",
                f"- Version vector: {versions}",
                f"- Canonical decision: {'allow' if example.canonical_decision.allowed else 'deny'}",
                (
                    "- First violated transition: "
                    f"{example.localized_surface} ({example.witness_class.value})"
                ),
                f"- Why: {contract_reason}",
                f"- Distinguishing result before containment: canonical={intended}, lowered={actual}",
                f"- Containment: {example.containment_layer or 'none'}",
                f"- Release: {'allowed' if example.release_decision.allowed else 'blocked'}",
                f"- Witness: {out_dir / (example.witness_path or '')}",
            ]
        )
    lines.extend(
        [
            f"- Wrote traces: {out_dir / 'traces.jsonl'}",
            f"- Wrote summary: {out_dir / 'summary.json'}",
            f"- Wrote minimized witnesses: {out_dir / 'witnesses'}",
            f"Next: policystrata summarize {out_dir}",
        ]
    )
    return "\n".join(lines) + "\n"


def first_drift_trace(traces: list[Trace]) -> Trace | None:
    return next((trace for trace in traces if trace.witness_class != WitnessClass.CLEAN), None)


def representative_trace(traces: list[Trace]) -> Trace | None:
    tenant_key_example = next(
        (trace for trace in traces if trace.mutation == "compiler_uses_old_tenant_key"),
        None,
    )
    return tenant_key_example or first_drift_trace(traces)


def witness_class_counts(traces: list[Trace]) -> dict[WitnessClass, int]:
    counts = dict.fromkeys(WitnessClass, 0)
    for trace in traces:
        counts[trace.witness_class] += 1
    return counts


def format_witness_class_counts(counts: dict[WitnessClass, int]) -> str:
    non_clean_counts = [
        f"{witness_class.value}={count}"
        for witness_class, count in counts.items()
        if witness_class != WitnessClass.CLEAN and count > 0
    ]
    if not non_clean_counts:
        return "none"
    return ", ".join(non_clean_counts)

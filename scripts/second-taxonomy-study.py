#!/usr/bin/env python3
"""Cross-check the v1 mutation registry against LASM's independent stack taxonomy.

Chu's Layered Attack Surface Model (LASM), derived from a survey of 116 papers, organizes
agent-security work across seven architectural layers and four temporal classes. This study asks
where PolicyStrata's materialized benchmark cases land in that independent vocabulary. It does
not treat the survey as a field distribution or the mapping below as author-validated.

Usage:
    uv run python scripts/second-taxonomy-study.py [--run-root runs/final]
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from policystrata.mutations import MUTATIONS

SUITES = (
    "support-seeded",
    "support-generated",
    "support-heldout-v1",
    "finance-seeded",
    "finance-heldout-v1",
    "analytics-clickhouse-seeded",
    "analytics-clickhouse-generated",
)

SOURCE: dict[str, Any] = {
    "citation": (
        "Chu, A Systematic Survey of Security Threats and Defenses in LLM-Based AI Agents: "
        "A Layered Attack Surface Framework, arXiv:2604.23338"
    ),
    "authored_by": "external",
    "papers_surveyed": 116,
    "layers": [
        "Foundation",
        "Cognitive",
        "Memory",
        "Tool Execution",
        "Multi-Agent Coordination",
        "Ecosystem",
        "Governance",
    ],
    "temporal_classes": [
        "instantaneous",
        "session-persistent",
        "cross-session cumulative",
        "sub-session-stack",
    ],
}

OPERATOR_LAYER = {
    "stale_metric_alias_manifest": "Cognitive",
    "grammar_permits_forbidden_dimension": "Cognitive",
    "validator_omits_sensitive_column": "Tool Execution",
    "cost_estimate_ignores_expansion": "Tool Execution",
    "gross_net_metric_drift": "Tool Execution",
    "fanout_join_drift": "Tool Execution",
    "compiler_removes_distinct": "Tool Execution",
    "compiler_inner_join_drops_rows": "Tool Execution",
    "fiscal_calendar_mismatch": "Tool Execution",
    "materialized_view_lineage_drop": "Tool Execution",
    "timezone_bucket_drift": "Tool Execution",
    "uniq_to_count_drift": "Tool Execution",
    "compiler_drops_tenant_predicate": "Governance",
    "compiler_uses_old_tenant_key": "Governance",
    "compiler_swaps_tenant_account_id": "Governance",
    "db_rls_old_ownership_field": "Governance",
    "app_deny_missing_db_policy": "Governance",
    "clickhouse_row_policy_missing_project_filter": "Governance",
    "distributed_table_policy_gap": "Governance",
    "clickhouse_row_policy_readonly_assumption_violation": "Governance",
    "aggregate_small_cohort_release": "Governance",
    "sample_clause_release_drift": "Governance",
}


def operator_counts(run_root: Path) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    for suite in SUITES:
        path = run_root / suite / "traces.jsonl"
        if not path.exists():
            raise SystemExit(f"missing {path}; run scripts/reproduce-final.sh first")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                counts[json.loads(line)["mutation"]] += 1
    return counts


def build_report(counts: collections.Counter[str]) -> dict[str, Any]:
    if set(OPERATOR_LAYER) != set(MUTATIONS) or set(counts) != set(MUTATIONS):
        raise SystemExit(
            "LASM map, registry, and traces are out of sync: "
            f"map_only={sorted(set(OPERATOR_LAYER) - set(MUTATIONS))} "
            f"registry_only={sorted(set(MUTATIONS) - set(OPERATOR_LAYER))} "
            f"trace_only={sorted(set(counts) - set(MUTATIONS))}"
        )

    layer_rows = []
    for layer in SOURCE["layers"]:
        operators = sorted(op for op, mapped in OPERATOR_LAYER.items() if mapped == layer)
        layer_rows.append(
            {
                "layer": layer,
                "coverage": "covered" if operators else "outside",
                "operators": operators,
                "operator_count": len(operators),
                "cases": sum(counts[op] for op in operators),
            }
        )

    total = sum(counts.values())
    return {
        "source": SOURCE,
        "mapping_status": "PolicyStrata-author judgement; LASM author has not reviewed it",
        "totals": {
            "benchmark_cases": total,
            "registry_operators": len(MUTATIONS),
            "layers_covered": sum(bool(row["operators"]) for row in layer_rows),
            "layers_outside": sum(not row["operators"] for row in layer_rows),
            "temporal_classes_covered": 1,
            "temporal_classes_outside": 3,
        },
        "layers": layer_rows,
        "temporality": [
            {
                "class": temporal,
                "coverage": "covered" if temporal == "instantaneous" else "outside",
                "cases": total if temporal == "instantaneous" else 0,
            }
            for temporal in SOURCE["temporal_classes"]
        ],
        "operator_cases": dict(sorted(counts.items())),
    }


def render_markdown(report: dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "# Second External Taxonomy Cross-Check",
        "",
        "The first external comparison uses Wang et al.'s eight data-agent vulnerabilities.",
        "This independent second comparison uses Chu's Layered Attack Surface Model (LASM), a",
        "7-layer by 4-timescale taxonomy derived from a survey of 116 agent-security papers",
        "(arXiv:2604.23338). LASM asks *where and when* a failure occurs, so it tests a different",
        "axis than the first vulnerability-name comparison.",
        "",
        "The mapping is a PolicyStrata-author judgement recorded in",
        "`scripts/second-taxonomy-study.py`; Chu did not review it. Counts come from the same",
        "materialized 1720 benchmark traces as the paper.",
        "",
        "## Result",
        "",
        f"- PolicyStrata covers {totals['layers_covered']} of 7 LASM layers: Cognitive, Tool",
        "  Execution, and Governance.",
        "- All 1720 cases measure an instantaneous, single-request consequence. The benchmark",
        "  has no session-persistent, cross-session-cumulative, or sub-session-stack case.",
        "- The cross-check therefore confirms the paper's declared boundary and exposes it more",
        "  sharply: v1 checks contract and enforcement drift after intent formation, not model",
        "  foundations, memory, agent coordination, or ecosystem compromise.",
        "",
        "## Architectural layers",
        "",
        "| LASM layer | Coverage | Operators | Cases |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in report["layers"]:
        lines.append(
            f"| {row['layer']} | {row['coverage']} | {row['operator_count']} | {row['cases']} |"
        )
    lines += [
        "",
        "## Temporal classes",
        "",
        "| LASM temporal class | Coverage | Cases |",
        "| --- | --- | ---: |",
    ]
    for row in report["temporality"]:
        lines.append(f"| {row['class']} | {row['coverage']} | {row['cases']} |")
    lines += [
        "",
        "A deployed drift can remain present across sessions, but the v1 benchmark does not model",
        "state accumulation or propagation: each case scores one request from a fixed faulty",
        "state. Calling those cases cross-session would overstate what was executed.",
        "",
        "## Operator mapping",
        "",
    ]
    for row in report["layers"]:
        if row["operators"]:
            lines.append(
                f"**{row['layer']}.** "
                + ", ".join(f"`{operator}`" for operator in row["operators"])
                + "."
            )
            lines.append("")
    lines += [
        "## Limits",
        "",
        "- LASM is a broad agent-security survey taxonomy, not a data-agent fault distribution.",
        "- Layer agreement is structural overlap, not evidence of production recall.",
        "- The mapping has not been reviewed by the LASM author.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "scripts/reproduce-final.sh",
        "uv run python scripts/second-taxonomy-study.py",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, default=Path("runs/final"))
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("studies/second-taxonomy-coverage.json"),
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("docs/second-taxonomy-coverage.md"),
    )
    args = parser.parse_args()

    report = build_report(operator_counts(args.run_root))
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                **report["totals"],
                "out_json": str(args.out_json),
                "out_md": str(args.out_md),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

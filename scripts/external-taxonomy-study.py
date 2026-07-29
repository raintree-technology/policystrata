#!/usr/bin/env python3
"""Compare the v1 mutation registry against an independently authored fault taxonomy.

The registry in ``policystrata.mutations`` was written by the same authors as the
detector, so its coverage of the total 1720-case benchmark says nothing about how
well it matches faults other people find in real data agents. This study measures
that overlap against the eight data-agent vulnerabilities (V1-V8) of Wang et al.,
"Data Agents Under Attack: Vulnerabilities in LLM-Driven Analytical Systems"
(arXiv:2606.08661), which were derived independently and evaluated on six systems
including two production cloud analytics services.

The operator-to-vulnerability mapping below is a human judgement and is stated as
one. Everything else -- case counts, per-class totals, unmapped remainder -- is
derived from the materialized traces of a reproduction run, so the published
numbers cannot drift away from the artifact.

Usage:
    uv run python scripts/external-taxonomy-study.py [--run-root runs/final]
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

from policystrata.mutations import MUTATIONS

SOURCE = {
    "citation": "Wang et al., Data Agents Under Attack, arXiv:2606.08661",
    "authored_by": "external",
    "systems_evaluated": 6,
    "vulnerability_count": 8,
}

DEFAULT_SUITES = (
    "support-seeded",
    "support-generated",
    "support-heldout-v1",
    "finance-seeded",
    "finance-heldout-v1",
    "analytics-clickhouse-seeded",
    "analytics-clickhouse-generated",
)


@dataclass(frozen=True)
class Vulnerability:
    id: str
    layer: str
    name: str
    coverage: str
    rationale: str


TAXONOMY: tuple[Vulnerability, ...] = (
    Vulnerability(
        "V1",
        "interpretation",
        "Implicit Trust Bias",
        "outside",
        "v1 begins at a typed semantic plan. It models no conflict between data "
        "assets and no precedence rule for resolving one.",
    ),
    Vulnerability(
        "V2",
        "interpretation",
        "Lack of Data Source Verification",
        "outside",
        "v1 treats database rows as trusted state, not as a channel that can "
        "carry instructions, so database-resident prompt injection is unmodelled.",
    ),
    Vulnerability(
        "V3",
        "execution",
        "Uncontrolled Query Cost",
        "covered",
        "The canonical policy declares per-role row and cost bounds and the "
        "compiler contract checks the lowered query against them. v1 checks a "
        "declared static estimate, not measured runtime resource consumption.",
    ),
    Vulnerability(
        "V4",
        "execution",
        "Cross-Engine Semantic Inconsistency",
        "partial",
        "The semantic oracle compares a reference interpreter against the "
        "lowered query under declared NULL, timezone, and tolerance rules, and "
        "two operators are date-semantics divergence exactly. v1 models one "
        "execution engine, so it finds reference-versus-SQL divergence and not "
        "SQL-versus-Python divergence.",
    ),
    Vulnerability(
        "V5",
        "execution",
        "Unbounded Multi-Step Query Chains",
        "outside",
        "v1 scores single-request, read-only analytics and has no multi-step budget.",
    ),
    Vulnerability(
        "V6",
        "policy",
        "Security Policy Forgetting under Context Pressure",
        "outside",
        "This is a property of the model context. v1's manifest operators model "
        "stale exposure, which is a deployed artifact being out of date, not "
        "policy being evicted from a context window at runtime.",
    ),
    Vulnerability(
        "V7",
        "policy",
        "Over-Privileged Database Connection",
        "covered",
        "The largest overlap. Every operator here is principal or tenant identity "
        "failing to survive a transition, or a runtime role carrying more "
        "privilege than the policy assumed.",
    ),
    Vulnerability(
        "V8",
        "policy",
        "Lack of Compositional Leakage Control",
        "outside",
        "v1 release is stateless and single-query by declaration. It checks a "
        "per-query cohort threshold and sampling disclosure, but tracks no "
        "cumulative disclosure across a session, which is what V8 names.",
    ),
)

OPERATOR_MAP: dict[str, str | None] = {
    "cost_estimate_ignores_expansion": "V3",
    "gross_net_metric_drift": "V4",
    "fanout_join_drift": "V4",
    "compiler_removes_distinct": "V4",
    "compiler_inner_join_drops_rows": "V4",
    "fiscal_calendar_mismatch": "V4",
    "materialized_view_lineage_drop": "V4",
    "timezone_bucket_drift": "V4",
    "uniq_to_count_drift": "V4",
    "compiler_drops_tenant_predicate": "V7",
    "compiler_uses_old_tenant_key": "V7",
    "compiler_swaps_tenant_account_id": "V7",
    "db_rls_old_ownership_field": "V7",
    "app_deny_missing_db_policy": "V7",
    "clickhouse_row_policy_missing_project_filter": "V7",
    "distributed_table_policy_gap": "V7",
    "clickhouse_row_policy_readonly_assumption_violation": "V7",
    "stale_metric_alias_manifest": None,
    "grammar_permits_forbidden_dimension": None,
    "validator_omits_sensitive_column": None,
    "aggregate_small_cohort_release": None,
    "sample_clause_release_drift": None,
}

UNMAPPED_RATIONALE = (
    "The external study fixes an adversary who controls only the user prompt and "
    "uploaded data, and treats the policy set as given. These operators model an "
    "update desynchronizing a surface with no adversary present: a retired alias "
    "still advertised to the model, a grammar still admitting a dimension policy "
    "has retired, a validator not yet updated for a newly sensitive column, and "
    "two release rules that can themselves drift. They are outside an attack "
    "taxonomy by construction, not by oversight."
)


def operator_counts(run_root: pathlib.Path, suites: tuple[str, ...]) -> collections.Counter[str]:
    counts: collections.Counter[str] = collections.Counter()
    for suite in suites:
        traces = run_root / suite / "traces.jsonl"
        if not traces.exists():
            raise SystemExit(f"missing {traces}; run scripts/reproduce-final.sh first or pass --run-root")
        for line in traces.read_text().splitlines():
            if line.strip():
                counts[json.loads(line)["mutation"]] += 1
    return counts


def build_report(counts: collections.Counter[str]) -> dict[str, Any]:
    unknown = set(counts) - set(OPERATOR_MAP)
    missing = set(OPERATOR_MAP) - set(MUTATIONS)
    unmapped_registry = set(MUTATIONS) - set(OPERATOR_MAP)
    if unknown or missing or unmapped_registry:
        raise SystemExit(
            "operator map is out of sync with the registry: "
            f"unknown_in_traces={sorted(unknown)} "
            f"not_in_registry={sorted(missing)} "
            f"registry_not_mapped={sorted(unmapped_registry)}"
        )

    per_vuln: dict[str, dict[str, Any]] = {}
    for vuln in TAXONOMY:
        ops = sorted(op for op, vid in OPERATOR_MAP.items() if vid == vuln.id)
        per_vuln[vuln.id] = {
            "id": vuln.id,
            "layer": vuln.layer,
            "name": vuln.name,
            "coverage": vuln.coverage,
            "rationale": vuln.rationale,
            "operators": ops,
            "operator_count": len(ops),
            "cases": sum(counts[op] for op in ops),
        }

    unmapped_ops = sorted(op for op, vid in OPERATOR_MAP.items() if vid is None)
    total = sum(counts.values())
    mapped_cases = sum(v["cases"] for v in per_vuln.values())
    unmapped_cases = sum(counts[op] for op in unmapped_ops)
    assert mapped_cases + unmapped_cases == total, "case accounting does not close"

    covered = [v for v in per_vuln.values() if v["coverage"] == "covered"]
    partial = [v for v in per_vuln.values() if v["coverage"] == "partial"]
    outside = [v for v in per_vuln.values() if v["coverage"] == "outside"]

    return {
        "source": SOURCE,
        "totals": {
            "benchmark_cases": total,
            "registry_operators": len(MUTATIONS),
            "external_vulnerabilities": len(TAXONOMY),
            "vulnerabilities_covered": len(covered),
            "vulnerabilities_partial": len(partial),
            "vulnerabilities_outside": len(outside),
            "cases_mapped_to_external": mapped_cases,
            "cases_without_external_counterpart": unmapped_cases,
        },
        "vulnerabilities": [per_vuln[v.id] for v in TAXONOMY],
        "unmapped": {
            "operators": unmapped_ops,
            "cases": unmapped_cases,
            "rationale": UNMAPPED_RATIONALE,
        },
        "operator_cases": dict(sorted(counts.items())),
    }


def render_markdown(report: dict[str, Any]) -> str:
    t = report["totals"]
    lines = [
        "# External Fault-Taxonomy Coverage",
        "",
        "PolicyStrata's 22 mutation operators were authored alongside its detector, so their",
        "coverage of the 1720-case benchmark measures internal consistency only. This study",
        "measures the registry against a fault vocabulary nobody on this project wrote: the",
        "eight data-agent vulnerabilities (V1-V8) of Wang et al., *Data Agents Under Attack*",
        "(arXiv:2606.08661), derived from a systematic audit and evaluated on six data agents",
        "including two production cloud analytics services.",
        "",
        "The operator-to-vulnerability mapping is a human judgement, recorded in",
        "`scripts/external-taxonomy-study.py` so it can be argued with. Case counts are derived",
        "from the materialized traces of `scripts/reproduce-final.sh`.",
        "",
        "## Result",
        "",
        f"- {t['vulnerabilities_covered']} of {t['external_vulnerabilities']} external"
        " vulnerability classes are covered by the v1 model,"
        f" {t['vulnerabilities_partial']} partially, and {t['vulnerabilities_outside']} fall outside it.",
        f"- {t['cases_mapped_to_external']} of {t['benchmark_cases']} benchmark cases instantiate a"
        " drift shape the external taxonomy also names.",
        f"- {t['cases_without_external_counterpart']} cases have no counterpart there, for a"
        " reason given below.",
        "",
        "Every class that falls outside does so because of a v1 scope boundary the paper already",
        "declares -- single-request, read-only, starting after intent formation, stateless release.",
        "That is the useful reading of this table: the exclusions are the declared scope, not gaps",
        "discovered after the fact.",
        "",
        "## Coverage by external vulnerability",
        "",
        "| Ext. | Layer | Vulnerability | v1 coverage | Operators | Cases |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for v in report["vulnerabilities"]:
        lines.append(
            f"| {v['id']} | {v['layer']} | {v['name']} | {v['coverage']} | "
            f"{v['operator_count']} | {v['cases']} |"
        )
    lines += [
        "",
        "## Why each class lands where it does",
        "",
    ]
    for v in report["vulnerabilities"]:
        lines.append(f"**{v['id']} {v['name']} — {v['coverage']}.** {v['rationale']}")
        if v["operators"]:
            lines.append("")
            lines.append("Operators: " + ", ".join(f"`{op}`" for op in v["operators"]) + ".")
        lines.append("")
    lines += [
        "## Cases with no external counterpart",
        "",
        f"{report['unmapped']['cases']} cases across "
        f"{len(report['unmapped']['operators'])} operators: "
        + ", ".join(f"`{op}`" for op in report["unmapped"]["operators"])
        + ".",
        "",
        report["unmapped"]["rationale"],
        "",
        "This is the direction of the comparison that is easy to miss. The two taxonomies differ",
        "in threat model, not just in scope: the external study asks what an adversary can induce,",
        "and PolicyStrata asks what an update can break. Neither subsumes the other, and a stack",
        "that only defends against one of them is unprotected against the other.",
        "",
        "## Limits",
        "",
        "- The mapping is our reading of another group's taxonomy. They did not review it.",
        "- Agreement on a fault *shape* is not evidence that PolicyStrata would detect that fault",
        "  in the systems where they observed it; those runs used live agents and adversarial",
        "  prompts, and PolicyStrata scores a deterministic simulator.",
        "- One external taxonomy is not the field distribution. It bounds our registry against a",
        "  second opinion; it does not turn 1720/1720 into recall.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "scripts/reproduce-final.sh",
        "uv run python scripts/external-taxonomy-study.py",
        "```",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=pathlib.Path, default=pathlib.Path("runs/final"))
    parser.add_argument(
        "--out-json", type=pathlib.Path, default=pathlib.Path("studies/external-taxonomy-coverage.json")
    )
    parser.add_argument(
        "--out-md", type=pathlib.Path, default=pathlib.Path("docs/external-taxonomy-coverage.md")
    )
    args = parser.parse_args(argv)

    counts = operator_counts(args.run_root, DEFAULT_SUITES)
    report = build_report(counts)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2) + "\n")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(render_markdown(report))

    t = report["totals"]
    print(
        json.dumps(
            {
                "covered": t["vulnerabilities_covered"],
                "partial": t["vulnerabilities_partial"],
                "outside": t["vulnerabilities_outside"],
                "cases_mapped": t["cases_mapped_to_external"],
                "cases_unmapped": t["cases_without_external_counterpart"],
                "out_json": str(args.out_json),
                "out_md": str(args.out_md),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

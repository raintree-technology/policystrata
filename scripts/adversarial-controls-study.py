#!/usr/bin/env python
"""Adversarial clean-control precision study.

Generates 1000+ adversarial clean controls per domain, runs the detector, and
reports its false-positive rate alongside baseline false-positive rates.
Deterministic; no LLM API key required.

Usage:
    uv run python scripts/adversarial-controls-study.py --out runs/adv-controls
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policystrata.baselines import BASELINES, evaluate_false_positive_runs
from policystrata.domain import BUILTIN_DOMAINS
from policystrata.runner import run_suite
from policystrata.summary import summarize_run

# Baselines whose predicate references the detector's own localized_surface /
# witness_class output. On CLEAN traces that field defaults to "release", so
# their "false positives" here are an artifact, not a deployable checker's error.
_INTERNAL_ARTIFACT_BASELINES = frozenset(
    {
        "grammar_only",
        "sql_ast_policy_checker",
        "release_filter_only",
        "lineage_only",
        "sql_snapshot",
        "db_rls_only",
        "db_policy_only",
        "defense_in_depth_stack",
        "defense_in_depth_stack_v2",
        "final_answer_only",
        "semantic_validator_only",
    }
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adversarial clean-control precision study.")
    parser.add_argument("--out", type=Path, default=Path("runs/adv-controls"))
    parser.add_argument("--count", type=int, default=1000)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    combined: dict[str, object] = {}
    for domain in BUILTIN_DOMAINS:
        run_dir = args.out / domain
        run_suite(domain, "adversarial_clean_controls", run_dir, generated_count=args.count)
        summary = summarize_run(run_dir)
        fp = evaluate_false_positive_runs([run_dir])
        deployable = {
            name: stats
            for name, stats in fp.items()
            if name not in _INTERNAL_ARTIFACT_BASELINES
        }
        combined[domain] = {
            "total": summary.total,
            "detector_false_positives": summary.false_positives,
            "deployable_baseline_false_positives": deployable,
        }
        worst = max(deployable.values(), key=lambda s: s["false_positives"])
        print(
            f"{domain}: n={summary.total} detector_fp={summary.false_positives} "
            f"worst_deployable_baseline_fp={int(worst['false_positives'])}"
        )

    (args.out / "combined.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _ = BASELINES  # referenced for documentation of the full baseline set
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

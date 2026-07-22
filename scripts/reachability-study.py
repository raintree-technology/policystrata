#!/usr/bin/env python3
"""Run the natural-language reachability study over a domain's mutation operators.

Default run uses the free, deterministic stub client (harness verification only,
not reachability evidence):

    uv run python scripts/reachability-study.py --out runs/reachability-stub

Real-model run (INCURS API COST). It requires the `anthropic` package
(`pip install anthropic`; it is not a policystrata dependency), the
ANTHROPIC_API_KEY environment variable, and an explicit
POLICYSTRATA_ALLOW_PAID_CALLS=1 opt-in:

    POLICYSTRATA_ALLOW_PAID_CALLS=1 uv run python scripts/reachability-study.py \
        --client anthropic --out runs/reachability-real

Upper bound on paid API calls: cases x paraphrases x max attempts, plus
2 x max attempts for the manifest-skew probe. The model id defaults to
claude-sonnet-5 and can be overridden with POLICYSTRATA_REACHABILITY_MODEL.
See docs/reachability.md.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from policystrata.reachability import (
    DEFAULT_PARAPHRASE_COUNT,
    DEFAULT_REACHABILITY_SEED,
    AnthropicClient,
    DeterministicStubClient,
    ModelClient,
    ReachabilityBudget,
    build_cases,
    run_manifest_skew_probe,
    run_reachability_study,
    write_reachability_report,
)

PAID_CALLS_ENV = "POLICYSTRATA_ALLOW_PAID_CALLS"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--domain", default="support_saas", help="built-in domain (default: support_saas)")
    parser.add_argument(
        "--client",
        choices=("stub", "anthropic"),
        default="stub",
        help="stub is free and deterministic; anthropic sends paid API requests",
    )
    parser.add_argument("--out", type=Path, required=True, help="output directory for the JSON report")
    parser.add_argument(
        "--paraphrases",
        type=int,
        default=DEFAULT_PARAPHRASE_COUNT,
        help=f"paraphrases per case (default: {DEFAULT_PARAPHRASE_COUNT})",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_REACHABILITY_SEED)
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="model calls allowed per paraphrase, including JSON-repair retries (default: 3)",
    )
    parser.add_argument(
        "--paraphrase-dir",
        type=Path,
        default=None,
        help="directory of hand-written <mutation_id>.txt paraphrase files",
    )
    parser.add_argument(
        "--mutations",
        nargs="*",
        default=None,
        help="restrict the study to these mutation ids (default: all domain operators)",
    )
    parser.add_argument(
        "--skip-skew-probe",
        action="store_true",
        help="skip the manifest-skew behavioral probe",
    )
    return parser


def select_client(args: argparse.Namespace, parser: argparse.ArgumentParser) -> ModelClient:
    if args.client == "stub":
        return DeterministicStubClient()
    if os.environ.get(PAID_CALLS_ENV) != "1":
        parser.error(
            "--client anthropic sends paid API requests (up to cases x paraphrases x "
            f"max-attempts calls) and this incurs cost. Set {PAID_CALLS_ENV}=1 to confirm, "
            "export ANTHROPIC_API_KEY, and install the SDK with `pip install anthropic`."
        )
    return AnthropicClient()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    client = select_client(args, parser)
    budget = ReachabilityBudget(max_attempts=args.max_attempts)
    cases = build_cases(
        args.domain,
        paraphrase_count=args.paraphrases,
        seed=args.seed,
        paraphrase_dir=args.paraphrase_dir,
        mutations=args.mutations,
    )
    report = run_reachability_study(client, cases, budget)
    if not args.skip_skew_probe:
        probe = run_manifest_skew_probe(client, domain=args.domain, budget=budget)
        report = report.model_copy(update={"skew_probe": probe})

    report_path = write_reachability_report(report, args.out)
    print(f"client: {report.client}")
    print(f"cases reached: {report.reached_cases}/{report.total_cases}")
    for result in report.results:
        status = "reached" if result.reached else "not-reached"
        print(
            f"  {status:11s} {result.mutation} "
            f"({result.reached_count}/{result.paraphrase_count} paraphrases, "
            f"{result.total_attempts} attempts)"
        )
    if report.skew_probe is not None:
        print(f"manifest-skew probe: plans_differ={report.skew_probe.plans_differ}")
    print(f"report: {report_path}")
    if args.client == "stub":
        print("note: stub results verify the harness only; they are not reachability evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from policystrata.artifact_report import artifact_report_json, render_artifact_report
from policystrata.baselines import evaluate_baseline_run
from policystrata.demo import run_demo
from policystrata.domain import BUILTIN_DOMAIN, BUILTIN_DOMAINS, copy_domain
from policystrata.evidence import parse_run_args, render_evidence_tables
from policystrata.exports import export_run
from policystrata.generator import MAX_GENERATED_COUNT
from policystrata.init_scan import init_scan_project
from policystrata.integrations.dbt_semantic import compare_dbt_semantic_model
from policystrata.minimize import minimize_witness_file
from policystrata.runner import run_suite
from policystrata.scan_models import GateOutcome
from policystrata.scanner import run_scan
from policystrata.summary import summarize_run


def generated_count_arg(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("count must be an integer") from exc
    if count < 1 or count > MAX_GENERATED_COUNT:
        raise argparse.ArgumentTypeError(f"count must be between 1 and {MAX_GENERATED_COUNT}")
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="policystrata",
        description="Cross-layer policy regression testing.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-domain",
        help="Copy a built-in domain fixture into the current tree.",
    )
    init_parser.add_argument("domain", choices=BUILTIN_DOMAINS)
    init_parser.add_argument("--out", type=Path, default=Path("."))

    init_scan_parser = subparsers.add_parser(
        "init-scan",
        help="Create a runnable scanner scaffold with config, domain policy, surfaces, and example traces.",
    )
    init_scan_parser.add_argument("--out", type=Path, default=Path("."))
    init_scan_parser.add_argument("--source-domain", choices=BUILTIN_DOMAINS, default=BUILTIN_DOMAIN)
    init_scan_parser.add_argument("--force", action="store_true")

    demo_parser = subparsers.add_parser("demo", help="Run a 30-second built-in policy drift demo.")
    demo_parser.add_argument("--out", type=Path, default=Path("runs/demo"))

    run_parser = subparsers.add_parser("run", help="Run a deterministic benchmark suite.")
    run_parser.add_argument("--domain", default=BUILTIN_DOMAIN)
    run_parser.add_argument("--suite", default="seeded")
    run_parser.add_argument("--out", type=Path, required=True)
    run_parser.add_argument("--domain-path", type=Path, default=None)
    run_parser.add_argument(
        "--count",
        type=generated_count_arg,
        default=None,
        help="Task count for generated suites.",
    )
    run_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for generated suites.",
    )

    minimize_parser = subparsers.add_parser("minimize", help="Minimize a trace or witness JSON file.")
    minimize_parser.add_argument("--witness", type=Path, required=True)

    summarize_parser = subparsers.add_parser("summarize", help="Summarize a run directory.")
    summarize_parser.add_argument("run_dir", type=Path)

    baselines_parser = subparsers.add_parser("baselines", help="Evaluate baseline strategies for a run.")
    baselines_parser.add_argument("run_dir", type=Path)

    export_parser = subparsers.add_parser("export", help="Export a run through an external eval adapter.")
    export_parser.add_argument("run_dir", type=Path)
    export_parser.add_argument("--format", choices=["inspect", "benchflow"], required=True)
    export_parser.add_argument("--out", type=Path, required=True)

    evidence_parser = subparsers.add_parser("evidence", help="Render Markdown evidence tables.")
    evidence_parser.add_argument("runs", nargs="+", help="Run directories, optionally named as suite=path.")
    evidence_parser.add_argument("--out", type=Path, default=None)

    artifact_parser = subparsers.add_parser(
        "artifact-report",
        help="Render reviewer-facing reproducibility and usability metrics for a run.",
    )
    artifact_parser.add_argument("run_dir", type=Path)
    artifact_parser.add_argument("--domain-path", type=Path, default=None)
    artifact_parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    artifact_parser.add_argument("--out", type=Path, default=None)

    integration_parser = subparsers.add_parser(
        "check-integration",
        help="Check a small external semantic-layer fixture against a PolicyStrata domain.",
    )
    integration_parser.add_argument("kind", choices=["dbt-semantic"])
    integration_parser.add_argument("--domain", default=BUILTIN_DOMAIN, choices=BUILTIN_DOMAINS)
    integration_parser.add_argument("--path", type=Path, required=True)
    integration_parser.add_argument("--domain-path", type=Path, default=None)

    scan_parser = subparsers.add_parser(
        "scan",
        help="Run a production policy-drift scan over configured adapters and traces.",
    )
    scan_parser.add_argument("--config", type=Path, default=Path("policystrata.yaml"))
    scan_parser.add_argument("--out", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return run_command(args)
    except ValidationError as exc:
        parser.error(format_validation_error(exc))
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    except TypeError as exc:
        if not is_user_type_error(exc):
            raise
        parser.error(str(exc))
    return 2


def run_command(args: argparse.Namespace) -> int:
    if args.command == "init-domain":
        target = copy_domain(args.domain, args.out)
        print(target)
        return 0

    if args.command == "init-scan":
        print(
            json.dumps(
                init_scan_project(args.out, args.source_domain, args.force),
                sort_keys=True,
            )
        )
        return 0

    if args.command == "demo":
        print(run_demo(args.out), end="")
        return 0

    if args.command == "run":
        traces = run_suite(args.domain, args.suite, args.out, args.domain_path, args.count, args.seed)
        print(json.dumps({"traces": len(traces), "out": str(args.out)}, sort_keys=True))
        return 0

    if args.command == "minimize":
        print(json.dumps(minimize_witness_file(args.witness), indent=2, sort_keys=True))
        return 0

    if args.command == "summarize":
        print(summarize_run(args.run_dir).model_dump_json(indent=2))
        return 0

    if args.command == "baselines":
        print(json.dumps(evaluate_baseline_run(args.run_dir), indent=2, sort_keys=True))
        return 0

    if args.command == "export":
        print(json.dumps(export_run(args.run_dir, args.format, args.out), sort_keys=True))
        return 0

    if args.command == "evidence":
        markdown = render_evidence_tables(parse_run_args(args.runs))
        if args.out is not None:
            args.out.write_text(markdown, encoding="utf-8")
            print(json.dumps({"out": str(args.out)}, sort_keys=True))
        else:
            print(markdown, end="")
        return 0

    if args.command == "artifact-report":
        output = (
            artifact_report_json(args.run_dir, args.domain_path)
            if args.format == "json"
            else render_artifact_report(args.run_dir, args.domain_path)
        )
        if args.out is not None:
            args.out.write_text(output, encoding="utf-8")
            print(json.dumps({"out": str(args.out)}, sort_keys=True))
        else:
            print(output, end="")
        return 0

    if args.command == "check-integration" and args.kind == "dbt-semantic":
        print(
            json.dumps(
                compare_dbt_semantic_model(args.domain, args.path, args.domain_path),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "scan":
        result = run_scan(args.config, args.out)
        print(
            json.dumps(
                {
                    "gate": result.gate.outcome.value,
                    "findings": result.summary.total_findings,
                    "out": result.output_dir,
                },
                sort_keys=True,
            )
        )
        return 1 if result.gate.outcome == GateOutcome.FAIL else 0

    raise ValueError(f"unknown command: {args.command}")


def format_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return str(exc)
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "input"
    return f"{loc}: {first.get('msg', 'validation failed')}"


def is_user_type_error(exc: TypeError) -> bool:
    message = str(exc)
    return message.startswith(
        (
            "generated count must",
            "matrix count must",
            "suite name must",
        )
    )

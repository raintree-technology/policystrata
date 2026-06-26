from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from policystrata.artifact_report import artifact_report_json, render_artifact_report
from policystrata.baselines import evaluate_ablation_runs, evaluate_baseline_runs
from policystrata.demo import run_demo
from policystrata.doctor import environment_doctor, render_doctor_report, run_config_doctor
from policystrata.domain import BUILTIN_DOMAIN, BUILTIN_DOMAINS, copy_domain
from policystrata.evidence import parse_run_args, render_evidence_tables
from policystrata.exports import export_run
from policystrata.freeze import verify_benchmark_manifest, write_benchmark_manifest
from policystrata.generator import MAX_GENERATED_COUNT
from policystrata.init_scan import SCANNER_EXAMPLES, init_scan_project
from policystrata.integrations.dbt_semantic import compare_dbt_semantic_model, dbt_semantic_has_warnings
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
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        description=(
            "Create a runnable scanner scaffold.\n\n"
            "Examples:\n"
            "  policystrata init-scan --out policystrata\n"
            "  policystrata init-scan postgres_dbt --out policystrata-example"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_scan_parser.add_argument(
        "example",
        nargs="?",
        choices=SCANNER_EXAMPLES,
        default="basic",
        help="Scanner example to copy. Defaults to basic.",
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
    run_parser.add_argument(
        "--freeze-manifest",
        type=Path,
        default=None,
        help="Benchmark manifest created by freeze-benchmark; verified before running.",
    )

    freeze_parser = subparsers.add_parser(
        "freeze-benchmark",
        help="Create a detector/suite/policy freeze manifest for a deterministic benchmark run.",
    )
    freeze_parser.add_argument("--domain", default=BUILTIN_DOMAIN, choices=BUILTIN_DOMAINS)
    freeze_parser.add_argument("--suite", default="generated")
    freeze_parser.add_argument("--domain-path", type=Path, default=None)
    freeze_parser.add_argument("--count", type=generated_count_arg, default=None)
    freeze_parser.add_argument("--seed", type=int, default=None)
    freeze_parser.add_argument("--out", type=Path, required=True)

    verify_parser = subparsers.add_parser(
        "verify-freeze",
        help="Verify that current detector, policy, surfaces, and suite match a freeze manifest.",
    )
    verify_parser.add_argument("manifest", type=Path)
    verify_parser.add_argument("--domain", default=None, choices=BUILTIN_DOMAINS)
    verify_parser.add_argument("--suite", default=None)
    verify_parser.add_argument("--domain-path", type=Path, default=None)
    verify_parser.add_argument("--count", type=generated_count_arg, default=None)
    verify_parser.add_argument("--seed", type=int, default=None)

    minimize_parser = subparsers.add_parser("minimize", help="Minimize a trace or witness JSON file.")
    minimize_parser.add_argument("--witness", type=Path, required=True)

    summarize_parser = subparsers.add_parser("summarize", help="Summarize a run directory.")
    summarize_parser.add_argument("run_dir", type=Path)

    baselines_parser = subparsers.add_parser("baselines", help="Evaluate baseline strategies for a run.")
    baselines_parser.add_argument("run_dirs", type=Path, nargs="+")
    baselines_parser.add_argument("--format", choices=["json"], default="json")
    baselines_parser.add_argument("--out", type=Path, default=None)

    ablations_parser = subparsers.add_parser("ablations", help="Evaluate PolicyStrata ablations for a run.")
    ablations_parser.add_argument("run_dirs", type=Path, nargs="+")
    ablations_parser.add_argument("--format", choices=["json"], default="json")
    ablations_parser.add_argument("--out", type=Path, default=None)

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
    integration_parser.add_argument(
        "--strict",
        "--fail-on-warning",
        action="store_true",
        dest="fail_on_warning",
        help="Exit 1 when the integration check reports warning-level diagnostics.",
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Run a production policy-drift scan over configured adapters and traces.",
        description=(
            "Run a production policy-drift scan over configured adapters and traces.\n\n"
            "Examples:\n"
            "  policystrata scan --config policystrata/policystrata.yaml --out runs/policystrata-smoke\n"
            "  policystrata init-scan postgres_dbt --out policystrata-example\n"
            "  policystrata scan --config policystrata-example/policystrata_clean.yaml \\\n"
            "    --out runs/scan-clean\n\n"
            "Accepted config sections:\n"
            "  version, domain, domain_path, output, sarif, dbt, sql_traces,\n"
            "  policy_docs, prompt_manifests, source_maps, tenancy, database, fuzz, gate"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scan_parser.add_argument(
        "--config",
        type=Path,
        default=Path("policystrata.yaml"),
        help="Scan config YAML.",
    )
    scan_parser.add_argument("--out", type=Path, default=None, help="Output directory for scan artifacts.")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check local dependencies or audit a scanner configuration.",
        description=(
            "Check local dependencies or audit scanner wiring.\n\n"
            "Examples:\n"
            "  policystrata doctor\n"
            "  policystrata doctor --config policystrata/policystrata.yaml\n"
            "  policystrata doctor --config policystrata/policystrata.yaml --format markdown"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor_parser.add_argument("--config", type=Path, default=None, help="Scan config YAML to audit.")
    doctor_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    doctor_parser.add_argument("--out", type=Path, default=None, help="Optional output file.")
    doctor_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 when configured stack audit contains missing, partial, or invalid wiring.",
    )

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
                init_scan_project(args.out, args.example, args.source_domain, args.force),
                sort_keys=True,
            )
        )
        return 0

    if args.command == "demo":
        print(run_demo(args.out), end="")
        return 0

    if args.command == "run":
        traces = run_suite(
            args.domain,
            args.suite,
            args.out,
            args.domain_path,
            args.count,
            args.seed,
            args.freeze_manifest,
        )
        print(json.dumps({"traces": len(traces), "out": str(args.out)}, sort_keys=True))
        return 0

    if args.command == "freeze-benchmark":
        manifest = write_benchmark_manifest(
            args.domain,
            args.suite,
            args.out,
            args.domain_path,
            args.count,
            args.seed,
        )
        print(
            json.dumps(
                {
                    "benchmark_manifest_id": manifest["benchmark_manifest_id"],
                    "out": str(args.out),
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "verify-freeze":
        verification = verify_benchmark_manifest(
            args.manifest,
            args.domain,
            args.suite,
            args.domain_path,
            args.count,
            args.seed,
        )
        print(json.dumps(strip_manifest_payloads(verification), indent=2, sort_keys=True))
        return 0 if verification["verified"] else 1

    if args.command == "minimize":
        print(json.dumps(minimize_witness_file(args.witness), indent=2, sort_keys=True))
        return 0

    if args.command == "summarize":
        print(summarize_run(args.run_dir).model_dump_json(indent=2))
        return 0

    if args.command == "baselines":
        return write_json_result(evaluate_baseline_runs(args.run_dirs), args.out)

    if args.command == "ablations":
        return write_json_result(evaluate_ablation_runs(args.run_dirs), args.out)
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
        integration_result = compare_dbt_semantic_model(args.domain, args.path, args.domain_path)
        print(
            json.dumps(
                integration_result,
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if args.fail_on_warning and dbt_semantic_has_warnings(integration_result) else 0

    if args.command == "scan":
        scan_result = run_scan(args.config, args.out)
        print(
            json.dumps(
                {
                    "gate": scan_result.gate.outcome.value,
                    "findings": scan_result.summary.total_findings,
                    "out": scan_result.output_dir,
                },
                sort_keys=True,
            )
        )
        return 1 if scan_result.gate.outcome == GateOutcome.FAIL else 0

    if args.command == "doctor":
        if args.config is None:
            output = json.dumps(run_doctor(), indent=2, sort_keys=True) + "\n"
            exit_code = 0
        else:
            doctor = run_config_doctor(args.config)
            output = (
                render_doctor_report(doctor)
                if args.format == "markdown"
                else json.dumps(doctor, indent=2, sort_keys=True) + "\n"
            )
            exit_code = 1 if args.strict and doctor_has_missing_wiring(doctor) else 0
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(output, encoding="utf-8")
            print(json.dumps({"out": str(args.out)}, sort_keys=True))
        else:
            print(output, end="")
        return exit_code

    raise ValueError(f"unknown command: {args.command}")


def write_json_result(result: object, out_path: Path | None) -> int:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(json.dumps({"out": str(out_path)}, sort_keys=True))
    else:
        print(payload, end="")
    return 0


def strip_manifest_payloads(verification: dict[str, object]) -> dict[str, object]:
    manifest = verification.get("manifest")
    manifest_id = manifest.get("benchmark_manifest_id") if isinstance(manifest, dict) else None
    return {
        "verified": verification["verified"],
        "benchmark_manifest_id": manifest_id,
        "mismatches": verification["mismatches"],
    }


def run_doctor() -> dict[str, object]:
    return environment_doctor()


def doctor_has_missing_wiring(doctor: dict[str, object]) -> bool:
    stack = doctor.get("stack", [])
    if not isinstance(stack, list):
        return False
    return any(
        isinstance(item, dict) and item.get("status") in {"missing", "partial", "invalid"}
        for item in stack
    )


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

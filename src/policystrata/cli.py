from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from policystrata.artifact_report import artifact_report_json, render_artifact_report
from policystrata.baselines import evaluate_ablation_runs, evaluate_baseline_runs
from policystrata.clearance import (
    ClearanceRunnerConfig,
    ClearanceRunnerExitCode,
    build_clearance_evidence_pack,
    build_clearance_upload_payload,
    clearance_exit_code_for_pack,
    load_clearance_runner_config,
    protected_branch_upload_blocker,
    scan_metadata_boundary,
    upload_clearance_payload,
    write_clearance_contract_outputs,
)
from policystrata.demo import run_demo
from policystrata.doctor import (
    environment_doctor,
    render_doctor_report,
    render_environment_doctor_report,
    run_config_doctor,
)
from policystrata.domain import BUILTIN_DOMAIN, BUILTIN_DOMAINS, copy_domain
from policystrata.evidence import parse_run_args, render_evidence_tables
from policystrata.exports import export_run
from policystrata.freeze import verify_benchmark_manifest, write_benchmark_manifest
from policystrata.generator import MAX_GENERATED_COUNT
from policystrata.init_scan import SCANNER_EXAMPLES, init_scan_project
from policystrata.integrations.dbt_semantic import compare_dbt_semantic_model, dbt_semantic_has_warnings
from policystrata.integrations.native import (
    NATIVE_INTEGRATION_PROVIDERS,
    NativeIntegrationConnection,
    native_evidence_runtime_payload,
)
from policystrata.minimize import minimize_witness_file
from policystrata.runner import run_suite
from policystrata.runtime import (
    RuntimeEventEvaluation,
    evaluate_runtime_events,
    expected_runtime_decision_mismatches,
)
from policystrata.scan_models import GateOutcome
from policystrata.scanner import render_junit, run_scan
from policystrata.schemas import SCHEMA_KINDS, public_schema
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
    run_parser.add_argument(
        "--clearance-config",
        type=Path,
        default=None,
        help="Optional clearance.runner.yaml metadata for local Clearance artifacts.",
    )
    run_parser.add_argument("--release-candidate", default=None)
    run_parser.add_argument("--commit-sha", default=None)
    run_parser.add_argument("--environment", default=None)
    run_parser.add_argument("--project-id", default=None)
    run_parser.add_argument("--organization-id", default=None)
    run_parser.add_argument(
        "--clearance-output-dir",
        default=None,
        help="Relative output directory for Clearance artifacts. Defaults to .clearance.",
    )
    run_parser.add_argument(
        "--offline",
        action="store_true",
        help="Mark Clearance artifacts as intentionally local/offline.",
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

    export_parser = subparsers.add_parser("export", help="Export a run through an evidence or eval adapter.")
    export_parser.add_argument("run_dir", type=Path)
    export_parser.add_argument(
        "--format",
        choices=["inspect", "benchflow", "policystrata-json"],
        required=True,
    )
    export_parser.add_argument("--out", type=Path, required=True)

    evidence_parser = subparsers.add_parser("evidence", help="Render Markdown evidence tables.")
    evidence_parser.add_argument("runs", nargs="+", help="Run directories, optionally named as suite=path.")
    evidence_parser.add_argument("--out", type=Path, default=None)

    schema_parser = subparsers.add_parser(
        "schema",
        help="Render JSON Schema for a public PolicyStrata contract.",
    )
    schema_parser.add_argument(
        "--kind",
        choices=SCHEMA_KINDS,
        required=True,
        help="Contract schema to render.",
    )
    schema_parser.add_argument("--out", type=Path, default=None, help="Optional output file.")

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

    native_integration_parser = subparsers.add_parser(
        "integrations",
        help="Collect native provider evidence as Clearance runtime events.",
        description=(
            "Collect normalized provider evidence without storing raw provider payloads.\n\n"
            "Examples:\n"
            "  policystrata integrations collect --provider github --project governed-agent "
            "--connection-id conn_123\n"
            "  policystrata integrations collect --provider aws --project governed-agent "
            "--connection-id conn_aws --config aws.json --secret-key externalId"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    native_integration_parser.add_argument("action", choices=["collect"])
    native_integration_parser.add_argument("--provider", choices=NATIVE_INTEGRATION_PROVIDERS, required=True)
    native_integration_parser.add_argument("--project", required=True)
    native_integration_parser.add_argument("--connection-id", required=True)
    native_integration_parser.add_argument("--display-name", default=None)
    native_integration_parser.add_argument("--config", type=Path, default=None)
    native_integration_parser.add_argument("--secret-key", action="append", default=[])
    native_integration_parser.add_argument("--out", type=Path, default=None)

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
            "  policy_docs, prompt_manifests, source_maps, runtime_manifests,\n"
            "  runtime_events, tenancy, database, fuzz, gate"
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
    scan_parser.add_argument("--junit", type=Path, default=None, help="Optional JUnit XML output path.")

    runtime_parser = subparsers.add_parser(
        "runtime-evaluate",
        help="Evaluate redacted runtime gateway events against a PolicyStrata runtime manifest.",
        description=(
            "Evaluate one runtime event or an {events:[...]} batch.\n\n"
            "Examples:\n"
            "  policystrata runtime-evaluate --manifest runtime-manifest.json --event runtime-event.json\n"
            "  policystrata runtime-evaluate --manifest runtime-manifest.yaml --event events.json "
            "--out decisions.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    runtime_parser.add_argument("--manifest", type=Path, required=True)
    runtime_parser.add_argument("--event", type=Path, required=True)
    runtime_parser.add_argument("--out", type=Path, default=None)
    runtime_parser.add_argument(
        "--assert-expected",
        action="store_true",
        help=(
            "Assert each fixture expectedDecision against the evaluated decision. "
            "When set, exit status reflects assertion mismatches instead of blocked events."
        ),
    )

    clearance_parser = subparsers.add_parser(
        "clearance-runner",
        help="Validate Clearance runner contracts and metadata-only evidence packs.",
        description=(
            "Validate local Clearance runner config and evidence without uploading raw customer data.\n\n"
            "Examples:\n"
            "  policystrata clearance-runner validate --config clearance.runner.yaml\n"
            "  policystrata clearance-runner evidence-pack --run-dir runs/demo --out evidence-pack.json\n"
            "  policystrata clearance-runner upload --run-dir runs/demo --config clearance.runner.yaml\n"
            "  policystrata clearance-runner audit-payload --payload runtime-events.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    clearance_parser.add_argument("action", choices=["validate", "evidence-pack", "audit-payload", "upload"])
    clearance_parser.add_argument("--config", type=Path, default=None)
    clearance_parser.add_argument("--run-dir", type=Path, default=None)
    clearance_parser.add_argument("--payload", type=Path, default=None)
    clearance_parser.add_argument("--api-url", default=None)
    clearance_parser.add_argument("--token", default=None)
    clearance_parser.add_argument("--upload-path", default="/v1/runner/uploads")
    clearance_parser.add_argument("--idempotency-key", default=None)
    clearance_parser.add_argument("--local-override-note", default=None)
    clearance_parser.add_argument("--max-bytes", type=int, default=1_000_000)
    clearance_parser.add_argument("--out", type=Path, default=None)

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
        clearance_config = clearance_config_from_args(args)
        traces = run_suite(
            args.domain,
            args.suite,
            args.out,
            args.domain_path,
            args.count,
            args.seed,
            args.freeze_manifest,
            clearance_config=clearance_config,
            release_candidate=args.release_candidate,
            commit_sha=args.commit_sha,
            environment=args.environment,
            project_id=args.project_id,
            organization_id=args.organization_id,
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

    if args.command == "schema":
        return write_schema(args.kind, args.out)

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

    if args.command == "integrations" and args.action == "collect":
        config = read_json_or_yaml(args.config) if args.config is not None else {}
        if not isinstance(config, dict):
            raise ValueError("integration config must be a JSON/YAML object")
        payload = native_evidence_runtime_payload(
            NativeIntegrationConnection(
                provider=args.provider,
                project=args.project,
                connection_id=args.connection_id,
                display_name=args.display_name,
                config=config,
                secret_keys=tuple(args.secret_key),
            )
        )
        output = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        return write_text_result(output, args.out)

    if args.command == "scan":
        scan_result = run_scan(args.config, args.out)
        if args.junit is not None:
            args.junit.parent.mkdir(parents=True, exist_ok=True)
            args.junit.write_text(render_junit(scan_result), encoding="utf-8")
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

    if args.command == "runtime-evaluate":
        runtime_manifest = read_json_or_yaml(args.manifest)
        event_payload = read_json_or_yaml(args.event)
        if not isinstance(runtime_manifest, dict):
            raise ValueError("runtime manifest must be an object")
        events = runtime_event_list(event_payload)
        evaluations = evaluate_runtime_events(runtime_manifest, events)
        expected_mismatches = runtime_expected_mismatches(
            events,
            evaluations,
            require_expected=args.assert_expected,
        )
        runtime_output = {
            "ok": all(evaluation.allowed for evaluation in evaluations),
            "expectedMatched": not expected_mismatches,
            "expectedMismatches": expected_mismatches,
            "events": [
                evaluation.to_event(event)
                for evaluation, event in zip(evaluations, events, strict=True)
            ],
            "decisions": [evaluation.to_dict() for evaluation in evaluations],
        }
        runtime_payload = json.dumps(runtime_output, indent=2, sort_keys=True) + "\n"
        exit_code = 0 if not expected_mismatches else 1
        if not args.assert_expected:
            exit_code = 0 if runtime_output["ok"] else 1
        if args.out is not None:
            output_path = runtime_output_path(args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(runtime_payload, encoding="utf-8")
            print(json.dumps({"out": str(output_path)}, sort_keys=True))
        else:
            print(runtime_payload, end="")
        return exit_code

    if args.command == "clearance-runner":
        if args.action == "validate":
            if args.config is None:
                raise ValueError("--config is required for clearance-runner validate")
            try:
                config = load_clearance_runner_config(args.config)
            except (ValidationError, ValueError) as exc:
                return write_invalid_config_result(exc, args.out)
            output = json.dumps(
                {
                    "ok": True,
                    "schemaVersion": config.schema_version,
                    "projectId": config.project_id,
                    "uploadMode": config.upload_mode,
                    "uploadArtifacts": config.upload_artifacts,
                    "failMode": config.fail_mode,
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
            return write_text_result(output, args.out)
        if args.action == "evidence-pack":
            if args.run_dir is None:
                raise ValueError("--run-dir is required for clearance-runner evidence-pack")
            try:
                config = load_clearance_runner_config(args.config) if args.config is not None else None
            except (ValidationError, ValueError) as exc:
                return write_invalid_config_result(exc, args.out)
            artifacts = write_clearance_contract_outputs(args.run_dir, config)
            pack = build_clearance_evidence_pack(args.run_dir, config)
            output = json.dumps({**pack, "localArtifacts": artifacts}, indent=2, sort_keys=True) + "\n"
            exit_code = int(clearance_exit_code_for_pack(pack))
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(output, encoding="utf-8")
                print(
                    json.dumps(
                        {
                            "out": str(args.out),
                            "exitCode": exit_code,
                            "state": pack["decision"]["state"],
                            "blocked": pack["decision"]["blocked"],
                            "needsReview": pack["decision"]["needsReview"],
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(output, end="")
            return exit_code
        if args.action == "audit-payload":
            if args.payload is None:
                raise ValueError("--payload is required for clearance-runner audit-payload")
            audited_payload = read_json_or_yaml(args.payload)
            findings = [finding.model_dump() for finding in scan_metadata_boundary(audited_payload)]
            output = json.dumps(
                {
                    "ok": not findings,
                    "findings": findings,
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
            if findings:
                return _write_failing_text_result(output, args.out)
            return write_text_result(output, args.out)
        if args.action == "upload":
            if args.run_dir is None:
                raise ValueError("--run-dir is required for clearance-runner upload")
            if args.config is None:
                raise ValueError("--config is required for clearance-runner upload")
            try:
                config = load_clearance_runner_config(args.config)
            except (ValidationError, ValueError) as exc:
                return write_invalid_config_result(exc, args.out)
            if args.local_override_note:
                config = config.model_copy(update={"local_override_note": args.local_override_note})
            blocker = protected_branch_upload_blocker(config)
            if blocker is not None:
                return write_upload_auth_failure(
                    {
                        "ok": False,
                        "status": 0,
                        "error": "protected_branch_local_only_blocked",
                        "message": blocker,
                    },
                    args.out,
                )
            api_url = args.api_url or config.api_url
            if not api_url:
                raise ValueError("--api-url or apiUrl in clearance.runner.yaml is required for upload")
            runtime_events = read_json_or_yaml(args.payload) if args.payload is not None else None
            upload_payload = build_clearance_upload_payload(
                args.run_dir,
                config,
                runtime_events=runtime_events,
                idempotency_key=args.idempotency_key,
            )
            if config.upload_mode == "local_only":
                local_output: dict[str, object] = {
                    "ok": True,
                    "status": 0,
                    "uploadMode": "local_only",
                    "uploadId": upload_payload["uploadId"],
                    "runId": upload_payload["runId"],
                    "localOverrideNote": config.local_override_note,
                }
                return write_json_result(local_output, args.out)
            token = args.token or os.environ.get("CLEARANCE_RUNNER_TOKEN")
            if not token:
                return write_upload_auth_failure(
                    {
                        "ok": False,
                        "status": 0,
                        "uploadId": upload_payload["uploadId"],
                        "runId": upload_payload["runId"],
                        "error": "missing_runner_token",
                    },
                    args.out,
                )
            result = upload_clearance_payload(
                upload_payload,
                api_url=api_url,
                token=token,
                organization_id=config.organization_id,
                path=args.upload_path,
                max_bytes=args.max_bytes,
            )
            output = json.dumps(
                {
                    "ok": result.ok,
                    "status": result.status,
                    "uploadId": upload_payload["uploadId"],
                    "runId": upload_payload["runId"],
                    "body": result.body,
                    "error": result.error,
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
            if args.out is not None:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(output, encoding="utf-8")
                print(json.dumps({"out": str(args.out), "exitCode": 0 if result.ok else 4}, sort_keys=True))
            else:
                print(output, end="")
            return 0 if result.ok else 4

    if args.command == "doctor":
        if args.config is None:
            doctor = run_doctor()
            output = (
                render_environment_doctor_report(doctor)
                if args.format == "markdown"
                else json.dumps(doctor, indent=2, sort_keys=True) + "\n"
            )
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
    return write_text_result(payload, out_path)


def write_upload_auth_failure(result: object, out_path: Path | None) -> int:
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(json.dumps({"out": str(out_path), "exitCode": 4}, sort_keys=True))
    else:
        print(payload, end="")
    return int(ClearanceRunnerExitCode.UPLOAD_AUTH_FAILURE)


def write_invalid_config_result(exc: Exception, out_path: Path | None) -> int:
    message = format_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
    payload = json.dumps(
        {
            "ok": False,
            "error": "invalid_config",
            "message": message,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(
            json.dumps(
                {"out": str(out_path), "exitCode": int(ClearanceRunnerExitCode.INVALID_CONFIG)},
                sort_keys=True,
            )
        )
    else:
        print(payload, end="")
    return int(ClearanceRunnerExitCode.INVALID_CONFIG)


def clearance_config_from_args(args: argparse.Namespace) -> ClearanceRunnerConfig | None:
    config = (
        load_clearance_runner_config(args.clearance_config)
        if args.clearance_config is not None
        else None
    )
    updates = {
        "organizationId": args.organization_id,
        "projectId": args.project_id,
        "environment": args.environment,
        "releaseCandidate": args.release_candidate,
        "outputDir": args.clearance_output_dir,
        "offline": True if args.offline else None,
    }
    updates = {key: value for key, value in updates.items() if value is not None}
    if not updates:
        return config
    data = config.model_dump(by_alias=True) if config is not None else {}
    data.update(updates)
    if "projectId" not in data:
        data["projectId"] = args.domain
    return ClearanceRunnerConfig.model_validate(data)


def read_json_or_yaml(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def runtime_event_list(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        items = payload["events"]
    else:
        items = [payload]
    events = [item for item in items if isinstance(item, dict)]
    if len(events) != len(items):
        raise ValueError("runtime event payload must be an event object or {events:[...]}")
    return events


def runtime_output_path(out_path: Path) -> Path:
    if out_path.exists() and out_path.is_dir():
        return out_path / "runtime-events.json"
    if out_path.suffix:
        return out_path
    return out_path / "runtime-events.json"


def runtime_expected_mismatches(
    events: list[dict[str, object]],
    evaluations: list[RuntimeEventEvaluation],
    *,
    require_expected: bool,
) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    for event, evaluation in zip(events, evaluations, strict=True):
        expected = event.get("expectedDecision") or event.get("expected_decision")
        reasons: list[str] = []
        if require_expected and not isinstance(expected, dict):
            reasons.append("missing expectedDecision")
        reasons.extend(expected_runtime_decision_mismatches(event, evaluation))
        if reasons:
            mismatches.append(
                {
                    "eventId": event.get("eventId") or event.get("event_id"),
                    "mismatches": reasons,
                }
            )
    return mismatches


def write_schema(kind: str, out_path: Path | None) -> int:
    payload = json.dumps(public_schema(kind), indent=2, sort_keys=True) + "\n"
    return write_text_result(payload, out_path)


def write_text_result(payload: str, out_path: Path | None) -> int:
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(json.dumps({"out": str(out_path)}, sort_keys=True))
    else:
        print(payload, end="")
    return 0


def _write_failing_text_result(payload: str, out_path: Path | None) -> int:
    write_text_result(payload, out_path)
    return 1


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

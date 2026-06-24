from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from policystrata.baselines import evaluate_baselines
from policystrata.minimize import minimize_trace
from policystrata.models import Trace, WitnessClass
from policystrata.summary import load_traces


def render_evidence_tables(runs: dict[str, Path]) -> str:
    suite_rows = [suite_row(name, path) for name, path in runs.items()]
    traces = [trace for path in runs.values() for trace in load_traces(path)]
    baseline_rows = baseline_table_rows(traces)

    sections = [
        "## Suite Results",
        markdown_table(
            ["Suite", "Mutants", "Killed", "Survived", "Equivalent declared", "Median witness bytes"],
            suite_rows,
        ),
        "## Baselines",
        markdown_table(["Baseline", "Failures caught", "Catch rate"], baseline_rows),
    ]
    return "\n\n".join(sections) + "\n"


def suite_row(name: str, run_dir: Path) -> list[str]:
    traces = load_traces(run_dir)
    killed = sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN)
    survived = len(traces) - killed
    equivalent_declared = sum(
        1 for trace in traces if trace.expected_witness_class == WitnessClass.CLEAN
    )
    return [
        name,
        str(len(traces)),
        str(killed),
        str(survived),
        str(equivalent_declared),
        str(median_witness_bytes(run_dir, traces)),
    ]


def baseline_table_rows(traces: list[Trace]) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, result in evaluate_baselines(traces).items():
        rows.append(
            [
                name,
                f"{result['caught']}/{result['total_failures']}",
                f"{float(result['catch_rate']):.2f}",
            ]
        )
    return rows


def median_witness_bytes(run_dir: Path, traces: list[Trace]) -> int:
    sizes: list[int] = []
    for trace in traces:
        if trace.witness_path:
            witness_path = run_artifact_path(run_dir, trace.witness_path)
            sizes.append(len(witness_path.read_bytes()))
        elif trace.witness_class != WitnessClass.CLEAN:
            sizes.append(len(json.dumps(minimize_trace(trace), sort_keys=True).encode("utf-8")))
    if not sizes:
        return 0
    return int(median(sizes))


def run_artifact_path(run_dir: Path, relative_path: str) -> Path:
    raw_path = Path(relative_path)
    if raw_path.is_absolute():
        raise ValueError(f"run artifact path must be relative: {relative_path}")
    root = run_dir.resolve()
    candidate = (run_dir / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"run artifact path escapes run directory: {relative_path}") from exc
    return candidate


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def parse_run_args(values: list[str]) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for value in values:
        if "=" in value:
            name, raw_path = value.split("=", 1)
            runs[name] = Path(raw_path)
        else:
            path = Path(value)
            runs[path.name] = path
    return runs

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from policystrata.baselines import evaluate_baselines
from policystrata.minimize import minimize_trace
from policystrata.models import Trace, WitnessClass
from policystrata.summary import accounting_status, load_traces


def render_evidence_tables(runs: dict[str, Path]) -> str:
    suite_rows = [suite_row(name, path) for name, path in runs.items()]
    traces = [trace for path in runs.values() for trace in load_traces(path)]
    baseline_rows = baseline_table_rows(traces)
    provenance_rows = provenance_table_rows(runs)

    sections = [
        "## Suite Results",
        markdown_table(
            [
                "Suite",
                "Mutants",
                "Killed",
                "Survived",
                "Equivalent",
                "Invalid",
                "Clean controls",
                "False positives",
                "Median witness bytes",
                "Evidence level",
                "Provenance",
                "Detector frozen",
            ],
            suite_rows,
        ),
        "## Evidence Provenance",
        markdown_table(["Evidence level", "Suites", "Mutants"], provenance_rows),
        "## Baselines",
        markdown_table(["Baseline", "Failures caught", "Catch rate"], baseline_rows),
    ]
    return "\n\n".join(sections) + "\n"


def suite_row(name: str, run_dir: Path) -> list[str]:
    traces = load_traces(run_dir)
    metadata = load_run_metadata(run_dir)
    statuses = Counter(accounting_status(trace) for trace in traces)
    return [
        name,
        str(len(traces)),
        str(statuses["killed"]),
        str(statuses["survived"]),
        str(statuses["equivalent"]),
        str(statuses["invalid"]),
        str(statuses["clean_control"]),
        str(statuses["false_positive"]),
        str(median_witness_bytes(run_dir, traces)),
        str(metadata.get("evidence_level", "deterministic_fixture")),
        str(metadata.get("suite_provenance", "hand_authored")),
        format_bool(bool(metadata.get("detector_frozen", False))),
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


def provenance_table_rows(runs: dict[str, Path]) -> list[list[str]]:
    suite_counts: Counter[str] = Counter()
    mutant_counts: Counter[str] = Counter()
    for path in runs.values():
        metadata = load_run_metadata(path)
        evidence_level = str(metadata.get("evidence_level", "deterministic_fixture"))
        suite_counts[evidence_level] += 1
        mutant_counts[evidence_level] += len(load_traces(path))
    return [
        [evidence_level, str(suite_counts[evidence_level]), str(mutant_counts[evidence_level])]
        for evidence_level in sorted(suite_counts)
    ]


def load_run_metadata(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "metadata.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"expected run metadata mapping: {path}")
    return raw


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


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

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from statistics import median
from typing import Any

try:
    from importlib.resources.abc import Traversable
except ImportError:  # Python 3.10 exposes Traversable from importlib.abc.
    from importlib.abc import Traversable

from policystrata.domain import BUILTIN_DOMAINS, domain_root
from policystrata.evidence import load_run_metadata, markdown_table, run_artifact_path
from policystrata.models import Trace, WitnessClass
from policystrata.summary import load_traces


def build_artifact_report(run_dir: Path, domain_path: Path | None = None) -> dict[str, Any]:
    traces = load_traces(run_dir)
    metadata = load_run_metadata(run_dir)
    domain = str(metadata.get("domain", "support_saas"))
    witness_sizes = witness_byte_sizes(run_dir, traces)
    artifact_stats = local_tree_stats(run_dir)
    fixture_stats = domain_fixture_stats(domain, domain_path)

    return {
        "run_dir": str(run_dir),
        "domain": domain,
        "suite": metadata.get("suite"),
        "evidence_level": metadata.get("evidence_level", "deterministic_fixture"),
        "suite_provenance": metadata.get("suite_provenance", "hand_authored"),
        "detector_frozen": bool(metadata.get("detector_frozen", False)),
        "traces": len(traces),
        "non_clean_traces": sum(1 for trace in traces if trace.witness_class != WitnessClass.CLEAN),
        "minimized_witnesses": len(witness_sizes),
        "median_witness_bytes": int(median(witness_sizes)) if witness_sizes else 0,
        "run_artifact_files": artifact_stats["files"],
        "run_artifact_bytes": artifact_stats["bytes"],
        "domain_fixture_files": fixture_stats["files"],
        "domain_fixture_bytes": fixture_stats["bytes"],
        "domain_fixture_lines": fixture_stats["lines"],
        "avg_latency_ms": round(average_latency(traces), 4),
        "p95_latency_ms": round(percentile_latency(traces, 0.95), 4),
        "estimated_cost": sum(int(trace.cost.get("estimated", 0)) for trace in traces),
        "requires_llm_api_key": False,
    }


def render_artifact_report(run_dir: Path, domain_path: Path | None = None) -> str:
    report = build_artifact_report(run_dir, domain_path)
    rows = [
        ["Run", report["run_dir"]],
        ["Domain", report["domain"]],
        ["Suite", str(report["suite"])],
        ["Evidence level", report["evidence_level"]],
        ["Suite provenance", report["suite_provenance"]],
        ["Detector frozen", "yes" if report["detector_frozen"] else "no"],
        ["Traces", str(report["traces"])],
        ["Non-clean traces", str(report["non_clean_traces"])],
        ["Minimized witnesses", str(report["minimized_witnesses"])],
        ["Median witness bytes", str(report["median_witness_bytes"])],
        ["Average trace latency ms", str(report["avg_latency_ms"])],
        ["P95 trace latency ms", str(report["p95_latency_ms"])],
        ["Estimated policy cost", str(report["estimated_cost"])],
        ["Run artifact files", str(report["run_artifact_files"])],
        ["Run artifact bytes", str(report["run_artifact_bytes"])],
        ["Domain fixture files", str(report["domain_fixture_files"])],
        ["Domain fixture bytes", str(report["domain_fixture_bytes"])],
        ["Domain fixture lines", str(report["domain_fixture_lines"])],
        ["Requires LLM API key", "no"],
    ]
    return "# PolicyStrata Artifact Report\n\n" + markdown_table(["Metric", "Value"], rows) + "\n"


def witness_byte_sizes(run_dir: Path, traces: Iterable[Trace]) -> list[int]:
    sizes: list[int] = []
    for trace in traces:
        if trace.witness_path:
            sizes.append(len(run_artifact_path(run_dir, trace.witness_path).read_bytes()))
    return sizes


def local_tree_stats(root: Path) -> dict[str, int]:
    files = [path for path in root.rglob("*") if path.is_file()]
    return {
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "lines": sum(count_lines(path.read_text(encoding="utf-8")) for path in text_files(files)),
    }


def domain_fixture_stats(domain: str, domain_path: Path | None) -> dict[str, int]:
    if domain_path is not None:
        return local_tree_stats(domain_path)
    if domain in BUILTIN_DOMAINS:
        return traversable_tree_stats(domain_root(domain))
    return {"files": 0, "bytes": 0, "lines": 0}


def traversable_tree_stats(root: Traversable) -> dict[str, int]:
    files = list(traversable_files(root))
    return {
        "files": len(files),
        "bytes": sum(len(path.read_bytes()) for path in files),
        "lines": sum(count_lines(path.read_text(encoding="utf-8")) for path in text_traversables(files)),
    }


def traversable_files(root: Traversable) -> Iterable[Traversable]:
    for child in root.iterdir():
        if child.is_dir():
            yield from traversable_files(child)
        elif child.is_file():
            yield child


def text_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.suffix in {".json", ".jsonl", ".md", ".sql", ".yaml", ".yml"}:
            yield path


def text_traversables(paths: Iterable[Traversable]) -> Iterable[Traversable]:
    for path in paths:
        if Path(path.name).suffix in {".sql", ".yaml", ".yml"}:
            yield path


def count_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def average_latency(traces: list[Trace]) -> float:
    if not traces:
        return 0.0
    return sum(trace.latency_ms for trace in traces) / len(traces)


def percentile_latency(traces: list[Trace], percentile: float) -> float:
    if not traces:
        return 0.0
    latencies = sorted(trace.latency_ms for trace in traces)
    index = min(len(latencies) - 1, max(0, int(round(percentile * (len(latencies) - 1)))))
    return latencies[index]


def artifact_report_json(run_dir: Path, domain_path: Path | None = None) -> str:
    return json.dumps(build_artifact_report(run_dir, domain_path), indent=2, sort_keys=True) + "\n"

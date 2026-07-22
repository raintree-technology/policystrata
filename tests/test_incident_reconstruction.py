"""Reconstructed real-fault suite: benchmarks/incident_reconstruction.

Verifies the deterministic fixtures built from 19 real, citation-backed cross-layer policy faults
(see benchmarks/incident_reconstruction/MAPPING.md) are valid, run cleanly through the same
simulator as the built-in domains, and are all killed with correct localization. This suite's
recall number is reported separately from the synthetic operator-generated suites in
docs/evidence.md; see docs/incident-reconstruction-results.md for the honest framing.
"""

from __future__ import annotations

from pathlib import Path

from policystrata.domain import load_suite_metadata, load_tasks
from policystrata.runner import run_suite
from policystrata.summary import summarize_run

DOMAIN_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "incident_reconstruction"


def test_reconstructed_suite_loads_expected_task_count() -> None:
    tasks = load_tasks("incident_reconstruction", "reconstructed", DOMAIN_PATH)

    assert len(tasks) == 19
    assert len({task.id for task in tasks}) == 19


def test_reconstructed_suite_metadata_is_incident_reconstruction() -> None:
    metadata = load_suite_metadata("incident_reconstruction", "reconstructed", DOMAIN_PATH)

    assert metadata.provenance == "incident_reconstruction"
    assert metadata.evidence_level == "deterministic_fixture"
    assert metadata.notes, "suite_metadata.notes must carry the citation trail"


def test_reconstructed_suite_kills_every_task_with_correct_localization(tmp_path) -> None:
    out_dir = tmp_path / "run"

    traces = run_suite("incident_reconstruction", "reconstructed", out_dir, DOMAIN_PATH)
    summary = summarize_run(out_dir)

    assert len(traces) == 19
    assert summary.total == 19
    assert summary.killed == 19
    assert summary.survived == 0
    assert summary.mutant_kill_rate == 1.0
    assert summary.localization_accuracy == 1.0
    assert summary.expected_class_accuracy == 1.0

    for trace in traces:
        assert trace.accounting_status == "killed", trace.task_id
        assert trace.witness_class == trace.expected_witness_class, trace.task_id
        assert trace.localized_surface == trace.expected_localized_surface, trace.task_id
        assert trace.containment_layer == trace.expected_containment_layer, trace.task_id
        assert trace.witness_path is not None, trace.task_id
        assert trace.request, trace.task_id
        assert "http" in trace.request, f"{trace.task_id} request must carry its source citation"


def test_reconstructed_suite_run_metadata_reports_provenance(tmp_path) -> None:
    import json

    out_dir = tmp_path / "run"
    run_suite("incident_reconstruction", "reconstructed", out_dir, DOMAIN_PATH)

    metadata = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["suite_provenance"] == "incident_reconstruction"
    assert metadata["evidence_level"] == "deterministic_fixture"
    assert metadata["trace_count"] == 19

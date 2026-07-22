from __future__ import annotations

from pathlib import Path

from policystrata.domain import load_policy, load_surface_config
from policystrata.minimization import measure_trace, minimization_report
from policystrata.models import SemanticQuery, Task, WitnessClass
from policystrata.runner import evaluate_task, run_suite


def test_measure_trace_reports_reduction_and_one_minimality() -> None:
    policy = load_policy("support_saas")
    surfaces = load_surface_config("support_saas")
    principal = next(p.id for p in policy.principals.values() if "admin" not in p.role)
    # The grammar mutation's witness is driven by the sensitive dimension, so the
    # extra "region" dimension is removable noise the reducer should drop.
    task = Task(
        id="min_case",
        domain="support_saas",
        principal=principal,
        request="minimization test",
        policy_version=policy.version,
        surface_versions=surfaces.versions,
        mutation="grammar_permits_forbidden_dimension",
        semantic_query=SemanticQuery(
            metric="ticket_count", dimensions=["customer_email", "region"], limit=100
        ),
        expected_witness_class=WitnessClass.OVER_PERMISSIVE,
        expected_localized_surface="grammar",
    )
    trace = evaluate_task(policy, task, surfaces)
    assert trace.witness_class != WitnessClass.CLEAN
    entry = measure_trace(policy, surfaces, trace)
    assert entry is not None
    assert 0.0 <= entry.reduction_ratio <= 1.0
    assert entry.minimized_bytes <= entry.original_bytes
    assert entry.minimized_ir_bytes <= entry.original_ir_bytes
    assert entry.dimensions_removed >= 1
    assert isinstance(entry.one_minimal, bool)


def test_clean_trace_has_no_minimization() -> None:
    policy = load_policy("support_saas")
    surfaces = load_surface_config("support_saas")
    principal = next(p.id for p in policy.principals.values() if "admin" not in p.role)
    task = Task(
        id="clean_case",
        domain="support_saas",
        principal=principal,
        request="clean",
        policy_version=policy.version,
        surface_versions=surfaces.versions,
        mutation="none",
        semantic_query=SemanticQuery(metric="ticket_count"),
        expected_witness_class=WitnessClass.CLEAN,
        expected_localized_surface="release",
    )
    trace = evaluate_task(policy, task, surfaces)
    assert measure_trace(policy, surfaces, trace) is None


def test_minimization_report_over_run(tmp_path: Path) -> None:
    out = tmp_path / "seeded"
    run_suite("support_saas", "seeded", out)
    report = minimization_report(out)
    assert report.domain == "support_saas"
    assert report.total_witnesses == 50
    assert report.one_minimal_rate == 1.0
    assert 0.0 <= report.median_reduction_ratio <= 1.0
    assert report.median_ir_reduction_ratio >= report.median_reduction_ratio - 1e-9
    assert report.total_reduction_ms >= 0.0

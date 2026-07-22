from __future__ import annotations

from pathlib import Path

from policystrata.difficulty import (
    deployable_baselines,
    difficulty_report,
    difficulty_report_from_runs,
)
from policystrata.runner import run_suite
from policystrata.summary import load_traces


def test_composite_baselines_excluded() -> None:
    names = set(deployable_baselines())
    assert "defense_in_depth_stack" not in names
    assert "defense_in_depth_stack_v2" not in names
    assert "naive_surface_equality" in names


def test_difficulty_differentiates_operators(tmp_path: Path) -> None:
    run_dir = tmp_path / "gen"
    run_suite("support_saas", "generated", run_dir, generated_count=300, generated_seed=1729)
    report = difficulty_report(load_traces(run_dir))
    assert report.total_cases == 300
    assert report.baseline_count == deployable_baselines().__len__()
    # Tiers sum to the case count.
    assert sum(report.tier_counts.values()) == report.total_cases
    # Operators vary in how many baselines catch them (real differentiation).
    means = [op.mean_baseline_catchers for op in report.operators]
    assert max(means) > min(means)


def test_per_operator_tiers_sum_to_cases(tmp_path: Path) -> None:
    run_dir = tmp_path / "gen"
    run_suite("support_saas", "generated", run_dir, generated_count=200, generated_seed=1729)
    report = difficulty_report_from_runs([run_dir])
    for operator in report.operators:
        assert operator.hard + operator.medium + operator.easy == operator.cases

"""Difficulty tiers derived from the baseline kill matrix.

A benchmark case is "hard" when few detection strategies catch it and "easy"
when most do. This module scores every non-clean trace by how many baseline
detection strategies catch it, assigns a difficulty tier, and aggregates by
operator so a leaderboard can weight or bucket cases.

Difficulty is scored against the full baseline set: every baseline is a distinct
detection strategy, and on a non-clean trace their predicates are all in their
intended domain. The union of them still misses the hardest cases, which is
exactly the signal difficulty tiers capture. The composite "defense-in-depth"
baselines are excluded from the count because they are unions of the others and
would double-weight cases their members already catch.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from policystrata.baselines import BASELINES, BaselinePredicate
from policystrata.models import InputModel, Trace, WitnessClass
from policystrata.summary import load_traces

# Composite baselines are unions of the individual detection strategies; counting
# them would double-weight cases their members already catch.
_COMPOSITE_BASELINES = frozenset({"defense_in_depth_stack", "defense_in_depth_stack_v2"})


def deployable_baselines() -> dict[str, BaselinePredicate]:
    return {name: predicate for name, predicate in BASELINES.items() if name not in _COMPOSITE_BASELINES}


def _tier(catchers: int, total_baselines: int) -> str:
    if catchers <= max(1, total_baselines // 6):
        return "hard"
    if catchers <= total_baselines // 2:
        return "medium"
    return "easy"


class OperatorDifficulty(InputModel):
    operator: str
    cases: int
    mean_baseline_catchers: float
    hard: int
    medium: int
    easy: int


class DifficultyReport(InputModel):
    total_cases: int
    baseline_count: int
    tier_counts: dict[str, int]
    operators: list[OperatorDifficulty]


def difficulty_report(traces: list[Trace]) -> DifficultyReport:
    baselines = deployable_baselines()
    total_baselines = len(baselines)
    non_clean = [trace for trace in traces if trace.witness_class != WitnessClass.CLEAN]

    per_operator: dict[str, list[int]] = {}
    per_operator_tiers: dict[str, Counter[str]] = {}
    tier_counts: Counter[str] = Counter()

    for trace in non_clean:
        catchers = sum(1 for predicate in baselines.values() if predicate(trace))
        tier = _tier(catchers, total_baselines)
        tier_counts[tier] += 1
        per_operator.setdefault(trace.mutation, []).append(catchers)
        per_operator_tiers.setdefault(trace.mutation, Counter())[tier] += 1

    operators = []
    for operator, catcher_counts in sorted(per_operator.items()):
        tiers = per_operator_tiers[operator]
        operators.append(
            OperatorDifficulty(
                operator=operator,
                cases=len(catcher_counts),
                mean_baseline_catchers=sum(catcher_counts) / len(catcher_counts),
                hard=tiers["hard"],
                medium=tiers["medium"],
                easy=tiers["easy"],
            )
        )

    return DifficultyReport(
        total_cases=len(non_clean),
        baseline_count=total_baselines,
        tier_counts=dict(tier_counts),
        operators=operators,
    )


def difficulty_report_from_runs(run_dirs: list[Path]) -> DifficultyReport:
    traces: list[Trace] = []
    for run_dir in run_dirs:
        traces.extend(load_traces(run_dir))
    return difficulty_report(traces)

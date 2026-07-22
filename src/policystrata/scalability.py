"""Scalability curves and covering-array case generation.

Two things the review asked for and the paper only mentioned:

* **Covering arrays.** Exhaustively crossing every principal x role x metric x
  dimension x operator is combinatorial. A t-way covering array covers all
  t-way interactions with far fewer cases. :func:`covering_array` implements a
  deterministic greedy pairwise (and general t-way) generator and reports the
  reduction versus the full cross product.

* **Scalability curves.** :func:`throughput_curve` measures detector cost
  (wall-clock per case, estimated query cost) as suite size grows, and
  :func:`factor_scaling` measures how covering-array size grows with the number
  of principals, roles, and schema objects.

Neither adds a dependency; the covering-array generator is pure Python.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from itertools import combinations, product
from pathlib import Path
from typing import Any

from policystrata.models import InputModel


class CoveringArrayResult(InputModel):
    strength: int
    factor_names: list[str]
    factor_sizes: list[int]
    full_cross_product: int
    covering_array_size: int
    reduction_ratio: float
    all_interactions_covered: bool
    rows: list[dict[str, Any]]


def _all_interactions(
    factors: list[tuple[str, list[Any]]],
    strength: int,
) -> set[tuple[tuple[str, Any], ...]]:
    interactions: set[tuple[tuple[str, Any], ...]] = set()
    for factor_combo in combinations(range(len(factors)), strength):
        value_lists = [factors[i][1] for i in factor_combo]
        for values in product(*value_lists):
            interactions.add(
                tuple((factors[i][0], value) for i, value in zip(factor_combo, values, strict=True))
            )
    return interactions


def _row_interactions(
    row: dict[str, Any],
    factor_names: list[str],
    strength: int,
) -> set[tuple[tuple[str, Any], ...]]:
    covered: set[tuple[tuple[str, Any], ...]] = set()
    for combo in combinations(factor_names, strength):
        covered.add(tuple((name, row[name]) for name in combo))
    return covered


def covering_array(
    factors: Mapping[str, Sequence[Any]],
    strength: int = 2,
) -> CoveringArrayResult:
    """Deterministic greedy t-way covering array.

    Builds rows one at a time; each new row greedily fixes each factor to the
    value that covers the most still-uncovered t-way interactions. Guarantees
    every t-way interaction is covered (falls back to adding the uncovered
    interaction directly if the greedy row misses it).
    """
    if strength < 1:
        raise ValueError("covering-array strength must be at least 1")
    ordered = [(name, list(values)) for name, values in sorted(factors.items())]
    if any(not values for _, values in ordered):
        raise ValueError("every factor must have at least one value")
    strength = min(strength, len(ordered))

    factor_names = [name for name, _ in ordered]
    remaining = _all_interactions(ordered, strength)
    full_cross = 1
    for _, values in ordered:
        full_cross *= len(values)

    rows: list[dict[str, Any]] = []
    while remaining:
        row: dict[str, Any] = {}
        for name, values in ordered:
            best_value = values[0]
            best_gain = -1
            for value in values:
                candidate = {**row, name: value}
                # Count how many not-yet-placed interactions this choice enables.
                gain = 0
                for combo in _row_interactions_partial(candidate, factor_names, strength):
                    if combo in remaining:
                        gain += 1
                if gain > best_gain:
                    best_gain = gain
                    best_value = value
            row[name] = best_value
        covered = _row_interactions(row, factor_names, strength)
        newly = covered & remaining
        if not newly:
            # Greedy row covered nothing new (rare); seed from an uncovered tuple.
            row = _row_from_interaction(next(iter(remaining)), ordered)
            covered = _row_interactions(row, factor_names, strength)
        remaining -= covered
        rows.append(row)

    size = len(rows)
    return CoveringArrayResult(
        strength=strength,
        factor_names=factor_names,
        factor_sizes=[len(values) for _, values in ordered],
        full_cross_product=full_cross,
        covering_array_size=size,
        reduction_ratio=1.0 - (size / full_cross) if full_cross else 0.0,
        all_interactions_covered=True,
        rows=rows,
    )


def _row_interactions_partial(
    partial: dict[str, Any],
    factor_names: list[str],
    strength: int,
) -> set[tuple[tuple[str, Any], ...]]:
    placed = [name for name in factor_names if name in partial]
    if len(placed) < strength:
        return set()
    covered: set[tuple[tuple[str, Any], ...]] = set()
    for combo in combinations(placed, strength):
        covered.add(tuple((name, partial[name]) for name in combo))
    return covered


def _row_from_interaction(
    interaction: tuple[tuple[str, Any], ...],
    ordered: list[tuple[str, list[Any]]],
) -> dict[str, Any]:
    fixed = dict(interaction)
    return {name: fixed.get(name, values[0]) for name, values in ordered}


class ThroughputPoint(InputModel):
    cases: int
    total_ms: float
    mean_ms_per_case: float
    kills: int
    estimated_cost: int


class ThroughputCurve(InputModel):
    domain: str
    points: list[ThroughputPoint]


def throughput_curve(
    domain: str,
    sizes: Sequence[int] = (50, 100, 200, 400, 800),
    seed: int = 1729,
    base_path: Path | None = None,
) -> ThroughputCurve:
    """Detector cost as suite size grows, on a real domain."""
    from policystrata.domain import load_policy, load_surface_config, load_surfaces
    from policystrata.generator import generate_tasks
    from policystrata.runner import evaluate_task

    policy = load_policy(domain, base_path)
    surfaces = load_surfaces(domain, base_path)
    surface_config = load_surface_config(domain, base_path)

    points: list[ThroughputPoint] = []
    for size in sizes:
        tasks = generate_tasks(domain, policy, surfaces, count=size, seed=seed)
        started = time.perf_counter()
        traces = [evaluate_task(policy, task, surface_config) for task in tasks]
        total_ms = (time.perf_counter() - started) * 1000
        kills = sum(1 for trace in traces if trace.accounting_status == "killed")
        cost = sum(int(trace.cost.get("estimated", 0)) for trace in traces)
        points.append(
            ThroughputPoint(
                cases=size,
                total_ms=total_ms,
                mean_ms_per_case=total_ms / size if size else 0.0,
                kills=kills,
                estimated_cost=cost,
            )
        )
    return ThroughputCurve(domain=domain, points=points)


class FactorScalingPoint(InputModel):
    principals: int
    roles: int
    schema_objects: int
    operators: int
    full_cross_product: int
    covering_array_size: int
    reduction_ratio: float


def factor_scaling(
    principal_counts: Sequence[int] = (2, 4, 8, 16, 32),
    roles: int = 4,
    schema_objects: int = 8,
    operators: int = 21,
    strength: int = 2,
) -> list[FactorScalingPoint]:
    """Covering-array size versus the number of principals (and fixed roles,
    schema objects, operators)."""
    points: list[FactorScalingPoint] = []
    for principals in principal_counts:
        factors = {
            "principal": [f"p{i}" for i in range(principals)],
            "role": [f"r{i}" for i in range(roles)],
            "schema_object": [f"s{i}" for i in range(schema_objects)],
            "operator": [f"op{i}" for i in range(operators)],
        }
        result = covering_array(factors, strength=strength)
        points.append(
            FactorScalingPoint(
                principals=principals,
                roles=roles,
                schema_objects=schema_objects,
                operators=operators,
                full_cross_product=result.full_cross_product,
                covering_array_size=result.covering_array_size,
                reduction_ratio=result.reduction_ratio,
            )
        )
    return points

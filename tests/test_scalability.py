from __future__ import annotations

from itertools import combinations, product

import pytest

from policystrata.scalability import (
    covering_array,
    factor_scaling,
    throughput_curve,
)


def _all_pairs(factors: dict[str, list[str]]) -> set:
    names = sorted(factors)
    pairs = set()
    for a, b in combinations(names, 2):
        for va, vb in product(factors[a], factors[b]):
            pairs.add(((a, va), (b, vb)))
    return pairs


def test_pairwise_covering_array_covers_all_pairs() -> None:
    factors = {
        "principal": [f"p{i}" for i in range(6)],
        "role": [f"r{i}" for i in range(3)],
        "operator": [f"op{i}" for i in range(10)],
    }
    result = covering_array(factors, strength=2)
    names = sorted(factors)
    covered = set()
    for row in result.rows:
        for a, b in combinations(names, 2):
            covered.add(((a, row[a]), (b, row[b])))
    assert _all_pairs(factors) <= covered
    assert result.all_interactions_covered is True
    # A pairwise array must be far smaller than the full cross product.
    assert result.covering_array_size < result.full_cross_product
    assert result.reduction_ratio > 0.5


def test_strength_one_covers_every_value() -> None:
    factors = {"a": ["a1", "a2", "a3"], "b": ["b1", "b2", "b3", "b4"]}
    result = covering_array(factors, strength=1)
    seen = {(name, row[name]) for row in result.rows for name in factors}
    for name, values in factors.items():
        for value in values:
            assert (name, value) in seen


def test_covering_array_rejects_empty_factor() -> None:
    with pytest.raises(ValueError):
        covering_array({"a": ["a1"], "b": []})


def test_throughput_curve_is_measured() -> None:
    curve = throughput_curve("support_saas", sizes=(50, 100))
    assert [p.cases for p in curve.points] == [50, 100]
    for point in curve.points:
        assert point.kills == point.cases  # every generated mutant is killed
        assert point.mean_ms_per_case >= 0.0


def test_factor_scaling_reduction_grows_with_size() -> None:
    points = factor_scaling(principal_counts=(2, 8, 32))
    assert points[0].covering_array_size < points[-1].covering_array_size
    # Reduction ratio should not shrink as the cross product grows.
    assert points[-1].reduction_ratio >= points[0].reduction_ratio

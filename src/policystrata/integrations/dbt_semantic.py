from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from policystrata.domain import load_policy, load_yaml_mapping
from policystrata.models import DimensionPolicy, MetricPolicy

DBT_SEMANTIC_WARNING_KEYS = (
    "missing_policy_metrics",
    "stale_dbt_metrics",
    "missing_policy_dimensions",
    "stale_dbt_dimensions",
    "expression_mismatches",
    "sensitive_metadata_missing",
)


def load_dbt_semantic_names(path: Path) -> dict[str, set[str]]:
    inventory = load_dbt_semantic_inventory(path)
    return {
        "metrics": set(inventory["metrics"]),
        "measures": set(inventory["measures"]),
        "dimensions": set(inventory["dimensions"]),
    }


def load_dbt_semantic_inventory(path: Path) -> dict[str, Any]:
    raw = load_yaml_mapping(path)
    metrics = {
        str(metric["name"])
        for metric in raw.get("metrics", [])
        if isinstance(metric, Mapping) and "name" in metric
    }
    measures: dict[str, dict[str, Any]] = {}
    dimensions: dict[str, dict[str, Any]] = {}
    semantic_models: list[dict[str, Any]] = []

    for model in raw.get("semantic_models", []):
        if not isinstance(model, Mapping):
            continue
        model_name = str(model.get("name", "<unnamed>"))
        semantic_models.append(
            {
                "name": model_name,
                "model": str(model.get("model", "")),
            }
        )
        for measure in model.get("measures", []):
            if isinstance(measure, Mapping) and "name" in measure:
                measure_name = str(measure["name"])
                measures[measure_name] = dict(measure)
        for dimension in model.get("dimensions", []):
            if isinstance(dimension, Mapping) and "name" in dimension:
                dimension_name = str(dimension["name"])
                dimensions[dimension_name] = dict(dimension)

    return {
        "metrics": metrics,
        "measures": measures,
        "dimensions": dimensions,
        "semantic_models": semantic_models,
    }


def compare_dbt_semantic_model(
    domain: str,
    path: Path,
    base_path: Path | None = None,
) -> dict[str, Any]:
    return inspect_dbt_semantic_model(domain, path, base_path)


def inspect_dbt_semantic_model(
    domain: str,
    path: Path,
    base_path: Path | None = None,
) -> dict[str, Any]:
    policy = load_policy(domain, base_path)
    inventory = load_dbt_semantic_inventory(path)
    policy_metrics = set(policy.metrics)
    policy_dimensions = set(policy.dimensions)
    dbt_metric_names = set(inventory["metrics"]) | set(inventory["measures"])
    dbt_dimensions = set(inventory["dimensions"])

    return {
        "domain": domain,
        "path": str(path),
        "matched_metrics": sorted(policy_metrics & dbt_metric_names),
        "missing_policy_metrics": sorted(policy_metrics - dbt_metric_names),
        "stale_dbt_metrics": sorted(dbt_metric_names - policy_metrics),
        "matched_dimensions": sorted(policy_dimensions & dbt_dimensions),
        "missing_policy_dimensions": sorted(policy_dimensions - dbt_dimensions),
        "stale_dbt_dimensions": sorted(dbt_dimensions - policy_dimensions),
        "expression_mismatches": expression_mismatches(policy.metrics, inventory["measures"]),
        "sensitive_metadata_missing": sensitive_metadata_missing(
            policy.dimensions,
            inventory["dimensions"],
        ),
        "models_missing_lineage": models_missing_lineage(inventory["semantic_models"]),
    }


def dbt_semantic_has_warnings(result: Mapping[str, object]) -> bool:
    return any(bool(result.get(key)) for key in DBT_SEMANTIC_WARNING_KEYS)


def expression_mismatches(
    policy_metrics: dict[str, MetricPolicy],
    dbt_measures: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    for metric_name, metric in sorted(policy_metrics.items()):
        measure = dbt_measures.get(metric_name)
        if measure is None:
            continue
        expr = str(measure.get("expr", "")).strip()
        if not expr:
            mismatches.append(
                {
                    "metric": metric_name,
                    "policy_expression": metric.expression,
                    "dbt_expression": expr,
                    "reason": "dbt measure expression is empty",
                }
            )
            continue
        if not expression_matches_policy(expr, metric):
            mismatches.append(
                {
                    "metric": metric_name,
                    "policy_expression": metric.expression,
                    "dbt_expression": expr,
                    "reason": "dbt measure expression does not reference the policy metric column",
                }
            )
    return mismatches


def expression_matches_policy(expr: str, metric: MetricPolicy) -> bool:
    normalized_expr = normalize_expression(expr)
    if normalized_expr in normalize_expression(metric.expression):
        return True
    for column in metric.columns:
        normalized_column = normalize_expression(column)
        column_tail = normalized_column.split(".")[-1]
        if normalized_expr in (normalized_column, column_tail):
            return True
    return False


def sensitive_metadata_missing(
    policy_dimensions: dict[str, DimensionPolicy],
    dbt_dimensions: dict[str, dict[str, Any]],
) -> list[str]:
    missing: list[str] = []
    for dimension_name, dimension in sorted(policy_dimensions.items()):
        if not dimension.sensitive or dimension_name not in dbt_dimensions:
            continue
        if not dbt_dimension_declares_sensitive(dbt_dimensions[dimension_name]):
            missing.append(dimension_name)
    return missing


def dbt_dimension_declares_sensitive(dimension: dict[str, Any]) -> bool:
    meta = dimension.get("meta", {})
    if isinstance(meta, Mapping) and meta.get("sensitive") is True:
        return True
    if isinstance(meta, Mapping):
        policystrata = meta.get("policystrata", {})
        if isinstance(policystrata, Mapping) and policystrata.get("sensitive") is True:
            return True
    return False


def models_missing_lineage(semantic_models: list[dict[str, Any]]) -> list[str]:
    return [model["name"] for model in semantic_models if not model.get("model")]


def normalize_expression(expr: str) -> str:
    return "".join(char for char in expr.lower() if char.isalnum() or char in "._")

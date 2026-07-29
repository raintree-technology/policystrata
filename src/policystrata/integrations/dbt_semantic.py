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

# Names a query interface can group by without the semantic model declaring them as dimensions.
# `metric_time` is the aggregation-time dimension every metric exposes.
SEMANTIC_LAYER_BUILTIN_DIMENSIONS = frozenset({"metric_time"})


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
    entities: set[str] = set()
    # Local dimension name -> every name a query interface may use to reach it. Semantic layers
    # let a query join through an entity and refer to `entity__dimension`, a name that never
    # appears verbatim in the manifest.
    dimension_aliases: dict[str, set[str]] = {}
    # Same idea for entities, which are groupable in their own right.
    entity_aliases: dict[str, set[str]] = {}

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
        model_entities = entity_names(model)
        entities.update(model_entities)
        # An entity is groupable on its own and also reachable through another entity declared on
        # the same model, so a mapping model with entities {listing, lux_listing} serves both
        # `lux_listing` and `listing__lux_listing`.
        for entity in model_entities:
            aliases = entity_aliases.setdefault(entity, {entity})
            aliases.update(f"{other}__{entity}" for other in model_entities if other != entity)
        for measure in model.get("measures", []):
            if isinstance(measure, Mapping) and "name" in measure:
                measure_name = str(measure["name"])
                measures[measure_name] = dict(measure)
        for dimension in model.get("dimensions", []):
            if isinstance(dimension, Mapping) and "name" in dimension:
                dimension_name = str(dimension["name"])
                dimensions[dimension_name] = dict(dimension)
                # Qualify by this model's own entities, not by every entity in the project.
                aliases = dimension_aliases.setdefault(dimension_name, {dimension_name})
                aliases.update(f"{entity}__{dimension_name}" for entity in model_entities)

    return {
        "metrics": metrics,
        "measures": measures,
        "dimensions": dimensions,
        "entities": entities,
        "dimension_aliases": dimension_aliases,
        "entity_aliases": entity_aliases,
        "semantic_models": semantic_models,
    }


def entity_names(model: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    primary = model.get("primary_entity")
    if isinstance(primary, str) and primary:
        names.add(primary)
    for entity in model.get("entities", []):
        if isinstance(entity, Mapping) and "name" in entity:
            names.add(str(entity["name"]))
    return names


def resolvable_dimension_names(inventory: Mapping[str, Any]) -> set[str]:
    """Every dimension name a policy may legitimately reference.

    Declared local names, their entity-qualified forms, the entities themselves (groupable on
    their own), and the semantic layer's built-ins.
    """
    resolvable: set[str] = set(SEMANTIC_LAYER_BUILTIN_DIMENSIONS)
    for aliases in inventory["dimension_aliases"].values():
        resolvable.update(aliases)
    for aliases in inventory["entity_aliases"].values():
        resolvable.update(aliases)
    return resolvable


def governable_metric_names(inventory: Mapping[str, Any]) -> set[str]:
    """Names that are meant to be governed individually.

    Metrics declared in their own document, plus measures the manifest auto-promotes with
    `create_metric: true`. A measure without it is a private building block: policy is not
    expected to name it, so reporting it as stale is noise.
    """
    promoted = {
        name for name, measure in inventory["measures"].items() if measure.get("create_metric") is True
    }
    return set(inventory["metrics"]) | promoted


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
    # Asymmetric on purpose. "Can the policy's name be served?" needs the broadest pool, so a
    # policy metric backed by a private measure is not reported missing. "Is this dbt name
    # ungoverned?" needs only the names meant to be governed individually.
    servable_metric_names = set(inventory["metrics"]) | set(inventory["measures"])
    governable_metrics = governable_metric_names(inventory)
    # Same asymmetry for dimensions: a policy may reference an entity-qualified name, while
    # staleness is judged against what the manifest actually declares.
    resolvable_dimensions = resolvable_dimension_names(inventory)
    declared_dimensions = set(inventory["dimensions"])
    dimension_aliases = inventory["dimension_aliases"]
    stale_dimensions = {
        name for name in declared_dimensions if not (dimension_aliases.get(name, {name}) & policy_dimensions)
    }

    return {
        "domain": domain,
        "path": str(path),
        "matched_metrics": sorted(policy_metrics & servable_metric_names),
        "missing_policy_metrics": sorted(policy_metrics - servable_metric_names),
        "stale_dbt_metrics": sorted(governable_metrics - policy_metrics),
        "matched_dimensions": sorted(policy_dimensions & resolvable_dimensions),
        "missing_policy_dimensions": sorted(policy_dimensions - resolvable_dimensions),
        "stale_dbt_dimensions": sorted(stale_dimensions),
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
        # An omitted `expr` is not an empty expression. dbt/MetricFlow default it to the measure's
        # own name, so resolve it that way and judge the result like any other expression.
        expr = str(measure.get("expr", "")).strip() or metric_name
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
    if not normalized_expr:
        # The substring tests below would both accept an empty expression, since "" is a
        # substring of everything. Callers resolve an omitted `expr:` to the measure name
        # before getting here, so this is unreachable today; it is an explicit no rather
        # than a silent yes, because the failure it would otherwise produce is a check that
        # always passes.
        return False
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

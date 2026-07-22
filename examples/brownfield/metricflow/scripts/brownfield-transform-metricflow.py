#!/usr/bin/env python3
"""Deterministic brownfield transform for dbt-labs/metricflow.

Reads native metricflow fixtures from a shallow clone of dbt-labs/metricflow and
produces PolicyStrata scanner inputs:

  1. ``semantic_models.yml`` -- a mechanical multi-doc-to-plural-list merge of
     metricflow's own ``simple_manifest`` semantic-model and metric YAML (the
     "their multi-doc singular ``semantic_model:`` form needs a small merge
     transform" gap called out in the brownfield inventory). Content is native;
     the only addition is a ``model: ref('<alias>')`` lineage field synthesized
     from each model's real ``node_relation.alias`` so PolicyStrata's dbt
     adapter does not flag every model as lineage-less (metricflow's own test
     fixtures use ``node_relation`` instead of dbt-project ``ref()`` syntax).
  2. ``traces.jsonl`` -- imported-trace records synthesized from
     ``tests_metricflow/integration/test_cases/itest_*.yaml``. Each record's
     ``sql`` is metricflow's own ``check_query`` (real, hand-authored expected
     SQL from metricflow's integration-test suite), lightly rendered by
     substituting the ``{{ source_schema }}`` Jinja placeholder with a fixed
     schema name. Test cases that use any other Jinja helper (metricflow's
     test-harness-only macros such as ``render_time_constraint``) are skipped
     rather than guessed at, because reimplementing those macros would mean
     inventing SQL metricflow never produced. Every other field on the trace
     (principal, tenant_ids, time_range, grain, limit) is synthesized, because
     metricflow is a single-tenant SQL compiler with no principal/tenancy
     concept at all.
  3. ``domain/policy.yaml`` -- a PolicyStrata domain policy auto-derived from
     the merged semantic manifest: one metric per dbt metric (expression
     templated from the underlying measure's ``agg``/``expr``), one dimension
     per raw metricflow dimension name (for the dbt-adapter comparison) plus
     one per distinct group-by token observed in the selected traces
     (metricflow's queries reference entity-qualified dunder names such as
     ``booking__is_instant``, which do not appear verbatim in any semantic
     model's ``dimensions:`` list). A single synthetic role/principal covers
     everything; there is no real role structure to reflect.

Nothing under the metricflow clone is executed; this script only parses YAML
and does bounded, whitelisted string substitution.

Usage:
    python brownfield-transform-metricflow.py --source <metricflow-clone> --out <example-dir>
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

SYNTHETIC_SCHEMA = "mf_brownfield_src"
JINJA_TOKEN_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}", re.DOTALL)
SELECT_ALIAS_PATTERN = r"^(?P<expr>.+?)\s+AS\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*,?\s*$"
SELECT_ALIAS_RE = re.compile(SELECT_ALIAS_PATTERN, re.IGNORECASE)
FORBIDDEN_SQL_TOKENS = {
    "alter", "call", "copy", "create", "delete", "do", "drop", "execute", "grant",
    "insert", "merge", "notify", "reindex", "reset", "revoke", "set", "truncate",
    "update", "vacuum",
}
SENSITIVE_NAME_HINTS = ("email", "name", "ip", "phone", "address", "ssn")
SYNTHETIC_PRINCIPAL = "metricflow_query_service"
SYNTHETIC_ROLE = "compiler_output"
SYNTHETIC_TENANT = "mf_default_tenant"
SYNTHETIC_TIME_RANGE = "all_time"
SYNTHETIC_GRAIN = "day"
SYNTHETIC_LIMIT = 1000


def load_docs_by_key(path: Path, key: str) -> list[dict[str, Any]]:
    """Parse a metricflow multi-doc YAML file, keeping only ``key:`` documents.

    Some metricflow fixture files (for example ``user_sm_source.yaml``) mix one
    ``semantic_model:`` document with several trailing ``metric:`` documents in
    the same file, so callers filter by key rather than assume uniform docs.
    """
    items: list[dict[str, Any]] = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if not doc or key not in doc:
            continue
        items.append(dict(doc[key]))
    return items


def merge_semantic_manifest(models_dir: Path, metrics_path: Path) -> dict[str, Any]:
    """Merge metricflow's singular multi-doc manifest into a plural single-doc form."""
    semantic_models: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    for model_path in sorted(models_dir.glob("*.yaml")):
        for model in load_docs_by_key(model_path, "semantic_model"):
            node_relation = model.get("node_relation") or {}
            alias = node_relation.get("alias")
            if alias and "model" not in model:
                model["model"] = f"ref('{alias}')"
            semantic_models.append(model)
        metrics.extend(load_docs_by_key(model_path, "metric"))
    metrics.extend(load_docs_by_key(metrics_path, "metric"))
    return {"semantic_models": semantic_models, "metrics": metrics}


def jinja_tokens(text: str) -> list[str]:
    return [match.group(1).strip() for match in JINJA_TOKEN_RE.finditer(text)]


def render_check_query(check_query: str) -> str | None:
    """Render check_query if its only Jinja reference is {{ source_schema }}."""
    tokens = jinja_tokens(check_query)
    if any(token != "source_schema" for token in tokens):
        return None
    return JINJA_TOKEN_RE.sub(SYNTHETIC_SCHEMA, check_query).strip()


def sql_is_read_only(sql: str) -> bool:
    lowered = sql.strip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    return re.search(r"\b(" + "|".join(sorted(FORBIDDEN_SQL_TOKENS)) + r")\b", lowered) is None


def iter_integration_tests(path: Path) -> list[dict[str, Any]]:
    tests = []
    for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if not doc or "integration_test" not in doc:
            continue
        tests.append(doc["integration_test"])
    return tests


def extract_metric_expression_from_sql(sql: str, metric_name: str) -> str | None:
    for line in sql.splitlines():
        match = SELECT_ALIAS_RE.match(line.strip())
        if match and match.group("alias").lower() == metric_name.lower():
            return match.group("expr").strip()
        if line.strip().upper().startswith("FROM"):
            break
    return None


def select_traces(itest_dir: Path, source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select renderable, single-metric itest cases and synthesize trace records."""
    selected: list[dict[str, Any]] = []
    skipped: dict[str, int] = {
        "multi_metric_ir_unsupported": 0,
        "unrendered_jinja_macro": 0,
        "unusable_sql": 0,
        "non_simple_manifest_model": 0,
    }
    seen_ids: set[str] = set()
    for itest_path in sorted(itest_dir.glob("itest_*.yaml")):
        relative_source = itest_path.relative_to(source_root).as_posix()
        for test in iter_integration_tests(itest_path):
            metrics = test.get("metrics") or []
            check_query = test.get("check_query")
            name = str(test.get("name", "unnamed"))
            # itest_*.yaml cases are parameterized across several manifest fixtures
            # (SIMPLE_MODEL, SCD_MODEL, EXTENDED_DATE_MODEL, ...); only SIMPLE_MODEL
            # matches the simple_manifest semantic layer merged into semantic_models.yml.
            if test.get("model") != "SIMPLE_MODEL":
                skipped["non_simple_manifest_model"] += 1
                continue
            if len(metrics) != 1:
                skipped["multi_metric_ir_unsupported"] += 1
                continue
            if not check_query:
                skipped["unusable_sql"] += 1
                continue
            rendered = render_check_query(check_query)
            if rendered is None:
                skipped["unrendered_jinja_macro"] += 1
                continue
            if not sql_is_read_only(rendered):
                skipped["unusable_sql"] += 1
                continue
            trace_id = name if name not in seen_ids else f"{itest_path.stem}__{name}"
            seen_ids.add(trace_id)
            selected.append(
                {
                    "trace_id": trace_id,
                    "metric": str(metrics[0]),
                    "dimensions": [str(item) for item in (test.get("group_bys") or [])],
                    "sql": rendered,
                    "source_file": relative_source,
                    "test_name": name,
                    "description": str(test.get("description", "")),
                }
            )
    return selected, skipped


def build_traces(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traces = []
    for item in selected:
        traces.append(
            {
                "id": item["trace_id"],
                "principal": SYNTHETIC_PRINCIPAL,
                "tenant_ids": [SYNTHETIC_TENANT],
                "source": f"metricflow:{item['source_file']}#{item['test_name']}",
                "release_allowed": True,
                "regression_case": "pass_to_pass",
                "semantic_ir": {
                    "metric": item["metric"],
                    "dimensions": item["dimensions"],
                    "time_range": SYNTHETIC_TIME_RANGE,
                    "grain": SYNTHETIC_GRAIN,
                    "limit": SYNTHETIC_LIMIT,
                },
                "sql": item["sql"],
                "expected_policy": {
                    "note": (
                        "native metricflow check_query SQL from tests_metricflow/integration/"
                        "test_cases; principal/tenancy/time_range/grain/limit are synthesized -- "
                        "metricflow is a single-tenant compiler with no such concepts"
                    ),
                    "source_test": item["description"],
                },
            }
        )
    return traces


def measure_lookup(semantic_models: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    measures: dict[str, dict[str, Any]] = {}
    for model in semantic_models:
        for measure in model.get("measures", []):
            measures.setdefault(str(measure["name"]), dict(measure))
    return measures


def resolve_measure_name(metric: dict[str, Any]) -> str | None:
    """Return the underlying measure name for a metric, if it references exactly one.

    ``type_params.measure`` is a bare string for most simple metrics but a
    ``{name, join_to_timespine}`` mapping for sub-daily simple metrics; derived
    and cumulative metric types may reference no single measure at all.
    """
    measure = (metric.get("type_params") or {}).get("measure")
    if isinstance(measure, dict):
        name = measure.get("name")
        return str(name) if name else None
    if isinstance(measure, str):
        return measure
    return None


def build_policy(
    manifest: dict[str, Any],
    selected: list[dict[str, Any]],
) -> dict[str, Any]:
    measures = measure_lookup(manifest["semantic_models"])
    sql_by_metric: dict[str, list[str]] = {}
    for item in selected:
        sql_by_metric.setdefault(item["metric"], []).append(item["sql"])

    metrics: dict[str, Any] = {}
    for metric in manifest["metrics"]:
        metric_name = str(metric["name"])
        measure_name = resolve_measure_name(metric) or metric_name
        measure = measures.get(measure_name)
        agg = str(measure.get("agg", "sum")) if measure else "sum"
        expr = str(measure.get("expr", measure_name)) if measure else measure_name
        observed = None
        for sql in sql_by_metric.get(metric_name, []):
            observed = extract_metric_expression_from_sql(sql, metric_name)
            if observed:
                break
        expression = observed or f"{agg}({expr})"
        columns = [] if expr.strip().isdigit() else [expr]
        metrics[metric_name] = {
            "expression": expression,
            "table": measure_name,
            "columns": columns,
            "allowed_roles": [SYNTHETIC_ROLE],
            "aliases": [],
            "grain": "row",
            "cost": 10,
        }

    dimensions: dict[str, Any] = {}
    for model in manifest["semantic_models"]:
        model_name = str(model.get("name", "unknown_model"))
        for dimension in model.get("dimensions", []):
            dim_name = str(dimension["name"])
            dimensions.setdefault(
                dim_name,
                {
                    "column": f"{model_name}.{dim_name}",
                    "allowed_roles": [SYNTHETIC_ROLE],
                    "sensitive": any(hint in dim_name.lower() for hint in SENSITIVE_NAME_HINTS),
                    "cost": 1,
                },
            )
    trace_dimension_tokens: set[str] = set()
    for item in selected:
        trace_dimension_tokens.update(item["dimensions"])
    for token in sorted(trace_dimension_tokens):
        dimensions.setdefault(
            token,
            {
                "column": f"query_token.{token}",
                "allowed_roles": [SYNTHETIC_ROLE],
                "sensitive": any(hint in token.lower() for hint in SENSITIVE_NAME_HINTS),
                "cost": 1,
            },
        )

    return {
        "version": "brownfield-metricflow-v1",
        "principals": {
            SYNTHETIC_PRINCIPAL: {
                "id": SYNTHETIC_PRINCIPAL,
                "role": SYNTHETIC_ROLE,
                "tenant_ids": [SYNTHETIC_TENANT],
            }
        },
        "roles": {
            SYNTHETIC_ROLE: {
                "allowed_metrics": sorted(metrics),
                "allowed_dimensions": sorted(dimensions),
                "allowed_time_ranges": [SYNTHETIC_TIME_RANGE],
                "max_rows": 100000,
                "max_cost": 100000,
                "aggregate_only": False,
            }
        },
        "metrics": metrics,
        "dimensions": dimensions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="path to the metricflow clone")
    parser.add_argument("--out", required=True, type=Path, help="path to examples/brownfield/metricflow")
    args = parser.parse_args()

    source_root: Path = args.source.resolve()
    out_root: Path = args.out.resolve()
    manifest_dir = source_root / "metricflow_semantics/test_helpers/semantic_manifest_yamls/simple_manifest"
    models_dir = manifest_dir / "semantic_models"
    metrics_path = manifest_dir / "metrics.yaml"
    itest_dir = source_root / "tests_metricflow/integration/test_cases"

    manifest = merge_semantic_manifest(models_dir, metrics_path)
    selected, skipped = select_traces(itest_dir, source_root)
    traces = build_traces(selected)
    policy = build_policy(manifest, selected)

    (out_root / "semantic_models.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    with (out_root / "traces.jsonl").open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")
    (out_root / "domain" / "policy.yaml").write_text(
        yaml.safe_dump(policy, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    report = {
        "semantic_models_merged": len(manifest["semantic_models"]),
        "metrics_merged": len(manifest["metrics"]),
        "itest_files_scanned": len(list(itest_dir.glob("itest_*.yaml"))),
        "traces_selected": len(selected),
        "traces_skipped": skipped,
        "metrics_in_policy": len(policy["metrics"]),
        "dimensions_in_policy": len(policy["dimensions"]),
    }
    report_text = json.dumps(report, indent=2, sort_keys=True)
    (out_root / "transform_report.json").write_text(report_text + "\n", encoding="utf-8")
    print(report_text)


if __name__ == "__main__":
    main()

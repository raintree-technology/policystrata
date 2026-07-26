#!/usr/bin/env python3
"""Deterministic brownfield transform for Canner/WrenAI's MDL row-level access control.

Reads Wren Engine's real MDL (Modeling Definition Language) test fixture
``core/wren-core-base/tests/data/mdl.json`` and produces:

  1. ``semantic_models.yml`` -- a mechanical mapping of MDL ``models[]`` to dbt-format
     ``semantic_models:``. MDL's `columns[]` (excluding relationship columns, which describe
     joins rather than selectable fields) become dbt `dimensions:`; column `type` values are
     carried through unmodified. This MDL fixture has no separate "measures"/"cubes" section, so
     the merged dbt YAML has an empty top-level `metrics:` list -- nothing is invented to fill
     that gap (see README.md for why, and how this differs from the metricflow/cube targets).
  2. ``domain/policy.yaml`` -- principals/roles/dimensions derived from the same MDL, scoped to
     the `customer` model, which is the one model in this fixture with a real
     `rowLevelAccessControls` entry.
  3. ``traces.jsonl`` -- one real-condition-consistent trace and one clearly-labeled hypothetical
     regression trace, built from the `customer` model's first row-level rule
     (``rule1``: ``requiredProperties: [{name: session_id, required: true}]``,
     ``condition: "c_custkey = @session_id"``). MDL's ``@session_property`` placeholder syntax is
     rendered the same way this fixture's own ``@session_id`` token is meant to be substituted at
     query time: with a literal session-property value, mirroring (not executing) the pattern
     shown in Wren Engine's own worked example,
     ``core/wren-core/wren-example/examples/row-level-access-control.rs`` (a *different*,
     tenant-scoped MDL manifest built via Rust `ManifestBuilder` calls, cited here only as
     corroborating evidence for how `@session_property` conditions are meant to be substituted --
     it is not parsed or transcribed by this script).

Usage:
    python brownfield-transform-wrenai.py --source <WrenAI-clone> --out <example-dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

MDL_PATH = "core/wren-core-base/tests/data/mdl.json"
TARGET_MODEL = "customer"
RULE_NAME = "rule1"
SYNTHETIC_PRINCIPAL = "wren_session_reader"
SYNTHETIC_TENANT = "4821"  # a synthetic session_id value, not a captured real one
CUSTOM_DOMAIN = "brownfield_wrenai"


def load_mdl(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relationship_column_types(mdl: dict[str, Any]) -> set[str]:
    """Model names that appear as a column `type` mean that column is a relationship, not a field."""
    return {str(model["name"]) for model in mdl.get("models", [])}


def mdl_to_dbt(mdl: dict[str, Any]) -> dict[str, Any]:
    model_names = relationship_column_types(mdl)
    semantic_models = []
    for model in mdl.get("models", []):
        dimensions = [
            {"name": str(column["name"]), "type": str(column.get("type", "unknown"))}
            for column in model.get("columns", [])
            if str(column.get("type")) not in model_names and "relationship" not in column
        ]
        table = model.get("tableReference", {}).get("table", model["name"])
        semantic_models.append(
            {
                "name": str(model["name"]),
                "model": f"ref('{table}')",
                "measures": [],
                "dimensions": dimensions,
            }
        )
    return {"semantic_models": semantic_models, "metrics": []}


def find_rule(mdl: dict[str, Any], model_name: str, rule_name: str) -> dict[str, Any]:
    for model in mdl.get("models", []):
        if model.get("name") != model_name:
            continue
        for rule in model.get("rowLevelAccessControls", []):
            if rule.get("name") == rule_name:
                return dict(rule)
    raise ValueError(f"rule {rule_name} not found on model {model_name}")


def condition_to_predicate(condition: str, session_property: str) -> str:
    """Render an MDL RLAC condition's @session_property token as PolicyStrata's
    :principal.tenant_id placeholder, unchanged otherwise."""
    return condition.replace(f"@{session_property}", ":principal.tenant_id")


def build_policy(mdl: dict[str, Any]) -> dict[str, Any]:
    dbt = mdl_to_dbt(mdl)
    customer_model = next(m for m in dbt["semantic_models"] if m["name"] == TARGET_MODEL)
    dimensions = {
        dim["name"]: {
            "column": f"{TARGET_MODEL}.{dim['name']}",
            "allowed_roles": ["session_reader"],
            "sensitive": False,
            "cost": 1,
        }
        for dim in customer_model["dimensions"]
    }
    return {
        "version": "brownfield-wrenai-v1",
        "principals": {
            SYNTHETIC_PRINCIPAL: {
                "id": SYNTHETIC_PRINCIPAL,
                "role": "session_reader",
                "tenant_ids": [SYNTHETIC_TENANT],
            }
        },
        "roles": {
            "session_reader": {
                "allowed_metrics": [],
                "allowed_dimensions": sorted(dimensions),
                "allowed_time_ranges": [],
                "max_rows": 1000,
                "max_cost": 1000,
                "aggregate_only": False,
            }
        },
        "metrics": {},
        "dimensions": dimensions,
    }


def build_traces(rule: dict[str, Any], predicate_sql: str) -> list[dict[str, Any]]:
    required_property = rule["requiredProperties"][0]["name"]
    clean_sql = f"select c_custkey, c_name from customer where {predicate_sql}"
    unfiltered_sql = "select c_custkey, c_name from customer"
    return [
        {
            "id": "wren_customer_rule1_consistent",
            "principal": SYNTHETIC_PRINCIPAL,
            "tenant_ids": [SYNTHETIC_TENANT],
            "source": f"wrenai:{MDL_PATH}#models[customer].rowLevelAccessControls[{RULE_NAME}]",
            "release_allowed": True,
            "regression_case": "pass_to_pass",
            "sql": clean_sql,
            "expected_policy": {
                "note": (
                    f"native MDL rule '{RULE_NAME}' on model '{TARGET_MODEL}': "
                    f"requiredProperties=[{required_property} (required)], "
                    f"condition='{rule['condition']}'. SQL renders the condition with the session "
                    "property substituted by a literal value, the same way wren-core's own "
                    "row-level-access-control.rs example substitutes @session_tenant_id."
                ),
            },
        },
        {
            "id": "wren_customer_rule1_bypassed_regression",
            "principal": SYNTHETIC_PRINCIPAL,
            "tenant_ids": [SYNTHETIC_TENANT],
            "source": f"wrenai:{MDL_PATH}#models[customer].rowLevelAccessControls[{RULE_NAME}]",
            "release_allowed": True,
            "regression_case": "fail_to_pass",
            "sql": unfiltered_sql,
            "expected_policy": {
                "note": (
                    f"synthesized regression case, NOT observed wren-core output: rule "
                    f"'{RULE_NAME}' marks '{required_property}' required=true, meaning wren's "
                    "engine should always apply this condition when planning a query against "
                    "'customer'. This trace represents the query PolicyStrata's SQL-trace "
                    "tenant-scope check must catch if a required RLAC rule were ever silently "
                    "not applied -- a defense-in-depth demonstration, not a claim about observed "
                    "wren-core behavior (we did not execute wren-core's planner)."
                ),
            },
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="path to the WrenAI clone")
    parser.add_argument("--out", required=True, type=Path, help="path to examples/brownfield/WrenAI")
    args = parser.parse_args()

    source_root: Path = args.source.resolve()
    out_root: Path = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "domain").mkdir(parents=True, exist_ok=True)
    mdl = load_mdl(source_root / MDL_PATH)

    rule = find_rule(mdl, TARGET_MODEL, RULE_NAME)
    session_property = rule["requiredProperties"][0]["name"]
    predicate = condition_to_predicate(rule["condition"], session_property)
    predicate_sql = predicate.replace(":principal.tenant_id", SYNTHETIC_TENANT)

    dbt = mdl_to_dbt(mdl)
    policy = build_policy(mdl)
    traces = build_traces(rule, predicate_sql)

    (out_root / "semantic_models.yml").write_text(
        yaml.safe_dump(dbt, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    (out_root / "domain" / "policy.yaml").write_text(
        yaml.safe_dump(policy, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    with (out_root / "traces.jsonl").open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")

    report = {
        "models_merged": len(dbt["semantic_models"]),
        "target_model": TARGET_MODEL,
        "rule": RULE_NAME,
        "native_condition": rule["condition"],
        "canonical_predicate": predicate,
        "traces_built": len(traces),
    }
    report_text = json.dumps(report, indent=2, sort_keys=True)
    (out_root / "transform_report.json").write_text(report_text + "\n", encoding="utf-8")
    print(report_text)


if __name__ == "__main__":
    main()

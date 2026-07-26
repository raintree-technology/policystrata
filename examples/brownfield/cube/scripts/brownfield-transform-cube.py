#!/usr/bin/env python3
"""Deterministic brownfield transform for cube-js/cube's intentionally-broken ACL fixtures.

cube ships three schema-compiler unit-test fixtures that define the *same* `orders` cube with
the *same* dimensions/measures/joins, differing only in the `admin` group's
`accessPolicy[].rowLevel.filters` member reference:

  * ``orders_big.yml``            -- valid: filters reference ``status`` / ``{CUBE}.created_at``
    / ``{CUBE}.completed_at``, all real dimensions declared on ``orders`` itself.
  * ``orders_incorrect_acl.yml``  -- broken: the first filter references
    ``{CUBE}.order_users.name``, a cross-cube joined path. cube's own compiler rejects this at
    build time (packages/cubejs-schema-compiler/test/unit/schema.test.ts, "throw errors for
    incorrect policy members with paths": *"Paths aren't allowed in the accessPolicy policy but
    'order_users.name' provided as a filter member reference for orders"*).
  * ``orders_nonexist_acl.yml``   -- broken: the first filter references
    ``{CUBE}.other.path.created_at``, which resolves to nothing. cube's compiler also rejects
    this (same test file, "throw errors for nonexistent policy members with paths": *"orders.other
    cannot be resolved. There's no such member or cube"*).

Because cube itself fails closed on the two broken fixtures (confirmed by its own test suite --
we do not execute cube's compiler, we only read the assertions in schema.test.ts as corroborating
evidence), there is no real SQL cube ever produced for them to capture as a trace. This script
does NOT claim otherwise. Instead it:

  1. Mechanically re-derives the *same* member-resolution verdict cube's compiler reaches (a
     small, deterministic path-resolution check against the cube's own declared dimensions and
     joins -- not a reimplementation of cube's SQL generation, just membership resolution).
  2. Transforms only the valid fixture (``orders_big.yml``) into a dbt-format
     ``semantic_models.yml`` for PolicyStrata's dbt adapter (native field values, cube's
     `cubes:`/`measures:`/`dimensions:` vocabulary mapped to dbt's `semantic_models:`/
     `measures:`/`dimensions:` vocabulary).
  3. Synthesizes one clearly-labeled *regression-style* SQL trace per fixture representing "an
     admin-scoped query against orders, as PolicyStrata's independent SQL-trace layer would see
     it if this accessPolicy config's row-level predicate were ever actually applied (or, for the
     two broken fixtures, silently NOT applied)". The predicate text itself is composed only from
     the resolved, real filter metadata (member/operator/values) of orders_big.yml -- nothing is
     invented beyond a literal SQL `=` rendering of an `equals` filter.

Usage:
    python brownfield-transform-cube.py --source <cube-clone> --out <example-dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

CUBE_NAME = "orders"
FIXTURE_FILES = {
    "correct": "orders_big.yml",
    "incorrect_acl": "orders_incorrect_acl.yml",
    "nonexist_acl": "orders_nonexist_acl.yml",
}
FIXTURE_DIR = "packages/cubejs-schema-compiler/test/unit/fixtures"
CUBE_DIMENSION_TYPE_TO_DBT = {"time": "time"}
CUBE_MEASURE_TYPE_TO_AGG = {
    "count": "count",
    "count_distinct": "count_distinct",
    "sum": "sum",
    "avg": "average",
    "min": "min",
    "max": "max",
}
SYNTHETIC_ADMIN_PRINCIPAL = "cube_admin_reviewer"
SYNTHETIC_COMMON_PRINCIPAL = "cube_common_viewer"
SYNTHETIC_TENANT = "cube_brownfield_scope"


def load_cube(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cubes = raw.get("cubes") or []
    if not cubes:
        raise ValueError(f"{path}: expected a top-level 'cubes:' list")
    return dict(cubes[0])


def local_dimension_names(cube: dict[str, Any]) -> set[str]:
    return {str(dim["name"]) for dim in cube.get("dimensions", [])}


def local_measure_names(cube: dict[str, Any]) -> set[str]:
    return {str(measure["name"]) for measure in cube.get("measures", [])}


def join_names(cube: dict[str, Any]) -> set[str]:
    return {str(join["name"]) for join in cube.get("joins", [])}


def resolve_filter_member(cube: dict[str, Any], raw_member: str) -> dict[str, Any]:
    """Re-derive cube's own member-resolution verdict for one accessPolicy filter member.

    Mirrors (does not execute) the two real compiler errors cube's own test suite asserts for
    these exact fixtures: a same-cube name resolves; a joined-cube path is explicitly rejected
    ("Paths aren't allowed..."); an unknown path segment is rejected ("... cannot be resolved.
    There's no such member or cube").
    """
    member = raw_member.replace("{CUBE}.", "").strip()
    parts = member.split(".")
    locals_ = local_dimension_names(cube) | local_measure_names(cube)
    if len(parts) == 1:
        if parts[0] in locals_:
            return {"member": raw_member, "resolved": True, "local_name": parts[0], "reason": None}
        return {
            "member": raw_member,
            "resolved": False,
            "local_name": None,
            "reason": f"'{parts[0]}' is not a declared dimension or measure on cube '{cube['name']}'",
        }
    first = parts[0]
    if first in join_names(cube):
        return {
            "member": raw_member,
            "resolved": False,
            "local_name": None,
            "reason": (
                f"Paths aren't allowed in the accessPolicy policy but '{member}' provided as a "
                f"filter member reference for {cube['name']} "
                "(matches cube's own compiler error in schema.test.ts)"
            ),
        }
    return {
        "member": raw_member,
        "resolved": False,
        "local_name": None,
        "reason": (
            f"{cube['name']}.{first} cannot be resolved. There's no such member or cube "
            "(matches cube's own compiler error in schema.test.ts)"
        ),
    }


def admin_group(cube: dict[str, Any]) -> dict[str, Any]:
    for group in cube.get("accessPolicy", []):
        if group.get("group") == "admin":
            return group
    raise ValueError("expected an 'admin' accessPolicy group")


def primary_filter_predicate(cube: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Resolve the admin group's first (non-nested) rowLevel filter to a SQL predicate.

    Only handles the literal, deterministic case present in these fixtures: a single top-level
    ``equals`` filter with one value. The nested ``or:``/``and:`` date-range blocks that follow it
    are identical noise across all three fixtures and are not needed to distinguish them, so they
    are intentionally not translated.
    """
    group = admin_group(cube)
    filters = (group.get("rowLevel") or {}).get("filters") or []
    first = filters[0]
    resolution = resolve_filter_member(cube, str(first["member"]))
    if not resolution["resolved"]:
        return resolution, None
    operator = str(first.get("operator"))
    values = first.get("values") or []
    if operator != "equals" or len(values) != 1:
        return resolution, None
    predicate = f"{CUBE_NAME}.{resolution['local_name']} = '{values[0]}'"
    return resolution, predicate


def cube_to_dbt_semantic_model(cube: dict[str, Any]) -> dict[str, Any]:
    dimensions = [
        {
            "name": str(dim["name"]),
            "type": CUBE_DIMENSION_TYPE_TO_DBT.get(str(dim.get("type")), "categorical"),
        }
        for dim in cube.get("dimensions", [])
    ]
    measures = [
        {
            "name": str(measure["name"]),
            "agg": CUBE_MEASURE_TYPE_TO_AGG.get(str(measure.get("type")), str(measure.get("type"))),
            "expr": str(measure.get("sql", measure["name"])),
        }
        for measure in cube.get("measures", [])
    ]
    metrics = [
        {"name": measure["name"], "type": "simple", "type_params": {"measure": measure["name"]}}
        for measure in measures
    ]
    model = {
        "name": str(cube["name"]),
        "model": f"ref('{cube.get('sql_table', cube['name'])}')",
        "measures": measures,
        "dimensions": dimensions,
    }
    return {"semantic_models": [model], "metrics": metrics}


def build_trace(
    trace_id: str,
    principal: str,
    sql: str,
    predicate_included: bool,
    regression_case: str,
    provenance_note: str,
) -> dict[str, Any]:
    return {
        "id": trace_id,
        "principal": principal,
        "tenant_ids": [SYNTHETIC_TENANT],
        "source": f"cube:{FIXTURE_DIR}/{FIXTURE_FILES.get(trace_id.split('__')[-1], 'orders_big.yml')}",
        "release_allowed": True,
        "regression_case": regression_case,
        "semantic_ir": {
            "metric": "count",
            "dimensions": ["status"],
            "time_range": "all_time",
            "grain": "day",
            "limit": 1000,
        },
        "sql": sql,
        "expected_policy": {
            "note": provenance_note,
            "row_level_predicate_included": predicate_included,
        },
    }


def build_policy(cube: dict[str, Any]) -> dict[str, Any]:
    dims = {
        str(dim["name"]): {
            "column": f"{cube['name']}.{dim['name']}",
            "allowed_roles": ["admin_group", "common_group"],
            "sensitive": False,
            "cost": 1,
        }
        for dim in cube.get("dimensions", [])
    }
    metrics = {
        "count": {
            "expression": "count(id)",
            "table": cube["name"],
            "columns": ["id"],
            "allowed_roles": ["admin_group", "common_group"],
            "aliases": [],
            "grain": "row",
            "cost": 5,
        }
    }
    return {
        "version": "brownfield-cube-v1",
        "principals": {
            SYNTHETIC_ADMIN_PRINCIPAL: {
                "id": SYNTHETIC_ADMIN_PRINCIPAL,
                "role": "admin_group",
                "tenant_ids": [SYNTHETIC_TENANT],
            },
            SYNTHETIC_COMMON_PRINCIPAL: {
                "id": SYNTHETIC_COMMON_PRINCIPAL,
                "role": "common_group",
                "tenant_ids": [SYNTHETIC_TENANT],
            },
        },
        "roles": {
            "admin_group": {
                "allowed_metrics": ["count"],
                "allowed_dimensions": ["status"],
                "allowed_time_ranges": ["all_time"],
                "max_rows": 5000,
                "max_cost": 5000,
                "aggregate_only": False,
            },
            "common_group": {
                "allowed_metrics": ["count"],
                "allowed_dimensions": ["status"],
                "allowed_time_ranges": ["all_time"],
                "max_rows": 5000,
                "max_cost": 5000,
                "aggregate_only": False,
            },
        },
        "metrics": metrics,
        "dimensions": dims,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="path to the cube clone")
    parser.add_argument("--out", required=True, type=Path, help="path to examples/brownfield/cube")
    args = parser.parse_args()

    source_root: Path = args.source.resolve()
    out_root: Path = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "domain").mkdir(parents=True, exist_ok=True)
    fixtures_dir = source_root / FIXTURE_DIR

    cubes = {key: load_cube(fixtures_dir / name) for key, name in FIXTURE_FILES.items()}
    resolutions = {key: primary_filter_predicate(cube) for key, cube in cubes.items()}

    _, correct_predicate = resolutions["correct"]
    if correct_predicate is None:
        raise RuntimeError("expected the valid fixture's primary filter to resolve to a SQL predicate")

    select_prefix = f"select count(id) as count, status from {CUBE_NAME}"
    unfiltered_sql = f"{select_prefix} group by status"
    clean_sql = f"{select_prefix} where {correct_predicate} group by status"

    traces = [
        build_trace(
            "cube_admin_query__correct",
            SYNTHETIC_ADMIN_PRINCIPAL,
            clean_sql,
            True,
            "pass_to_pass",
            (
                "orders_big.yml: admin group's first rowLevel filter (member: status, operator: "
                "equals, values: [completed]) resolves to a real local dimension on 'orders'; "
                "SQL composed from that resolved, real filter metadata."
            ),
        )
    ]
    for key in ("incorrect_acl", "nonexist_acl"):
        resolution, _ = resolutions[key]
        traces.append(
            build_trace(
                f"cube_admin_query__{key}",
                SYNTHETIC_ADMIN_PRINCIPAL,
                unfiltered_sql,
                False,
                "fail_to_pass",
                (
                    f"{FIXTURE_FILES[key]}: admin group's first rowLevel filter member "
                    f"'{resolution['member']}' does not resolve to a local member on 'orders' "
                    f"({resolution['reason']}). cube's own compiler rejects this config at build "
                    "time (packages/cubejs-schema-compiler/test/unit/schema.test.ts), so cube "
                    "itself never produces SQL for it. This trace is a synthesized regression "
                    "case, NOT captured cube output: it represents the query PolicyStrata's "
                    "independent SQL-trace tenant/row-level-scope check must still catch if this "
                    "kind of unresolvable row-level predicate were ever silently dropped instead "
                    "of raising a hard compile error -- demonstrating the scanner as a "
                    "defense-in-depth layer, not a report of observed cube runtime behavior."
                ),
            )
        )
    traces.append(
        build_trace(
            "cube_common_query__correct",
            SYNTHETIC_COMMON_PRINCIPAL,
            unfiltered_sql,
            False,
            "allow_to_allow",
            (
                "orders_big.yml: 'common' group's rowLevel is `allowAll: true` -- no filter "
                "predicate is expected."
            ),
        )
    )

    manifest = cube_to_dbt_semantic_model(cubes["correct"])
    policy = build_policy(cubes["correct"])

    (out_root / "semantic_models.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    (out_root / "domain" / "policy.yaml").write_text(
        yaml.safe_dump(policy, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    with (out_root / "traces.jsonl").open("w", encoding="utf-8") as handle:
        for trace in traces:
            if trace["principal"] == SYNTHETIC_ADMIN_PRINCIPAL:
                handle.write(json.dumps(trace, sort_keys=True) + "\n")
    with (out_root / "traces_clean.jsonl").open("w", encoding="utf-8") as handle:
        for trace in traces:
            if trace["principal"] == SYNTHETIC_COMMON_PRINCIPAL:
                handle.write(json.dumps(trace, sort_keys=True) + "\n")

    report = {
        "canonical_row_level_predicate": correct_predicate,
        "fixture_resolutions": {
            key: {"member": res["member"], "resolved": res["resolved"], "reason": res["reason"]}
            for key, (res, _pred) in resolutions.items()
        },
        "traces_main_config": sum(1 for t in traces if t["principal"] == SYNTHETIC_ADMIN_PRINCIPAL),
        "traces_clean_config": sum(1 for t in traces if t["principal"] == SYNTHETIC_COMMON_PRINCIPAL),
    }
    report_text = json.dumps(report, indent=2, sort_keys=True)
    (out_root / "transform_report.json").write_text(report_text + "\n", encoding="utf-8")
    print(report_text)


if __name__ == "__main__":
    main()

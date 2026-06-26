from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from policystrata.compiler import compile_query
from policystrata.domain import BUILTIN_DOMAIN, domain_root, load_policy
from policystrata.models import SemanticQuery
from policystrata.policy import PolicyOracle

try:
    from importlib.resources.abc import Traversable
except ImportError:  # Python 3.10 exposes Traversable from importlib.abc.
    from importlib.abc import Traversable

SCANNER_EXAMPLES = ("basic", "postgres_dbt")
SCANNER_EXAMPLE_ROOT = "scanner_examples"

CONFIG_TEMPLATE = """version: 1
domain: {domain}
domain_path: domain
output: scan-out
sql_traces:
  files:
    - traces.example.jsonl
  required: true
tenancy:
  canonical_predicates:
    - "{tenant_predicate}"
  tenant_columns:
    - {tenant_column}
fuzz:
  enabled: false
gate:
  fail_on_high_confidence: true
  required_inputs:
    - sql_traces
"""


@dataclass(frozen=True)
class BasicScanTemplate:
    trace_id: str
    principal: str
    tenant_predicate: str
    tenant_column: str
    tenant_scope: str
    semantic_query: SemanticQuery


BASIC_SCAN_TEMPLATES: dict[str, BasicScanTemplate] = {
    "support_saas": BasicScanTemplate(
        trace_id="example_ticket_count",
        principal="acme_analyst",
        tenant_predicate="accounts.tenant_id = :principal.tenant_id",
        tenant_column="accounts.tenant_id",
        tenant_scope="accounts.tenant_id scoped to principal tenant_ids",
        semantic_query=SemanticQuery(
            metric="ticket_count",
            dimensions=["region"],
            time_range="last_month",
            grain="month",
            limit=100,
        ),
    ),
    "finance_saas": BasicScanTemplate(
        trace_id="example_aum_by_region",
        principal="north_advisor",
        tenant_predicate="households.firm_id = :principal.tenant_id",
        tenant_column="households.firm_id",
        tenant_scope="households.firm_id scoped to principal tenant_ids",
        semantic_query=SemanticQuery(
            metric="aum",
            dimensions=["advisor_region"],
            time_range="last_month",
            grain="month",
            limit=100,
        ),
    ),
    "analytics_clickhouse": BasicScanTemplate(
        trace_id="example_active_users_by_country",
        principal="acme_product_viewer",
        tenant_predicate="events.project_id = :principal.tenant_id",
        tenant_column="events.project_id",
        tenant_scope="events.project_id scoped to principal project_ids",
        semantic_query=SemanticQuery(
            metric="active_users",
            dimensions=["country"],
            time_range="last_7_days",
            grain="day",
            limit=100,
        ),
    ),
}


def init_scan_project(
    destination: Path,
    example: str = "basic",
    source_domain: str = BUILTIN_DOMAIN,
    force: bool = False,
) -> dict[str, Any]:
    if example == "basic":
        return init_basic_scan_project(destination, source_domain, force)
    if example == "postgres_dbt":
        return init_packaged_scan_example(destination, example, force)
    raise ValueError(f"unknown scanner example: {example}")


def init_basic_scan_project(
    destination: Path,
    source_domain: str = BUILTIN_DOMAIN,
    force: bool = False,
) -> dict[str, Any]:
    destination = destination.resolve()
    domain_dir = destination / "domain"
    files = {
        "config": destination / "policystrata.yaml",
        "policy": domain_dir / "policy.yaml",
        "surfaces": domain_dir / "surfaces.yaml",
        "traces": destination / "traces.example.jsonl",
    }
    if not force:
        existing = [str(path) for path in files.values() if path.exists()]
        if existing:
            raise FileExistsError(f"init-scan target already has files: {', '.join(existing)}")

    domain_dir.mkdir(parents=True, exist_ok=True)
    source = domain_root(source_domain)
    try:
        template = BASIC_SCAN_TEMPLATES[source_domain]
    except KeyError as exc:
        raise ValueError(
            f"basic scanner scaffold has no template for source domain: {source_domain}"
        ) from exc
    files["config"].write_text(
        CONFIG_TEMPLATE.format(
            domain=source_domain,
            tenant_predicate=template.tenant_predicate,
            tenant_column=template.tenant_column,
        ),
        encoding="utf-8",
    )
    files["policy"].write_text(source.joinpath("policy.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    files["surfaces"].write_text(
        source.joinpath("surfaces.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    files["traces"].write_text(
        json.dumps(build_basic_scan_trace(source_domain, template), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    command = f"policystrata scan --config {files['config']}"
    return {
        "example": "basic",
        "out": str(destination),
        "files": {name: str(path) for name, path in files.items()},
        "command": command,
    }


def build_basic_scan_trace(source_domain: str, template: BasicScanTemplate) -> dict[str, Any]:
    policy = load_policy(source_domain)
    principal = policy.principals.get(template.principal)
    if principal is None:
        raise ValueError(
            f"basic scanner scaffold template references unknown principal: {template.principal}"
        )
    decision = PolicyOracle(policy).authorize(template.principal, template.semantic_query)
    if not decision.allowed:
        reasons = "; ".join(decision.reasons) or "authorization denied"
        raise ValueError(f"basic scanner scaffold template is not policy-allowed: {reasons}")
    compiled = compile_query(policy, principal, template.semantic_query, domain=source_domain)
    if template.tenant_column not in compiled.sql:
        raise ValueError(
            f"basic scanner scaffold SQL is missing configured tenant column: {template.tenant_column}"
        )
    return {
        "id": template.trace_id,
        "principal": template.principal,
        "tenant_ids": list(principal.tenant_ids),
        "source": "init_scan_example",
        "timestamp": "2026-06-24T12:00:00Z",
        "release_allowed": True,
        "regression_case": "pass_to_pass",
        "expected_policy": {
            "authorization": "allowed",
            "tenant_scope": template.tenant_scope,
        },
        "semantic_ir": template.semantic_query.model_dump(),
        "sql": compiled.sql,
    }


def init_packaged_scan_example(destination: Path, example: str, force: bool = False) -> dict[str, Any]:
    destination = destination.resolve()
    template = resources.files("policystrata").joinpath(SCANNER_EXAMPLE_ROOT).joinpath(example)
    if not template.is_dir():
        raise ValueError(f"scanner example is not packaged: {example}")
    if not force and destination.exists() and any(destination.iterdir()):
        existing = ", ".join(str(path) for path in sorted(destination.iterdir()))
        raise FileExistsError(f"init-scan target already has files: {existing}")

    destination.mkdir(parents=True, exist_ok=True)
    copy_resource_tree(template, destination)
    copy_resource_tree(domain_root(BUILTIN_DOMAIN), destination / "domain")

    files = {
        "config": destination / "policystrata.yaml",
        "clean_config": destination / "policystrata_clean.yaml",
        "real_db_config": destination / "policystrata_real_db_clean.yaml",
        "dbt": destination / "semantic_models.yml",
        "traces": destination / "traces.jsonl",
        "clean_traces": destination / "traces_clean.jsonl",
        "real_db_traces": destination / "traces_real_db_clean.jsonl",
        "policy": destination / "domain" / "policy.yaml",
        "surfaces": destination / "domain" / "surfaces.yaml",
        "schema": destination / "domain" / "schema.sql",
        "seed": destination / "domain" / "seed.sql",
    }
    command = f"policystrata scan --config {files['config']}"
    return {
        "example": example,
        "out": str(destination),
        "files": {name: str(path) for name, path in files.items()},
        "command": command,
        "commands": {
            "policy_drift_failure_demo": command,
            "clean_smoke_scan": f"policystrata scan --config {files['clean_config']}",
            "db_readiness_scan": f"policystrata scan --config {files['real_db_config']}",
            "db_readiness_doctor": (
                f"policystrata doctor --config {files['real_db_config']} --strict"
            ),
        },
        "notes": [
            (
                "doctor audits only the selected config; use policystrata_real_db_clean.yaml "
                "for DB/RLS readiness checks."
            ),
            (
                "policystrata_clean.yaml is a minimal passing smoke config and does not "
                "claim dbt or database wiring."
            ),
        ],
    }


def copy_resource_tree(source: Traversable, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            copy_resource_tree(child, target)
        else:
            target.write_bytes(child.read_bytes())

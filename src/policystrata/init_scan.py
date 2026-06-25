from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from policystrata.domain import BUILTIN_DOMAIN, domain_root

CONFIG_TEMPLATE = """version: 1
domain: custom
domain_path: domain
output: scan-out
sql_traces:
  files:
    - traces.example.jsonl
  required: true
tenancy:
  canonical_predicates:
    - "accounts.tenant_id = :principal.tenant_id"
  tenant_columns:
    - accounts.tenant_id
fuzz:
  enabled: false
gate:
  fail_on_high_confidence: true
  required_inputs:
    - sql_traces
"""

EXAMPLE_TRACE = {
    "id": "example_ticket_count",
    "principal": "acme_analyst",
    "tenant_ids": ["acme"],
    "source": "init_scan_example",
    "timestamp": "2026-06-24T12:00:00Z",
    "release_allowed": True,
    "regression_case": "pass_to_pass",
    "expected_policy": {
        "authorization": "allowed",
        "tenant_scope": "accounts.tenant_id scoped to principal tenant_ids",
    },
    "semantic_ir": {
        "metric": "ticket_count",
        "dimensions": ["region"],
        "time_range": "last_month",
        "grain": "month",
        "limit": 100,
    },
    "sql": (
        "select count(distinct support_tickets.id) as value, accounts.region as region "
        "from accounts "
        "left join support_tickets on support_tickets.account_id = accounts.id "
        "where accounts.tenant_id in ('acme') "
        "group by accounts.region "
        "limit 100"
    ),
}


def init_scan_project(
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
    files["config"].write_text(CONFIG_TEMPLATE, encoding="utf-8")
    files["policy"].write_text(source.joinpath("policy.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    files["surfaces"].write_text(
        source.joinpath("surfaces.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    files["traces"].write_text(json.dumps(EXAMPLE_TRACE, sort_keys=True) + "\n", encoding="utf-8")

    command = f"policystrata scan --config {files['config']}"
    return {
        "out": str(destination),
        "files": {name: str(path) for name, path in files.items()},
        "command": command,
    }

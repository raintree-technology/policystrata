from __future__ import annotations

import json
import random
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from policystrata.database import assert_read_only_sql
from policystrata.models import Policy, SemanticQuery
from policystrata.policy import PolicyOracle
from policystrata.scan_models import ImportedTrace, MutantStatus

NON_SQL_RECORD_TYPES = {"agent_session", "tool_execution", "mutation"}


def resolve_scan_input_paths(config_dir: Path, values: list[str], input_name: str) -> list[Path]:
    paths: list[Path] = []
    for value in values:
        raw_path = Path(value)
        if raw_path.is_absolute() or ".." in raw_path.parts:
            raise ValueError(f"{input_name} path must stay under the config directory: {value}")
        candidate = (config_dir / raw_path).resolve()
        try:
            candidate.relative_to(config_dir.resolve())
        except ValueError as exc:
            raise ValueError(f"{input_name} path escapes config directory: {value}") from exc
        paths.append(candidate)
    return paths


def resolve_optional_config_path(config_dir: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    raw_path = Path(value)
    if raw_path.is_absolute():
        return raw_path
    return (config_dir / raw_path).resolve()


def load_imported_traces(paths: list[Path]) -> list[ImportedTrace]:
    traces: list[ImportedTrace] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    normalized = normalize_imported_trace_record(raw)
                    if normalized is None:
                        continue
                    trace = ImportedTrace.model_validate(normalized)
                    assert_read_only_sql(trace.sql)
                except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                    raise ValueError(f"invalid imported trace {path}:{line_number}: {exc}") from exc
                traces.append(trace)
    return traces


def normalize_imported_trace_record(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        raise ValueError("trace record must be a JSON object")
    record_type = raw.get("record_type")
    if record_type in NON_SQL_RECORD_TYPES and "sql" not in raw:
        return None
    normalized = dict(raw)
    query = raw.get("query")
    if "sql" not in normalized and isinstance(query, dict) and isinstance(query.get("sql"), str):
        normalized["sql"] = query["sql"]
    if "id" not in normalized and isinstance(raw.get("trace_id"), str):
        normalized["id"] = raw["trace_id"]
    return normalized


def fuzz_imported_trace(
    trace: ImportedTrace,
    policy: Policy,
    seed: int,
    max_cases: int,
    tenant_columns: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    if max_cases == 0:
        return []
    rng = random.Random(f"{seed}:{trace.id}")
    candidates = [
        remove_tenant_predicate(trace, tenant_columns),
        mutate_join_path(trace),
        mutate_time_bounds(trace),
        add_sensitive_dimension(trace, policy, rng),
        replace_metric_with_denied_alias(trace, policy, rng),
        expand_limit_beyond_role(trace, policy),
        release_unauthorized_trace(trace, policy),
    ]
    return [candidate for candidate in candidates if candidate is not None][:max_cases]


def remove_tenant_predicate(
    trace: ImportedTrace,
    tenant_columns: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    columns = tenant_columns or ("accounts.tenant_id", "households.firm_id", "tenant_id", "firm_id")
    lowered = trace.sql.lower()
    if not any(column.lower() in lowered for column in columns):
        return {
            "mutation": "tenant_predicate_removed",
            "status": MutantStatus.EQUIVALENT,
            "reason": "trace SQL had no observable configured tenant predicate to remove",
        }
    mutated_sql = trace.sql
    for column in columns:
        mutated_sql = replace_tenant_column_with_legacy(mutated_sql, column)
    if mutated_sql == trace.sql:
        return {
            "mutation": "tenant_predicate_removed",
            "status": MutantStatus.EQUIVALENT,
            "reason": "tenant predicate was present but not in a replaceable canonical form",
        }
    return {
        "mutation": "tenant_predicate_removed",
        "status": MutantStatus.KILLED,
        "sql": mutated_sql,
        "reason": "tenant-scope predicate can be changed away from the configured policy column",
    }


def replace_tenant_column_with_legacy(sql: str, column: str) -> str:
    if "." not in column:
        replacement = f"legacy_{column}"
    else:
        table, name = column.rsplit(".", 1)
        replacement = f"{table}.legacy_{name}"
    pattern = rf"(?<![A-Za-z0-9_.]){re.escape(column)}(?![A-Za-z0-9_])"
    return re.sub(pattern, replacement, sql)


def mutate_join_path(trace: ImportedTrace) -> dict[str, Any]:
    lowered = trace.sql.lower()
    if "support_tickets" not in lowered or "ticket_events" in lowered:
        return {
            "mutation": "join_path_fanout",
            "status": MutantStatus.EQUIVALENT,
            "reason": "trace SQL has no recognized support-ticket join path to fan out",
        }
    mutated_sql = trace.sql.replace(
        " group by ",
        " left join ticket_events on ticket_events.ticket_id = support_tickets.id group by ",
        1,
    )
    if mutated_sql == trace.sql:
        return {
            "mutation": "join_path_fanout",
            "status": MutantStatus.STILLBORN,
            "reason": "trace SQL did not expose a stable group-by insertion point",
        }
    return {
        "mutation": "join_path_fanout",
        "status": MutantStatus.KILLED,
        "sql": mutated_sql,
        "reason": "join-path mutation introduces a potential aggregate fanout",
    }


def mutate_time_bounds(trace: ImportedTrace) -> dict[str, Any]:
    replacements = {
        "date '2026-05-01'": "date '2026-04-27'",
        "date '2026-06-01'": "date '2026-05-25'",
    }
    mutated_sql = trace.sql
    for source, replacement in replacements.items():
        mutated_sql = mutated_sql.replace(source, replacement)
    if mutated_sql == trace.sql:
        return {
            "mutation": "time_bounds_shifted",
            "status": MutantStatus.EQUIVALENT,
            "reason": "trace SQL has no recognized deterministic date bounds",
        }
    return {
        "mutation": "time_bounds_shifted",
        "status": MutantStatus.KILLED,
        "sql": mutated_sql,
        "reason": "time-bound mutation changes calendar/fiscal semantics",
    }


def add_sensitive_dimension(
    trace: ImportedTrace,
    policy: Policy,
    rng: random.Random,
) -> dict[str, Any] | None:
    if trace.semantic_ir is None:
        return {
            "mutation": "sensitive_dimension_added",
            "status": MutantStatus.STILLBORN,
            "reason": "trace has no semantic IR to mutate",
        }
    sensitive = [
        name
        for name, dimension in sorted(policy.dimensions.items())
        if dimension.sensitive and name not in trace.semantic_ir.dimensions
    ]
    if not sensitive:
        return {
            "mutation": "sensitive_dimension_added",
            "status": MutantStatus.EQUIVALENT,
            "reason": "policy has no additional sensitive dimensions for this trace",
        }
    dimension = rng.choice(sensitive)
    mutated = trace.semantic_ir.model_copy(
        update={"dimensions": [*trace.semantic_ir.dimensions, dimension]},
    )
    oracle = PolicyOracle(policy)
    decision = oracle.authorize(trace.principal, mutated)
    return {
        "mutation": "sensitive_dimension_added",
        "status": MutantStatus.KILLED if not decision.allowed else MutantStatus.SURVIVED,
        "semantic_ir": mutated,
        "reason": "; ".join(decision.reasons) or "mutated sensitive dimension remained authorized",
    }


def replace_metric_with_denied_alias(
    trace: ImportedTrace,
    policy: Policy,
    rng: random.Random,
) -> dict[str, Any] | None:
    if trace.semantic_ir is None:
        return {
            "mutation": "metric_alias_replaced",
            "status": MutantStatus.STILLBORN,
            "reason": "trace has no semantic IR to mutate",
    }
    principal = policy.principals.get(trace.principal)
    role_name = principal.role if principal is not None else None
    role = policy.roles.get(role_name) if role_name is not None else None
    denied_aliases = []
    if role is not None and role_name is not None:
        denied_aliases = [
            alias
            for name, metric in sorted(policy.metrics.items())
            for alias in metric.aliases
            if name not in role.allowed_metrics or role_name not in metric.allowed_roles
        ]
    if not denied_aliases:
        return {
            "mutation": "metric_alias_replaced",
            "status": MutantStatus.EQUIVALENT,
            "reason": "no denied metric alias is available for the trace principal",
        }
    mutated = trace.semantic_ir.model_copy(update={"metric": rng.choice(denied_aliases)})
    oracle = PolicyOracle(policy)
    decision = oracle.authorize(trace.principal, mutated)
    return {
        "mutation": "metric_alias_replaced",
        "status": MutantStatus.KILLED if not decision.allowed else MutantStatus.SURVIVED,
        "semantic_ir": mutated,
        "reason": "; ".join(decision.reasons) or "mutated denied alias remained authorized",
    }


def expand_limit_beyond_role(trace: ImportedTrace, policy: Policy) -> dict[str, Any] | None:
    if trace.semantic_ir is None:
        return {
            "mutation": "limit_expanded",
            "status": MutantStatus.STILLBORN,
            "reason": "trace has no semantic IR to mutate",
        }
    principal = policy.principals.get(trace.principal)
    if principal is None:
        return {
            "mutation": "limit_expanded",
            "status": MutantStatus.STILLBORN,
            "reason": "trace principal is not declared in the policy",
        }
    role = policy.roles.get(principal.role)
    if role is None:
        return {
            "mutation": "limit_expanded",
            "status": MutantStatus.STILLBORN,
            "reason": "trace principal role is not declared in the policy",
        }
    mutated = trace.semantic_ir.model_copy(update={"limit": role.max_rows + 1})
    oracle = PolicyOracle(policy)
    decision = oracle.authorize(trace.principal, mutated)
    return {
        "mutation": "limit_expanded",
        "status": MutantStatus.KILLED if not decision.allowed else MutantStatus.SURVIVED,
        "semantic_ir": mutated,
        "reason": "; ".join(decision.reasons) or "expanded limit remained authorized",
    }


def release_unauthorized_trace(trace: ImportedTrace, policy: Policy) -> dict[str, Any] | None:
    if trace.semantic_ir is None or trace.release_allowed is not True:
        return {
            "mutation": "release_unauthorized_result",
            "status": MutantStatus.EQUIVALENT,
            "reason": "trace either lacks semantic IR or did not release a result",
        }
    oracle = PolicyOracle(policy)
    decision = oracle.authorize(trace.principal, trace.semantic_ir)
    if decision.allowed:
        return {
            "mutation": "release_unauthorized_result",
            "status": MutantStatus.EQUIVALENT,
            "reason": "released trace is authorized by the canonical policy",
        }
    return {
        "mutation": "release_unauthorized_result",
        "status": MutantStatus.KILLED,
        "semantic_ir": trace.semantic_ir,
        "reason": "; ".join(decision.reasons),
    }


def semantic_query_dump(query: SemanticQuery | None) -> dict[str, Any] | None:
    if query is None:
        return None
    return query.normalized()

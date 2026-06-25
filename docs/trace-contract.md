# Imported Trace Contract

PolicyStrata scans newline-delimited JSON (`.jsonl`) records. Each line is one observed tool call,
ORM query, semantic-layer query, or SQL span.

## Minimal Record

```json
{
  "id": "ticket_count_001",
  "principal": "acme_analyst",
  "tenant_ids": ["acme"],
  "release_allowed": true,
  "semantic_ir": {
    "metric": "ticket_count",
    "dimensions": ["region"],
    "time_range": "last_month",
    "grain": "month",
    "limit": 100
  },
  "sql": "select count(distinct support_tickets.id) as value from accounts left join support_tickets on support_tickets.account_id = accounts.id where accounts.tenant_id in ('acme') limit 100"
}
```

## Fields

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable trace identifier. Use letters, numbers, `_`, `.`, or `-`. |
| `principal` | yes | Policy principal id from `domain/policy.yaml`. |
| `sql` | yes | Read-only SQL emitted by the application, ORM, semantic layer, or traced span. |
| `tenant_ids` | recommended | Tenant ids bound for the principal/request. These can be absent from parameterized SQL. |
| `semantic_ir` | recommended | PolicyStrata semantic query to authorize independently of SQL generation. |
| `release_allowed` | recommended | Whether the application released the result to the user. |
| `expected_policy` | optional | Free-form expected-policy notes, including `allow_rls_only: true` when SQL intentionally relies on RLS. |
| `source` | optional | Adapter or service that emitted the trace, such as `prisma`, `sqlalchemy`, or `otel`. |
| `timestamp` | optional | ISO-8601 event timestamp. |
| `regression_case` | optional | One of `fail_to_pass`, `pass_to_pass`, `contain_to_contain`, `deny_to_deny`, `allow_to_allow`, `unclassified`. |

`semantic_ir` supports:

| Field | Meaning |
| --- | --- |
| `metric` | Canonical policy metric or allowed alias. |
| `dimensions` | Requested dimensions. |
| `filters` | Structured filters captured before SQL lowering. |
| `time_range` | Canonical time range label. |
| `grain` | Aggregation grain. |
| `limit` | Row budget requested or applied. |

## Tenancy Configuration

Configure real application tenancy vocabulary in `policystrata.yaml`:

```yaml
tenancy:
  canonical_predicates:
    - "transactions.household_id = :principal.tenant_id"
    - "accounts.household_id = :principal.tenant_id"
    - "orders.organization_id = current_setting('app.organization_id')"
  tenant_columns:
    - transactions.household_id
    - accounts.household_id
    - organization_id
```

Use `expected_policy.allow_rls_only: true` only when the trace intentionally omits tenant literals
because database RLS is the policy containment layer.

## Validation

Run a local scan against imported traces:

```bash
uv run policystrata scan --config policystrata.yaml --out runs/scan
```

Findings include `what_changed`, `owner`, `probable_fix`, `minimal_repro_trace`, and
`ci_gate_command` so the scan artifact can be used directly in review or CI.

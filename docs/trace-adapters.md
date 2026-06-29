# Trace Adapter Recipes

These recipes produce PolicyStrata JSONL records without adding PolicyStrata to the production
request path. Emit traces in test, staging, or a sanitized replay job.

## TypeScript / Drizzle

Use the Node recorder when your agent stack runs in TypeScript/Next/Drizzle:

```ts
import { createPolicyStrataRecorder } from "policystrata/node";

const recorder = createPolicyStrataRecorder({
  service: "demo-data-agent",
  environment: process.env.NODE_ENV,
  out: ".policystrata/traces.jsonl",
  tenancy: {
    tenantColumns: ["transactions.household_id", "accounts.household_id"],
  },
});

const searchTransactions = recorder.wrapTool("searchTransactions", {
  kind: "read",
  scope: "household",
  handler: async (args, ctx) => {
    const query = db.select().from(transactions);
    recorder.captureQuery(query); // captures .toSQL() when the query builder exposes it
    return await query;
  },
});
```

Read-tool SQL records include top-level `sql`, `principal`, `tenant_ids`, and `semantic_ir`, so
`policystrata scan` can consume them directly. The same JSONL file may also contain
`agent_session`, `tool_execution`, and `mutation` records; the SQL scanner ignores those non-SQL
records while preserving them for downstream agent-session analysis.

The recorder redacts by default: ID-like fields are HMACed with a per-recorder key, prompt text and
raw error messages are omitted, SQL literal values are replaced with placeholders, arguments are
recorded by sanitized shape, and results are summarized as row counts plus sanitized field names. Pass a
deployment-specific `redaction.hashSalt` when traces need stable pseudonymous IDs across recorder
instances. With default ID hashing, the Node recorder omits scanner-contract `tenant_ids` rather
than writing HMAC values there; use `redaction.hashIds: false` only for trusted fixture traces that
need explicit tenant IDs for real database comparison. Structured payloads such as `semantic_ir`,
`expected_policy`, mutation, and audit metadata are recursively redacted; `semantic_ir.filters.tenant_id`
is HMACed under default ID hashing and preserved raw only when trusted fixtures set
`redaction.hashIds: false`.

## Prisma

Capture `$queryRaw` or generated SQL at the boundary where the app executes an AI-generated query:

```ts
prisma.$on("query", (event) => {
  if (!requestContext.aiToolCall) return;
  writePolicyStrataTrace({
    id: requestContext.traceId,
    principal: requestContext.principalId,
    tenantIds: [requestContext.tenantId],
    semanticIr: requestContext.semanticIr,
    sql: event.query,
    releaseAllowed: requestContext.releaseAllowed
  });
});
```

## SQLAlchemy

Use an engine event in a test or replay harness:

```py
import json
from sqlalchemy import event


@event.listens_for(engine, "before_cursor_execute")
def capture_policystrata_trace(conn, cursor, statement, parameters, context, executemany):
    request = getattr(context, "policystrata_request", None)
    if request is None:
        return
    with open("traces.policystrata.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "id": request.trace_id,
            "principal": request.principal,
            "tenant_ids": request.tenant_ids,
            "semantic_ir": request.semantic_ir,
            "sql": statement,
            "release_allowed": request.release_allowed,
            "source": "sqlalchemy",
        }) + "\n")
```

## Rails ActiveRecord

Subscribe to SQL notifications and attach request metadata from your AI tool context:

```rb
ActiveSupport::Notifications.subscribe("sql.active_record") do |_name, _start, _finish, _id, payload|
  ctx = Current.policystrata_trace
  next if ctx.nil?

  File.open("traces.policystrata.jsonl", "a") do |f|
    f.puts({
      id: ctx.trace_id,
      principal: ctx.principal,
      tenant_ids: ctx.tenant_ids,
      semantic_ir: ctx.semantic_ir,
      sql: payload[:sql],
      release_allowed: ctx.release_allowed,
      source: "active_record"
    }.to_json)
  end
end
```

## dbt Semantic Layer

Export the semantic query, compiled SQL, and principal mapping from the job or test harness that
calls dbt:

```json
{
  "id": "dbt_metric_001",
  "principal": "finance_analyst",
  "tenant_ids": ["north"],
  "semantic_ir": {"metric": "aum", "dimensions": ["segment"], "limit": 100},
  "sql": "select sum(balances.amount_cents) as value from ...",
  "release_allowed": true,
  "source": "dbt_semantic_layer"
}
```

Then add the semantic-model YAML to the same scan config:

```yaml
dbt:
  files:
    - semantic_models.yml
sql_traces:
  files:
    - traces.policystrata.jsonl
```

## OpenTelemetry Span Logs

If SQL already appears in spans, transform span attributes into the trace contract:

```json
{
  "id": "span-7f0a",
  "principal": "acme_analyst",
  "tenant_ids": ["acme"],
  "semantic_ir": {"metric": "ticket_count", "dimensions": ["region"], "limit": 100},
  "sql": "<db.statement>",
  "release_allowed": true,
  "source": "otel"
}
```

Recommended span attributes:

| Attribute | Trace field |
| --- | --- |
| `enduser.id` or app principal attribute | `principal` |
| tenant/org/household attribute | `tenant_ids` |
| semantic intent attribute | `semantic_ir` |
| `db.statement` | `sql` |
| output/release attribute | `release_allowed` |

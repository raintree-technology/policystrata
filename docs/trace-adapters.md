# Trace Adapter Recipes

These recipes produce PolicyStrata JSONL records without adding PolicyStrata to the production
request path. Emit traces in test, staging, or a sanitized replay job.

## TypeScript / Drizzle

Wrap the call site where your Ask AI tool has already produced semantic intent and SQL:

```ts
import { appendFileSync } from "node:fs";

export function writePolicyStrataTrace(trace: {
  id: string;
  principal: string;
  tenantIds: string[];
  semanticIr: unknown;
  sql: string;
  releaseAllowed: boolean;
}) {
  appendFileSync(
    "traces.policystrata.jsonl",
    JSON.stringify({
      id: trace.id,
      principal: trace.principal,
      tenant_ids: trace.tenantIds,
      semantic_ir: trace.semanticIr,
      sql: trace.sql,
      release_allowed: trace.releaseAllowed,
      source: "drizzle"
    }) + "\n"
  );
}
```

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

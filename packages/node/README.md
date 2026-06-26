# PolicyStrata Node SDK

This package records sanitized agent, tool, SQL, and mutation traces from TypeScript/Node
applications. Read-tool SQL records are compatible with `policystrata scan` JSONL imports.

```ts
import { createPolicyStrataRecorder } from "policystrata/node";

const recorder = createPolicyStrataRecorder({
  service: "betteroff-ask-ai",
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
    const query = db
      .select()
      .from(transactions)
      .where(eq(transactions.householdId, ctx.householdId));

    recorder.captureQuery(query);
    return await query;
  },
});
```

By default the recorder hashes ID fields, drops prompt text, redacts SQL literal values, records
argument shape instead of argument values, and summarizes result rows as field names plus row count.

## Drizzle

Use `captureQuery(query)` on Drizzle query builders that expose `.toSQL()`, or wrap a client:

```ts
const tracedDb = recorder.wrapDrizzleClient(db);
```

The proxy captures common execution methods (`execute`, `all`, `get`, `values`, `run`) and query
builders with `.toSQL()` before they execute. For explicit control, prefer `captureQuery()` at the
tool boundary where request context and release decisions are available.

## Record Types

- `sql_trace`: read-tool SQL records with top-level `sql`, `principal`, and `tenant_ids`; these can
  be consumed by `policystrata scan`.
- `agent_session`: session metadata such as model, prompt class, available tools, approval policy,
  and write-tool enablement. Prompt text is omitted unless explicitly enabled.
- `mutation`: write-tool metadata such as touched table, ownership predicates, written columns, and
  audit event state. These records intentionally omit top-level read SQL.
- `tool_execution`: a tool call that did not execute SQL.

The Python scanner ignores non-SQL SDK records when they appear in the same JSONL file.

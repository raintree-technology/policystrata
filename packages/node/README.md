# PolicyStrata Node SDK

This package records sanitized agent, tool, SQL, and mutation traces from TypeScript/Node
applications. Read-tool SQL records are compatible with `policystrata scan` JSONL imports.
The scanner/CLI distribution remains the PolicyStrata PyPI package; this directory is the
TypeScript SDK source and packaging surface.

It also exposes a deterministic runtime authorizer at `policystrata/runtime`. The scanner remains
a release gate, not a live service dependency; the runtime authorizer is the small in-process helper
applications can put on their own request path.

Install the Node runtime from npm:

```bash
npm install policystrata
```

`pip install policystrata` installs the Python CLI and scanner. It does not make
`policystrata/runtime` importable to Node applications.

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
    const query = db
      .select()
      .from(transactions)
      .where(eq(transactions.householdId, ctx.householdId));

    recorder.captureQuery(query);
    return await query;
  },
});
```

By default the recorder hashes ID fields with a per-recorder HMAC key, drops prompt text,
redacts raw error messages and SQL literal values, records sanitized argument shape instead of
argument values, and summarizes result rows as sanitized field names plus row count. Pass a deployment-specific
`redaction.hashSalt` when traces need stable pseudonymous IDs across recorder instances. With
default ID hashing, scanner-contract `tenant_ids` are omitted rather than HMACed; use
`redaction.hashIds: false` only for trusted fixture traces that need explicit tenant IDs for real
database comparison. Structured payloads such as `semantic_ir`, `expected_policy`, mutation, and
audit metadata are recursively redacted; `semantic_ir.filters.tenant_id` is HMACed under default ID
hashing and preserved raw only when trusted fixtures set `redaction.hashIds: false`.

## Drizzle

Use `captureQuery(query)` on Drizzle query builders that expose `.toSQL()`, or wrap a client:

```ts
const tracedDb = recorder.wrapDrizzleClient(db);
```

The proxy captures common execution methods (`execute`, `all`, `get`, `values`, `run`) and query
builders with `.toSQL()` before they execute. For explicit control, prefer `captureQuery()` at the
tool boundary where request context and release decisions are available.

## Record Types

- `sql_trace`: read-tool SQL records with top-level `sql` and `principal`; trusted fixture traces
  may also include raw `tenant_ids` for `policystrata scan`.
- `agent_session`: session metadata such as model, prompt class, available tools, approval policy,
  and write-tool enablement. Prompt text is omitted unless explicitly enabled.
- `mutation`: write-tool metadata such as touched table, ownership predicates, written columns, and
  audit event state. These records intentionally omit top-level read SQL.
- `tool_execution`: a tool call that did not execute SQL.

The Python scanner ignores non-SQL SDK records when they appear in the same JSONL file.

## Runtime Authorizer

```ts
import { createPolicyStrataAuthorizer } from "policystrata/runtime";

const authorizer = createPolicyStrataAuthorizer(runtimeManifest);
const decision = authorizer.authorize({
  subject: { id: "user-1", role: "owner" },
  action: "read",
  resource: "searchTransactions",
  context: {
    semanticIr: { metric: "transaction_spend", dimensions: ["merchant_name"] },
  },
  mode: "shadow",
});
```

`authorizeTool()` remains as a compatibility wrapper over the generic API:

```ts
const toolDecision = authorizer.authorizeTool({
  toolName: "searchTransactions",
  userId: "user-1",
  householdId: "household-1",
  role: "owner",
  toolKind: "read",
  allowWriteTools: false,
  writeState: "disabled",
  approvalRequiredSatisfied: true,
  approvalState: "satisfied",
  decisionPoint: "execution",
  semanticIr: { metric: "transaction_spend", dimensions: ["merchant_name"] },
  mode: "shadow",
});
```

`authorizeTool()` decisions include operational metadata for application logs and metrics:
`toolKind`, `decisionPoint`, `writeState`, `approvalState`, `userId`, and `householdId`.
Approval-required tools may be visible at `decisionPoint: "pre_model"` with
`approvalState: "pending"`; the same pending approval is denied at `decisionPoint: "execution"`.

`authorizeRelease()` wraps the same API for the paper's release-conformance boundary: a result and
its lineage may leave only approved boundaries.

```ts
const releaseDecision = authorizer.authorizeRelease({
  subject: { id: "user-1", role: "owner" },
  resource: "searchTransactions",
  boundary: "user",
  result: { kind: "aggregate", rowCount: 12, containsSensitiveValues: false },
  lineage: { sources: ["transactions"], containsRawRows: false },
  mode: "enforce",
});
```

Runtime manifests must default to deny. Unknown tools/resources/actions, unknown roles, missing
approval, write tools without an application write-tool grant, undeclared semantic metrics or
dimensions, and release attempts that violate result/lineage/boundary constraints are denied.
`allowed` is always the deterministic policy decision. `mode` is reported as rollout metadata:
applications usually log or sample denied shadow decisions, then block the same denied decision only
after switching that call site to `mode: "enforce"`.

```ts
if (!decision.allowed && decision.enforcementMode === "enforce") {
  throw new Error(decision.reasons.join("; "));
}
```

The same runtime module evaluates v0.2 gateway events across auth context, retrieval, memory,
tool, browser/code, SQL, schema binding, output, egress, and trace layers:

```ts
import { evaluateRuntimeEvent, sqlRuntimeEvent } from "policystrata/runtime";

const runtimeDecision = evaluateRuntimeEvent(runtimeManifest, sqlRuntimeEvent({
  eventId: "evt_1",
  project: "support-bi",
  agent: { key: "support-bi-copilot" },
  summary: "Tenant-scoped support ticket query",
  actor: { userId: "user-1", tenantId: "tenant-a", role: "support", purpose: "support" },
  resource: { kind: "table", name: "support_tickets" },
  sql: "select count(*) from support_tickets where tenant_id = $1",
}));
```

Runtime event builders are available for common layers:

- `buildRuntimeEvent()` for explicit low-level events.
- `sqlRuntimeEvent()` for SQL statement metadata.
- `toolRuntimeEvent()` for MCP/tool calls and schema refs.
- `retrievalRuntimeEvent()` for vector/search retrieval evidence.
- `egressRuntimeEvent()` for outbound webhook/API destinations.
- `clearanceEvidencePackRuntimeEvent()` for referencing a local `.clearance/evidence-pack.json`
  artifact in runtime evidence without calling hosted Clearance APIs.

## Next.js Route Handler

Use the runtime helpers in the application request path, not as a hosted dependency:

```ts
import { NextResponse } from "next/server";
import { evaluateRuntimeEvent, sqlRuntimeEvent } from "policystrata/runtime";
import runtimeManifest from "@/policystrata.runtime.json";

export async function POST(request: Request) {
  const body = await request.json();
  const sql = compileTenantScopedSql(body);
  const decision = evaluateRuntimeEvent(runtimeManifest, sqlRuntimeEvent({
    eventId: crypto.randomUUID(),
    project: "support-bi",
    agent: { key: "support-bi-copilot" },
    summary: "Support ticket query",
    actor: {
      userId: body.userId,
      tenantId: body.tenantId,
      role: body.role,
      purpose: "support",
    },
    resource: { kind: "table", name: "support_tickets", tenantId: body.tenantId },
    sql,
  }));

  if (!decision.allowed) {
    return NextResponse.json({ error: decision.reason }, { status: 403 });
  }

  return NextResponse.json(await runQuery(sql));
}
```

For a customer-hosted sidecar, install `@policystrata/agent-trust-gateway`; it wraps this evaluator
in an HTTP gateway and strips runtime-event `payload` and fixture-only `expectedDecision` metadata
before control-plane upload by default. The gateway is an application-side enforcement and telemetry
helper; it does not replace
`policystrata scan`, `policystrata doctor`, application authorization, or database controls.

The runtime manifest schema is available at `policystrata/runtime-manifest.schema.json` and in this
source tree at `schema/runtime-manifest.schema.json`. The runtime authorizer is for in-process app
checks on tool and release boundaries in the request path. `policystrata scan` remains the
CI/release evidence gate over exported traces and should not be treated as a live authorization
service.

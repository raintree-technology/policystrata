# PolicyStrata Node SDK

**Active SDK for TypeScript and Node teams that need sanitized policy evidence or
deterministic runtime decisions inside their own application.**

Use `policystrata/node` to record agent, tool, SQL, and mutation traces. Use
`policystrata/runtime` to evaluate a deny-by-default runtime manifest without adding a
hosted service to the request path.

## Install

```bash
npm install policystrata
```

`pip install policystrata` installs the Python scanner and CLI. It does not provide the
Node imports shown here.

## Record a tool call

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

Expected result: the recorder writes sanitized JSONL that `policystrata scan` can
evaluate as release evidence.

## Choose a surface

| Import | Use it for | Result |
| --- | --- | --- |
| `policystrata/node` | Record tool, query, session, and mutation evidence | Sanitized JSONL traces |
| `policystrata/runtime` | Authorize tools, releases, and runtime events | Deterministic local decisions |
| `@policystrata/agent-trust-gateway` | Run the evaluator as a customer-hosted sidecar | Loopback HTTP decisions and redacted envelopes |

The scanner remains a CI and release gate. The runtime helpers are the in-process
checks that applications can place on request, tool, and release boundaries.

## Privacy and support boundary

The recorder hashes ID fields with a per-recorder HMAC key, drops prompt text, redacts
raw errors and SQL literal values, records argument shape instead of argument values,
and summarizes result rows by field names and row count. Set a deployment-specific
`redaction.hashSalt` when pseudonymous IDs must remain stable across recorder instances.

Review deployment-specific fields before export. Keep application authorization and
database controls in place. Runtime manifests must default to deny; the runtime helper
does not replace database enforcement, and the scanner is not a live authorization
service.

## Deeper documentation

- [Node SDK and runtime guide](../../docs/node-sdk.md) — Drizzle capture, record types,
  authorizers, runtime events, and a Next.js route example.
- [Runtime controls](../../docs/runtime-controls.md) — PII, SQL, MCP, browser, code,
  approval, and kill-switch examples.
- [Imported trace contract](../../docs/trace-contract.md) — JSONL fields accepted by the
  scanner.
- [PolicyStrata project guide](../../README.md) — Scanner workflow, evidence, and limits.
- [Security policy](../../SECURITY.md) — Reporting and disclosure boundary.

## License

[MIT License](LICENSE)

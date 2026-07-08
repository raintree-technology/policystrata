# PolicyStrata Agent Trust Gateway

Customer-hosted runtime gateway for governed-data agents. The gateway evaluates redacted runtime
events locally with `policystrata/runtime`, blocks deny/quarantine/approval-required decisions in
enforce mode, and uploads only decision envelopes to Clearance by PolicyStrata by default.
It is an application-side enforcement and telemetry helper, not a replacement for `policystrata
scan`, `policystrata doctor`, application authorization, or database controls.

```bash
npm install @policystrata/agent-trust-gateway
```

```bash
agent-trust-gateway serve --manifest runtime-manifest.json --port 8787 \
  --api-url https://policystrata.example
```

Loopback bindings are intended for same-host sidecars. If you bind beyond
loopback, set `POLICYSTRATA_GATEWAY_TOKEN` or pass `--gateway-token`; callers
must send `authorization: Bearer <token>` to `/v1/decide`.

POST one event or `{ "events": [...] }` to `/v1/decide`:

```bash
curl -s http://127.0.0.1:8787/v1/decide \
  -H 'content-type: application/json' \
  --data @runtime-event.json
```

The same evaluator is available in-process:

```ts
import { decideRuntimeEvent } from "@policystrata/agent-trust-gateway";

const result = decideRuntimeEvent(runtimeManifest, runtimeEvent);
if (!result.ok) {
  throw new Error(result.decisions.map((decision) => decision.reason).join("; "));
}
```

## Runtime Modes

Use `enforce` for production gates that should fail closed on deny, quarantine, or approval-required
decisions. Use `shadow` to observe decisions without blocking the caller. For tenant, PII, SQL,
egress, and tool controls, production examples should default to fail-closed behavior and rely on
explicit approvals or allowlists for exceptions.

The evaluator supports:

- auth-context required fields
- retrieval tenant and entitlement checks
- SQL tenant predicate detection, query-risk classification, and row-limit checks
- RLS drift events through the `database_rule` layer
- runtime kill-switch deny behavior
- memory tenant isolation
- egress destination allowlists, approval requirements, and destination classes
- data-class deny/redaction policies

See `docs/runtime-controls.md` for PII, MCP schema, browser action, code execution, human approval,
and kill-switch event examples.
See `docs/gateway-deployment-examples.md` for generic Docker, Terraform, and Helm deployment
sketches that avoid hosted-app assumptions.

## Upload Boundary

`payload` is stripped before upload unless `includePayload` or `--include-payload` is set.
Fixture-only `expectedDecision` metadata is always stripped before upload. Keep raw prompts, rows,
documents, tool payloads, connector payloads, and test expectations local; send hashes, witness
refs, policy refs, redaction classes, query risk, and the runtime decision envelope to the control
plane.

Uploads fail closed by default if the redacted envelope still contains sensitive field names or
common secret/PII value patterns in summaries, refs, or other metadata. Use
`allowBoundaryViolations` only for local negative tests.

Uploads send `x-clearance-organization-id` and the legacy
`x-assurance-organization-id` header while hosted control planes migrate. Uploads also support an
idempotency key and enforce a 1 MB default upload-body limit before opening the network request.

## Deployment Guidance

Keep the gateway close to the application or agent runtime. For production:

- bind to loopback or require a gateway token for non-loopback bindings;
- terminate TLS and rate-limit requests at the platform edge, service mesh, or reverse proxy;
- keep request bodies small and metadata-only;
- default tenant, PII, SQL, egress, and tool controls to fail closed;
- use `shadow` mode only while validating policy coverage before an enforcement rollout.

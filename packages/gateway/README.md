# PolicyStrata Agent Trust Gateway

**Active customer-hosted package for teams that need PolicyStrata runtime decisions
beside an application or agent.**

The gateway evaluates redacted runtime events locally with `policystrata/runtime`. In
enforce mode it blocks deny, quarantine, and approval-required decisions. It uploads
only decision envelopes to a configured control plane by default.

## Install and start

```bash
npm install @policystrata/agent-trust-gateway
```

```bash
agent-trust-gateway serve --manifest runtime-manifest.json --port 8787 \
  --api-url https://policystrata.example
```

Expected result: a loopback HTTP service accepts redacted runtime events at
`/v1/decide` and returns deterministic allow, deny, quarantine, or approval decisions.

```bash
curl -s http://127.0.0.1:8787/v1/decide \
  -H 'content-type: application/json' \
  --data @runtime-event.json
```

The endpoint accepts one event or `{ "events": [...] }`. To bind beyond loopback, set
`POLICYSTRATA_GATEWAY_TOKEN` or pass `--gateway-token`; callers must send an
`authorization: Bearer <token>` header.

## Use the evaluator in-process

```ts
import { decideRuntimeEvent } from "@policystrata/agent-trust-gateway";

const result = decideRuntimeEvent(runtimeManifest, runtimeEvent);
if (!result.ok) {
  throw new Error(result.decisions.map((decision) => decision.reason).join("; "));
}
```

Use `enforce` when a deny, quarantine, or approval-required decision must fail closed.
Use `shadow` while measuring policy coverage without blocking the caller.

## Security and upload boundary

The gateway strips `payload` before upload unless `includePayload` or
`--include-payload` is set. It always strips fixture-only `expectedDecision` metadata.
Keep raw prompts, rows, documents, tool payloads, connector payloads, and test
expectations local.

Uploads fail closed by default if the redacted envelope still contains sensitive field
names or common secret or PII value patterns. The default upload-body limit is 1 MB.
Use `allowBoundaryViolations` only for local negative tests.

## Compatibility and support boundary

The gateway requires the Node version declared by the package and a deny-by-default
PolicyStrata runtime manifest. Keep it close to the application, bind to loopback or a
trusted network, and terminate TLS and rate-limit at the platform edge, service mesh, or
reverse proxy.

This package is an application-side enforcement and telemetry helper. It does not
replace application authorization, database controls, `policystrata scan`, or
`policystrata doctor`.

## Deeper documentation

- [Runtime controls](../../docs/runtime-controls.md) — Supported control layers and event examples.
- [Gateway deployment examples](../../docs/gateway-deployment-examples.md) — Docker,
  Terraform, and Helm starting points.
- [Node SDK and runtime guide](../../docs/node-sdk.md) — In-process authorizers and event builders.
- [PolicyStrata project guide](../../README.md) — Scanner workflow, evidence, and limits.
- [Security policy](../../SECURITY.md) — Reporting and disclosure boundary.

## License

[MIT License](LICENSE)

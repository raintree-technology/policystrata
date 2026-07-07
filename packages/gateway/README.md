# PolicyStrata Agent Trust Gateway

Customer-hosted runtime gateway for governed-data agents. The gateway evaluates redacted runtime
events locally with `policystrata/runtime`, blocks deny/quarantine/approval-required decisions in
enforce mode, and uploads only decision envelopes to the PolicyStrata control plane by default.
It is an application-side enforcement and telemetry helper, not a replacement for `policystrata
scan`, `policystrata doctor`, application authorization, or database controls.

```bash
npm install @policystrata/agent-trust-gateway
```

```bash
agent-trust-gateway serve --manifest runtime-manifest.json --port 8787 \
  --api-url https://policystrata.example
```

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

`payload` is stripped before upload unless `includePayload` or `--include-payload` is set.
Fixture-only `expectedDecision` metadata is always stripped before upload. Keep raw prompts, rows,
documents, tool payloads, and test expectations local; send hashes, witness refs, policy refs, and
the runtime decision envelope to the control plane.

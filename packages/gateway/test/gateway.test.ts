import assert from "node:assert/strict";
import { createServer, type IncomingMessage } from "node:http";
import type { AddressInfo } from "node:net";
import test from "node:test";

import {
  PolicyStrataGatewayBlockedError,
  decideRuntimeEvent,
  decideRuntimeEvents,
  guardRuntimePayload,
  startAgentTrustGateway,
  uploadRuntimeEvents,
  type RuntimeEventWithDecision,
} from "../src/index.js";
import type { PolicyStrataRuntimeEventInput, PolicyStrataRuntimeManifest } from "policystrata/runtime";

const manifest: PolicyStrataRuntimeManifest = {
  schemaVersion: "policystrata.runtime_manifest.v1",
  version: "gateway.test",
  defaultDecision: "deny",
  resources: [
    {
      name: "support_tickets",
      type: "table",
      actions: [{ name: "read", allowedRoles: ["support_manager"] }],
    },
  ],
  controls: {
    authContext: { requiredFields: ["userId", "tenantId", "role", "purpose"] },
    sql: { tenantColumn: "tenant_id" },
    egress: { allowedDestinations: ["https://approved.example/webhook"] },
  },
};

function event(overrides: Partial<PolicyStrataRuntimeEventInput> = {}): PolicyStrataRuntimeEventInput {
  return {
    schemaVersion: "0.2.0",
    eventId: "evt_gateway",
    project: "support-bi",
    observedAt: "2026-07-06T15:58:52Z",
    agent: { key: "support-bi-copilot" },
    layer: "sql",
    operation: "read",
    summary: "SQL read against support tickets",
    actor: {
      userId: "user_1",
      tenantId: "tenant_a",
      role: "support_manager",
      purpose: "support",
    },
    resource: { kind: "table", name: "support_tickets" },
    payload: { sql: "select * from support_tickets where tenant_id = 'tenant_a'" },
    ...overrides,
  };
}

test("decideRuntimeEvent returns an allow decision with a redacted event envelope", () => {
  const result = decideRuntimeEvent(manifest, event());

  assert.equal(result.ok, true);
  assert.equal(result.mode, "enforce");
  assert.equal(result.events[0].decision.action, "allow");
  assert.equal(result.decisions[0].event.decision.action, "allow");
});

test("guardRuntimePayload throws in enforce mode for denied runtime events", async () => {
  await assert.rejects(
    guardRuntimePayload(
      manifest,
      event({ payload: { sql: "select * from support_tickets where status = 'open'" } }),
    ),
    PolicyStrataGatewayBlockedError,
  );
});

test("decideRuntimeEvents permits shadow-mode observation without changing the decision", () => {
  const result = decideRuntimeEvents(
    manifest,
    [event({ payload: { sql: "select * from support_tickets" } })],
    "shadow",
  );

  assert.equal(result.ok, false);
  assert.equal(result.mode, "shadow");
  assert.equal(result.decisions[0].action, "deny");
});

test("uploadRuntimeEvents strips payloads by default", async () => {
  let received: unknown;
  const controlPlane = await startJsonServer(async (request) => {
    received = await readJson(request);
    return { ok: true };
  });
  try {
    const result = decideRuntimeEvent(manifest, event({ expectedDecision: { allowed: true, action: "allow" } }));
    const upload = await uploadRuntimeEvents({
      apiUrl: controlPlane.url,
      token: "token_test",
      organizationId: "org_test",
      events: result.events,
    });

    assert.equal(upload.ok, true);
    assert.equal(upload.status, 200);
    assert.deepEqual((received as { events: RuntimeEventWithDecision[] }).events[0].payload, undefined);
    assert.equal((received as { events: RuntimeEventWithDecision[] }).events[0].expectedDecision, undefined);
    assert.equal((received as { events: RuntimeEventWithDecision[] }).events[0].payloadHash, undefined);
  } finally {
    await controlPlane.close();
  }
});

test("HTTP gateway evaluates, blocks, and uploads redacted runtime events", async () => {
  let received: unknown;
  const controlPlane = await startJsonServer(async (request) => {
    received = await readJson(request);
    return { ok: true };
  });
  const gateway = await startAgentTrustGateway({
    manifest,
    port: 0,
    upload: { apiUrl: controlPlane.url },
  });
  try {
    const response = await fetch(`${gateway.url}/v1/decide`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        events: [event({ eventId: "evt_deny", payload: { sql: "select * from support_tickets" } })],
      }),
    });
    const body = (await response.json()) as {
      ok: boolean;
      decisions: Array<{ action: string }>;
    };

    assert.equal(response.status, 403);
    assert.equal(body.ok, false);
    assert.equal(body.decisions[0].action, "deny");
    assert.equal((received as { events: RuntimeEventWithDecision[] }).events[0].payload, undefined);
    assert.equal((received as { events: RuntimeEventWithDecision[] }).events[0].decision.action, "deny");
  } finally {
    await gateway.close();
    await controlPlane.close();
  }
});

async function startJsonServer(
  handler: (request: IncomingMessage) => Promise<unknown>,
): Promise<{ url: string; close(): Promise<void> }> {
  const server = createServer((request, response) => {
    void handler(request).then(
      (body) => {
        response.writeHead(200, { "content-type": "application/json" });
        response.end(`${JSON.stringify(body)}\n`);
      },
      (error: unknown) => {
        response.writeHead(500, { "content-type": "application/json" });
        response.end(`${JSON.stringify({ error: error instanceof Error ? error.message : String(error) })}\n`);
      },
    );
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      resolve();
    });
  });
  const address = server.address() as AddressInfo;
  return {
    url: `http://${address.address}:${address.port}`,
    close: () =>
      new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      }),
  };
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown;
}

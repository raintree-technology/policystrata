import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import type { AddressInfo } from "node:net";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  POLICYSTRATA_GATEWAY_VERSION,
  PolicyStrataGatewayBlockedError,
  decideRuntimeEvent,
  decideRuntimeEvents,
  guardRuntimePayload,
  nativeIntegrationRuntimeEvent,
  scanMetadataBoundary,
  startAgentTrustGateway,
  uploadRuntimeEvents,
  type RuntimeEventWithDecision,
} from "../src/index.js";
import type { PolicyStrataRuntimeEventInput, PolicyStrataRuntimeManifest } from "policystrata/runtime";

const TEST_DIR = dirname(fileURLToPath(import.meta.url));
const PACKAGE_JSON = JSON.parse(
  readFileSync(join(TEST_DIR, "..", "..", "package.json"), "utf8"),
) as { version: string };

function requiredItem<T>(items: readonly T[], index: number): T {
  const item = items[index];
  if (item === undefined) {
    throw new Error(`expected item at index ${index}`);
  }
  return item;
}

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
  assert.equal(requiredItem(result.events, 0).decision.action, "allow");
  assert.equal(requiredItem(result.decisions, 0).event.decision.action, "allow");
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
  assert.equal(requiredItem(result.decisions, 0).action, "deny");
});

test("uploadRuntimeEvents strips payloads by default", async () => {
  let received: unknown;
  let idempotency: string | undefined;
  const controlPlane = await startJsonServer(async (request) => {
    received = await readJson(request);
    idempotency = request.headers["idempotency-key"]?.toString();
    return { ok: true };
  });
  try {
    const result = decideRuntimeEvent(manifest, event({ expectedDecision: { allowed: true, action: "allow" } }));
    const upload = await uploadRuntimeEvents({
      apiUrl: controlPlane.url,
      token: "token_test",
      organizationId: "org_test",
      idempotencyKey: "evt-upload-once",
      events: result.events,
    });

    assert.equal(upload.ok, true);
    assert.equal(upload.status, 200);
    assert.equal(
      (received as { gateway: { name: string } }).gateway.name,
      "@policystrata/agent-trust-gateway",
    );
    assert.equal(
      (received as { gateway: { version: string } }).gateway.version,
      PACKAGE_JSON.version,
    );
    const uploadedEvent = requiredItem(
      (received as { events: RuntimeEventWithDecision[] }).events,
      0,
    );
    assert.deepEqual(uploadedEvent.payload, undefined);
    assert.equal(uploadedEvent.expectedDecision, undefined);
    assert.equal(uploadedEvent.payloadHash, undefined);
    assert.equal((received as { headers?: unknown }).headers, undefined);
    assert.equal(idempotency, "evt-upload-once");
  } finally {
    await controlPlane.close();
  }
});

test("gateway version constant matches package metadata", () => {
  assert.equal(POLICYSTRATA_GATEWAY_VERSION, PACKAGE_JSON.version);
});

test("scanMetadataBoundary finds raw prompts and secrets before upload", () => {
  const findings = scanMetadataBoundary({
    events: [
      {
        eventId: "evt_secret",
        rawPrompt: "contact alice@example.com",
        sampledRows: [{ customerEmail: "alice@example.com" }],
        toolPayload: { card: "4111 1111 1111 1111" },
        summary: "Authorization: Bearer tokenfixturevalue",
      },
    ],
  });

  assert.ok(findings.some((finding) => finding.path === "$.events[0].rawPrompt"));
  assert.ok(findings.some((finding) => finding.path === "$.events[0].sampledRows"));
  assert.ok(findings.some((finding) => finding.path === "$.events[0].toolPayload"));
  assert.ok(findings.some((finding) => finding.reason.includes("bearer token")));
});

test("uploadRuntimeEvents fails closed on metadata boundary violations", async () => {
  const result = decideRuntimeEvent(
    manifest,
    event({ summary: "Authorization: Bearer tokenfixturevalue" }),
  );

  await assert.rejects(
    uploadRuntimeEvents({
      apiUrl: "https://clearance.example",
      events: result.events,
    }),
    /metadata-only boundary violation/,
  );
});

test("uploadRuntimeEvents enforces upload payload size before network", async () => {
  const result = decideRuntimeEvent(manifest, event());

  await assert.rejects(
    uploadRuntimeEvents({
      apiUrl: "https://clearance.example",
      events: result.events,
      maxBodyBytes: 1,
    }),
    /too large/,
  );
});

test("runtime evaluation rejects SQL substring tenant matches and classifies risk", () => {
  const substring = decideRuntimeEvent(
    {
      ...manifest,
      controls: { ...manifest.controls, sql: { tenantColumn: "tenant_id" } },
    },
    event({ payload: { sql: "select tenant_id from support_tickets where status = 'open'" } }),
  );
  const exportRisk = decideRuntimeEvent(
    {
      ...manifest,
      controls: { ...manifest.controls, sql: { tenantColumn: "tenant_id", allowedQueryRisks: ["read"] } },
    },
    event({ payload: { sql: "copy support_tickets to stdout where tenant_id = 'tenant_a'" } }),
  );

  assert.equal(substring.ok, false);
  assert.match(requiredItem(substring.decisions, 0).reason, /missing tenant predicate/);
  assert.equal(requiredItem(exportRisk.decisions, 0).queryRisk, "export");
  assert.match(
    requiredItem(exportRisk.decisions, 0).reasons.join("\n"),
    /SQL query risk export/,
  );
});

test("runtime evaluation denies unparameterized SQL when required", () => {
  const result = decideRuntimeEvent(
    {
      ...manifest,
      controls: { ...manifest.controls, sql: { tenantColumn: "tenant_id", requireParameterized: true } },
    },
    event({ payload: { sql: "select * from support_tickets where tenant_id = 'tenant_a'" } }),
  );

  assert.equal(result.ok, false);
  assert.equal(requiredItem(result.decisions, 0).controlId, "sql_parameterization_required");
  assert.match(requiredItem(result.decisions, 0).reason, /string_literal/);
});

test("runtime evaluation checks RLS drift and egress destination classes", () => {
  const rls = decideRuntimeEvent(
    { ...manifest, controls: { ...manifest.controls, databaseRule: { requireRls: true } } },
    event({
      layer: "database_rule",
      operation: "rls_drift",
      resource: { kind: "table", name: "support_tickets" },
      rlsExpected: true,
      rlsEnabled: false,
    }),
  );
  const egress = decideRuntimeEvent(
    { ...manifest, controls: { ...manifest.controls, egress: { allowedDestinationClasses: ["approved_vendor"] } } },
    event({
      layer: "egress",
      operation: "export",
      resource: {
        kind: "webhook",
        name: "external",
        uri: "https://analytics.example/webhook",
        destinationClass: "public_internet",
      },
    }),
  );

  assert.equal(requiredItem(rls.decisions, 0).controlId, "rls_drift");
  assert.equal(requiredItem(egress.decisions, 0).controlId, "egress_destination_class");
});

test("runtime evaluation denies when manifest kill switch is enabled", () => {
  const result = decideRuntimeEvent(
    { ...manifest, controls: { ...manifest.controls, runtime: { killSwitch: true } } },
    event(),
  );

  assert.equal(result.ok, false);
  assert.equal(requiredItem(result.decisions, 0).controlId, "runtime_kill_switch");
});

test("nativeIntegrationRuntimeEvent emits provider traceability", () => {
  const integrationEvent = nativeIntegrationRuntimeEvent({
    provider: "aws",
    project: "support-bi",
    connectionId: "conn_aws",
    payload: { accountId: "123456789012" },
  });

  assert.equal(integrationEvent.provider, "aws");
  assert.equal(integrationEvent.integrationConnectionId, "conn_aws");
  assert.equal(integrationEvent.layer, "egress");
  assert.equal(integrationEvent.decision?.action, "require_approval");
  assert.deepEqual(integrationEvent.artifactRefs, ["integration://aws/conn_aws"]);
});

test("uploadRuntimeEvents sends the configured organization header", async () => {
  let organizationHeader: string | undefined;
  const controlPlane = await startJsonServer(async (request) => {
    organizationHeader = request.headers["x-clearance-organization-id"]?.toString();
    return { ok: true };
  });
  try {
    const result = decideRuntimeEvent(manifest, event());
    await uploadRuntimeEvents({
      apiUrl: controlPlane.url,
      token: "token_test",
      organizationId: "org_test",
      events: result.events,
    });

    assert.equal(organizationHeader, "org_test");
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
    assert.equal(requiredItem(body.decisions, 0).action, "deny");
    const uploadedEvent = requiredItem(
      (received as { events: RuntimeEventWithDecision[] }).events,
      0,
    );
    assert.equal(uploadedEvent.payload, undefined);
    assert.equal(uploadedEvent.decision.action, "deny");
  } finally {
    await gateway.close();
    await controlPlane.close();
  }
});

test("HTTP gateway requires a token when configured", async () => {
  const gateway = await startAgentTrustGateway({
    manifest,
    port: 0,
    gatewayToken: "gateway_secret",
  });
  try {
    const unauthorized = await fetch(`${gateway.url}/v1/decide`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(event()),
    });
    assert.equal(unauthorized.status, 401);

    const authorized = await fetch(`${gateway.url}/v1/decide`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: "Bearer gateway_secret",
      },
      body: JSON.stringify(event()),
    });
    assert.equal(authorized.status, 200);
  } finally {
    await gateway.close();
  }
});

test("HTTP gateway refuses non-loopback binding without a token", async () => {
  await assert.rejects(
    startAgentTrustGateway({
      manifest,
      host: "0.0.0.0",
      port: 0,
    }),
    /POLICYSTRATA_GATEWAY_TOKEN/,
  );
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

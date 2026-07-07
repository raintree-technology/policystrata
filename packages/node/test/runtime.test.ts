import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import { Ajv2020 } from "ajv/dist/2020.js";

import {
  authorize,
  authorizeRelease,
  authorizeTool,
  createPolicyStrataAuthorizer,
  evaluateRuntimeEvent,
  evaluateRuntimeEvents,
  expectedRuntimeDecisionMismatches,
  type PolicyStrataAuthorizeInput,
  type PolicyStrataRuntimeEventInput,
  type PolicyStrataRuntimeManifest,
} from "../src/runtime.js";

interface RuntimeFixtureCase {
  name: string;
  input: PolicyStrataAuthorizeInput;
  expected: {
    allowed: boolean;
    normalizedRoles: string[];
    reasonIncludes: string[];
  };
}

const conformanceManifest = JSON.parse(
  readFileSync(new URL("../../test/fixtures/runtime/manifest.json", import.meta.url), "utf8"),
) as PolicyStrataRuntimeManifest;

const conformanceCases = JSON.parse(
  readFileSync(new URL("../../test/fixtures/runtime/cases.json", import.meta.url), "utf8"),
) as RuntimeFixtureCase[];

const runtimeManifestSchema = JSON.parse(
  readFileSync(new URL("../../schema/runtime-manifest.schema.json", import.meta.url), "utf8"),
) as Record<string, unknown>;

const toolManifest: PolicyStrataRuntimeManifest = {
  schemaVersion: "policystrata.runtime_manifest.v1",
  version: "test.1",
  defaultDecision: "deny",
  roleAliases: {
    owner: "household_owner",
    admin: "household_admin",
    viewer: "household_viewer",
  },
  tools: [
    {
      name: "searchTransactions",
      kind: "read",
      allowedRoles: ["household_owner", "household_admin", "household_viewer"],
      metrics: ["transaction_spend"],
      dimensions: ["merchant_name"],
    },
    {
      name: "generateTransactionExport",
      kind: "export",
      approvalRequired: true,
      allowedRoles: ["household_owner", "household_admin"],
      metrics: ["export_row_count"],
      dimensions: ["export_kind"],
    },
    {
      name: "categorizeTransaction",
      kind: "write",
      approvalRequired: true,
      allowedRoles: ["household_owner", "household_admin"],
      metrics: ["transaction_spend"],
      dimensions: ["category"],
    },
  ],
};

const governedRuntimeManifest: PolicyStrataRuntimeManifest = {
  schemaVersion: "policystrata.runtime_manifest.v1",
  version: "runtime.v2.test",
  defaultDecision: "deny",
  resources: [
    {
      name: "support_tickets",
      type: "table",
      actions: [{ name: "read", allowedRoles: ["support_manager"] }],
    },
  ],
  controls: {
    authContext: {
      requiredFields: ["userId", "tenantId", "role", "purpose"],
    },
    retrieval: { enabled: true },
    tools: {
      allowlist: ["workspace.search_tickets"],
      approvalRequired: ["workspace.export_csv"],
    },
    sql: { tenantColumn: "tenant_id" },
    schemaBinding: { currentVersions: { customer_health_score: "v2" } },
    memory: { enabled: true },
    egress: {
      allowedDestinations: ["https://approved.example/webhook"],
      approvalRequired: true,
    },
    data: {
      redactClasses: ["pii"],
      secretClasses: ["credential"],
    },
    dataResidency: {
      enabled: true,
      allowedRegions: ["us"],
    },
    taint: {
      blockPromptInjection: true,
      blockTaintedToolResults: true,
    },
  },
};

function runtimeEvent(overrides: Partial<PolicyStrataRuntimeEventInput> = {}): PolicyStrataRuntimeEventInput {
  return {
    schemaVersion: "0.2.0",
    eventId: "evt_test",
    project: "support-bi",
    observedAt: "2026-07-06T15:58:52Z",
    agent: { key: "support-bi-copilot" },
    layer: "sql",
    operation: "read",
    summary: "runtime event",
    actor: {
      userId: "user_1",
      tenantId: "tenant_a",
      role: "support_manager",
      purpose: "support",
      region: "us",
    },
    resource: { kind: "table", name: "support_tickets" },
    dataClasses: [],
    payload: { sql: "select * from support_tickets where tenant_id = 'tenant_a'" },
    ...overrides,
  };
}

test("runtime manifest JSON Schema is packaged as a deny-by-default manifest schema", () => {
  assert.equal(runtimeManifestSchema.title, "PolicyStrata Runtime Manifest");
  assert.deepEqual(
    runtimeManifestSchema.properties &&
      (runtimeManifestSchema.properties as Record<string, unknown>).defaultDecision,
    {
      const: "deny",
    },
  );
  const defs = runtimeManifestSchema.$defs as Record<string, unknown>;
  assert.ok(defs.releaseConstraints);
});

test("runtime conformance manifest validates against the packaged JSON Schema", () => {
  const ajv = new Ajv2020({ allErrors: true, strictTypes: false });
  const validate = ajv.compile(runtimeManifestSchema);

  assert.equal(validate(conformanceManifest), true, JSON.stringify(validate.errors, null, 2));
  assert.equal(validate({ ...conformanceManifest, defaultDecision: "allow" }), false);
  assert.match(JSON.stringify(validate.errors), /defaultDecision/);
});

test("generic authorize follows runtime conformance fixtures", () => {
  const authorizer = createPolicyStrataAuthorizer(conformanceManifest);

  for (const fixture of conformanceCases) {
    const decision = authorizer.authorize(fixture.input);
    assert.equal(decision.allowed, fixture.expected.allowed, fixture.name);
    assert.deepEqual(decision.normalizedRoles, fixture.expected.normalizedRoles, fixture.name);
    assert.equal(decision.manifestVersion, "conformance.1", fixture.name);
    for (const expectedReason of fixture.expected.reasonIncludes) {
      assert.match(decision.reasons.join("\n"), new RegExp(expectedReason), fixture.name);
    }
  }
});

test("top-level authorize helper delegates to the generic runtime API", () => {
  const decision = authorize(conformanceManifest, conformanceCases[0].input);

  assert.equal(decision.allowed, true);
  assert.deepEqual(decision.normalizedRoles, ["household_viewer"]);
});

test("top-level authorizeTool helper delegates to the generic runtime API", () => {
  const decision = authorizeTool(toolManifest, {
    toolName: "searchTransactions",
    userId: "user_1",
    householdId: "household_1",
    role: "viewer",
    toolKind: "read",
    semanticIr: { metric: "transaction_spend", dimensions: ["merchant_name"] },
    decisionPoint: "execution",
  });

  assert.equal(decision.allowed, true);
  assert.equal(decision.action, "read");
  assert.equal(decision.normalizedRole, "household_viewer");
  assert.equal(decision.toolKind, "read");
  assert.equal(decision.userId, "user_1");
  assert.equal(decision.householdId, "household_1");
  assert.equal(decision.writeState, "disabled");
  assert.equal(decision.approvalState, "not_required");
  assert.equal(decision.decisionPoint, "execution");
});

test("authorizeRelease wraps release-boundary conformance checks", () => {
  const authorizer = createPolicyStrataAuthorizer(conformanceManifest);
  const decision = authorizer.authorizeRelease({
    subject: { role: "viewer" },
    resource: "searchTransactions",
    boundary: "user",
    result: { kind: "aggregate", rowCount: 12, containsSensitiveValues: false },
    lineage: { sources: ["transactions"], containsRawRows: false },
    mode: "enforce",
  });

  assert.equal(decision.allowed, true);
  assert.equal(decision.action, "release");
  assert.equal(decision.boundary, "user");
  assert.equal(decision.enforcementMode, "enforce");
});

test("top-level authorizeRelease delegates to the release runtime API", () => {
  const decision = authorizeRelease(conformanceManifest, {
    subject: { role: "viewer" },
    resource: "searchTransactions",
    boundary: "llm_context",
    result: { kind: "aggregate", rowCount: 12 },
    lineage: { sources: ["transactions"] },
  });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /release boundary llm_context/);
});

test("authorizeTool allows modeled read tools for aliased roles", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({
    toolName: "searchTransactions",
    role: "viewer",
    semanticIr: { metric: "transaction_spend", dimensions: ["merchant_name"] },
    mode: "shadow",
  });

  assert.equal(decision.allowed, true);
  assert.equal(decision.action, "read");
  assert.equal(decision.normalizedRole, "household_viewer");
  assert.equal(decision.manifestVersion, "test.1");
  assert.equal(decision.enforcementMode, "shadow");
});

test("authorizeTool denies unknown tools by default", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({ toolName: "unknownTool", role: "owner" });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /unknown tool: unknownTool/);
});

test("authorizeTool denies unknown roles", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({ toolName: "searchTransactions", role: "support" });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /unknown role: support/);
});

test("authorizeTool denies role/tool mismatches", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({
    toolName: "generateTransactionExport",
    role: "viewer",
    approvalRequiredSatisfied: true,
  });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /roles household_viewer are not allowed/);
});

test("authorizeTool approval-required tools require approval", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({
    toolName: "generateTransactionExport",
    role: "owner",
    approvalRequiredSatisfied: false,
  });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /requires approval/);
});

test("authorizeTool exposes approval-required tools at the pre-model decision point", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({
    toolName: "generateTransactionExport",
    role: "owner",
    toolKind: "export",
    decisionPoint: "pre_model",
    approvalState: "pending",
    userId: "user_1",
    householdId: "household_1",
  });

  assert.equal(decision.allowed, true);
  assert.equal(decision.toolKind, "export");
  assert.equal(decision.decisionPoint, "pre_model");
  assert.equal(decision.approvalState, "pending");
  assert.equal(decision.writeState, "disabled");
  assert.equal(decision.userId, "user_1");
  assert.equal(decision.householdId, "household_1");
});

test("authorizeTool denies mismatched tool-kind context", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({
    toolName: "searchTransactions",
    role: "owner",
    toolKind: "write",
  });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /tool kind context write/);
  assert.equal(decision.toolKind, "read");
});

test("authorizeTool write tools require the write-tool gate and approval", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const denied = authorizer.authorizeTool({
    toolName: "categorizeTransaction",
    role: "admin",
    approvalRequiredSatisfied: true,
    allowWriteTools: false,
  });
  assert.equal(denied.allowed, false);
  assert.match(denied.reasons.join("\n"), /requires allowWriteTools/);

  const allowed = authorizer.authorizeTool({
    toolName: "categorizeTransaction",
    role: "admin",
    approvalRequiredSatisfied: true,
    allowWriteTools: true,
    mode: "enforce",
  });
  assert.equal(allowed.allowed, true);
  assert.equal(allowed.enforcementMode, "enforce");
});

test("authorizeTool semantic IR must match declared tool metrics and dimensions", () => {
  const authorizer = createPolicyStrataAuthorizer(toolManifest);
  const decision = authorizer.authorizeTool({
    toolName: "searchTransactions",
    role: "owner",
    semanticIr: { metric: "account_balance", dimensions: ["account_mask"] },
  });

  assert.equal(decision.allowed, false);
  assert.match(decision.reasons.join("\n"), /metric account_balance/);
  assert.match(decision.reasons.join("\n"), /dimension account_mask/);
});

test("runtime manifests must default to deny", () => {
  assert.throws(
    () =>
      createPolicyStrataAuthorizer({
        ...toolManifest,
        defaultDecision: "allow" as "deny",
      }),
    /default to deny/,
  );
});

test("evaluateRuntimeEvent allows clean governed SQL metadata", () => {
  const event = runtimeEvent({ expectedDecision: { allowed: true, action: "allow" } });
  const decision = evaluateRuntimeEvent(governedRuntimeManifest, event);

  assert.equal(decision.allowed, true);
  assert.equal(decision.action, "allow");
  assert.equal(decision.decision.action, "allow");
  assert.equal(decision.event.decision.action, "allow");
  assert.deepEqual(expectedRuntimeDecisionMismatches(event, decision), []);
});

test("expectedRuntimeDecisionMismatches reports fixture assertion drift", () => {
  const event = runtimeEvent({ expectedDecision: { allowed: true, action: "allow" } });
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({ payload: { sql: "select * from support_tickets" } }),
  );

  assert.deepEqual(expectedRuntimeDecisionMismatches(event, decision), [
    "expected allowed=true, got allowed=false",
    "expected action=allow, got action=deny",
  ]);
});

test("evaluateRuntimeEvent denies missing auth context", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({ actor: { userId: "user_1", role: "support_manager" } }),
  );

  assert.equal(decision.allowed, false);
  assert.equal(decision.action, "deny");
  assert.match(decision.reason, /missing auth context fields/);
});

test("evaluateRuntimeEvent denies cross-tenant retrieval without entitlement", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({
      layer: "retrieval",
      operation: "retrieve",
      resource: {
        kind: "chunk",
        name: "refund_policy_enterprise",
        tenantId: "tenant_b",
        requiredEntitlements: ["refund_policy:enterprise"],
      },
    }),
  );

  assert.equal(decision.allowed, false);
  assert.equal(decision.action, "deny");
  assert.match(decision.reasons.join("\n"), /retrieval resource tenant/);
  assert.match(decision.reasons.join("\n"), /missing retrieval entitlements/);
});

test("evaluateRuntimeEvent requires approval for unapproved tools", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({
      layer: "tool_call",
      operation: "call_tool",
      resource: { kind: "mcp_tool", name: "workspace.export_csv" },
    }),
  );

  assert.equal(decision.allowed, false);
  assert.equal(decision.action, "require_approval");
  assert.match(decision.reason, /not in the runtime allowlist/);
});

test("evaluateRuntimeEvent blocks SQL without tenant scope", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({ payload: { sql: "select * from support_tickets where status = 'open'" } }),
  );

  assert.equal(decision.allowed, false);
  assert.equal(decision.action, "deny");
  assert.match(decision.reason, /missing tenant predicate tenant_id/);
});

test("evaluateRuntimeEvent logs stale schema bindings", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({
      layer: "schema_binding",
      operation: "bind_metric",
      resource: { kind: "metric", name: "customer_health_score", version: "v1" },
    }),
  );

  assert.equal(decision.allowed, true);
  assert.equal(decision.action, "log_only");
  assert.match(decision.reason, /expected v2/);
});

test("evaluateRuntimeEvent denies unapproved egress", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({
      layer: "egress",
      operation: "export",
      resource: { kind: "webhook", name: "external", uri: "https://bad.example/webhook" },
      approvalRequiredSatisfied: false,
    }),
  );

  assert.equal(decision.allowed, false);
  assert.equal(decision.action, "deny");
  assert.match(decision.reason, /egress destination/);
});

test("evaluateRuntimeEvent quarantines cross-tenant memory", () => {
  const decision = evaluateRuntimeEvent(
    governedRuntimeManifest,
    runtimeEvent({
      layer: "memory",
      operation: "read_memory",
      resource: { kind: "memory", name: "prior_summary", tenantId: "tenant_b" },
    }),
  );

  assert.equal(decision.allowed, false);
  assert.equal(decision.action, "quarantine");
  assert.match(decision.reason, /memory item tenant/);
});

test("evaluateRuntimeEvents returns decisions and redacted events for batches", () => {
  const decisions = evaluateRuntimeEvents(governedRuntimeManifest, [
    runtimeEvent({ eventId: "evt_allowed" }),
    runtimeEvent({ eventId: "evt_redact", dataClasses: ["pii"] }),
  ]);

  assert.deepEqual(
    decisions.map((decision) => decision.eventId),
    ["evt_allowed", "evt_redact"],
  );
  assert.equal(decisions[1].action, "redact");
  assert.deepEqual(decisions[1].redactions, ["pii"]);
  assert.deepEqual(decisions[1].event.decision.redactions, ["pii"]);
});

import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import assert from "node:assert/strict";
import test from "node:test";

import { analyzePolicyStrataSql, createPolicyStrataRecorder } from "../src/node.js";

function tempTracePath(): { dir: string; path: string } {
  const dir = mkdtempSync(join(tmpdir(), "policystrata-node-"));
  return { dir, path: join(dir, "traces.jsonl") };
}

function readJsonl(path: string): Record<string, unknown>[] {
  return readFileSync(path, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

test("wrapTool emits a redacted PolicyStrata-compatible SQL trace", async () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    environment: "test",
    out: path,
    principal: "household_admin",
    tenantIds: ["household-123"],
    tenancy: {
      tenantColumns: ["transactions.household_id", "accounts.household_id"],
    },
    uuid: () => "00000000-0000-4000-8000-000000000001",
    now: () => new Date("2026-06-26T12:00:00.000Z"),
  });

  const searchTransactions = recorder.wrapTool("searchTransactions", {
    kind: "read",
    scope: "household",
    handler: async (args: { merchant: string }, ctx: { sessionId: string } & Record<string, unknown>) => {
      assert.equal(args.merchant, "Coffee Shop");
      recorder.captureQuery({
        sql: `
          select transactions.merchant, transactions.amount, accounts.name
          from transactions
          join accounts on accounts.id = transactions.account_id
          where transactions.household_id = $1 and transactions.merchant = 'Coffee Shop'
        `,
      });
      assert.equal(ctx.sessionId, "chat-run-1");
      return [{ merchant: "Coffee Shop", amount: 42, date: "2026-06-01" }];
    },
  });

  await searchTransactions(
    { merchant: "Coffee Shop" },
    {
      sessionId: "chat-run-1",
      actor: { userId: "user-1", householdId: "household-123", role: "household_admin" },
      releaseAllowed: true,
      semanticIr: { metric: "transaction_search", limit: 25 },
    },
  );

  const records = readJsonl(path);
  assert.equal(records.length, 1);
  const record = records[0];
  assert.equal(record.record_type, "sql_trace");
  assert.equal(record.service, "demo-data-agent");
  assert.equal(record.principal, "household_admin");
  assert.equal(record.session_id, "chat-run-1");
  assert.equal((record.tool as Record<string, unknown>).name, "searchTransactions");
  assert.equal((record.tool as Record<string, unknown>).kind, "read");
  assert.match(String(record.sql), /transactions\.household_id = \$1/);
  assert.doesNotMatch(String(record.sql), /Coffee Shop/);
  assert.deepEqual((record.query as Record<string, unknown>).tenant_predicates, [
    "transactions.household_id",
  ]);
  assert.deepEqual((record.result as Record<string, unknown>).fields_returned, [
    "amount",
    "date",
    "merchant",
  ]);
  assert.equal((record.result as Record<string, unknown>).row_count, 1);
  assert.deepEqual(
    ((record.argument_shape as Record<string, unknown>).fields as Record<string, unknown>).merchant,
    { type: "string" },
  );
  assert.doesNotMatch(JSON.stringify(record.argument_shape), /Coffee Shop/);
  assert.match(((record.actor as Record<string, unknown>).user_id as string) ?? "", /^hmac-sha256:/);
  assert.equal(record.tenant_ids, undefined);

  rmSync(dir, { recursive: true, force: true });
});

test("recordSession drops prompt text by default", () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
    now: () => new Date("2026-06-26T12:00:00.000Z"),
  });

  recorder.recordSession({
    sessionId: "chat-run-1",
    promptClass: "user_finance_question",
    promptText: "How much did I spend at the coffee shop?",
    model: "gpt-test",
    toolsAvailable: ["searchTransactions"],
    toolsCalled: ["searchTransactions"],
    writeToolsEnabled: false,
    approvalPolicy: "read_only",
  });

  const [record] = readJsonl(path);
  assert.equal(record.record_type, "agent_session");
  assert.equal((record.agent_session as Record<string, unknown>).prompt_class, "user_finance_question");
  assert.equal((record.agent_session as Record<string, unknown>).prompt_text, undefined);

  rmSync(dir, { recursive: true, force: true });
});

test("write tools emit mutation records without top-level read SQL", async () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
    principal: "household_admin",
    redaction: { hashIds: false },
  });

  const categorizeTransaction = recorder.wrapTool("categorizeTransaction", {
    kind: "write",
    scope: "household",
    approvalRequired: true,
    handler: async () => {
      recorder.captureQuery(
        "update transactions set category_id = $1 where id = $2 and household_id = $3",
      );
      return { ok: true };
    },
    describeMutation: () => ({
      table: "transactions",
      where_predicates: ["id", "household_id"],
      columns_written: ["category_id"],
    }),
  });

  await categorizeTransaction(
    { transactionId: "txn-1", categoryId: "cat-1" },
    { sessionId: "chat-run-1", tenantIds: ["household-123"], approvalToken: "signed-token" },
  );

  const [record] = readJsonl(path);
  assert.equal(record.record_type, "mutation");
  assert.equal(record.sql, undefined);
  assert.equal(
    (record.query as Record<string, unknown>).sql,
    "update transactions set category_id = $1 where id = $2 and household_id = $3",
  );
  assert.deepEqual((record.mutation as Record<string, unknown>).columns_written, ["category_id"]);
  assert.equal((record.authorization as Record<string, unknown>).approval_token_present, true);

  rmSync(dir, { recursive: true, force: true });
});

test("SQL analysis flags common tenant-scope risks", () => {
  const analysis = analyzePolicyStrataSql("select count(*) from transactions", {
    tenancy: { tenantColumns: ["transactions.household_id"] },
  });

  assert.deepEqual(analysis.tables, ["transactions"]);
  assert.equal(analysis.tenant_predicates.length, 0);
  assert.ok(analysis.warnings.some((warning) => warning.code === "aggregate_without_tenant_predicate"));
  assert.ok(
    analysis.warnings.some((warning) => warning.code === "tenant_table_without_tenant_predicate"),
  );
});

test("SQL analysis redacts PostgreSQL dollar-quoted literals", () => {
  const analysis = analyzePolicyStrataSql(
    "select $$alice@example.com$$ as email, $secret$token-value$secret$ as token from accounts",
  );

  assert.doesNotMatch(analysis.sql, /alice@example\.com|token-value/);
  assert.match(analysis.sql, /select \? as email, \? as token from accounts/);
});

test("SQL analysis strips comments before writing trace SQL", () => {
  const analysis = analyzePolicyStrataSql(
    `
      select count(*) from accounts
      -- token=tokenfixturevalue Authorization: Bearer header-secret
      where accounts.tenant_id = 'acme'
      /* password=comment-secret */
    `,
  );

  assert.doesNotMatch(analysis.sql, /tokenfixturevalue|header-secret|comment-secret|Bearer|--|\/\*/);
  assert.match(analysis.sql, /where accounts\.tenant_id = \?/);
});

test("tool errors redact messages by default", async () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
  });
  const failingTool = recorder.wrapTool("failingTool", {
    kind: "read",
    handler: async () => {
      throw new Error("database password=supersecret token=tokenfixturevalue");
    },
  });

  await assert.rejects(() => failingTool({}, {}), /supersecret/);

  const [record] = readJsonl(path);
  assert.deepEqual(record.error, { name: "Error", message: "redacted" });
  assert.doesNotMatch(JSON.stringify(record), /supersecret|tokenfixturevalue/);

  rmSync(dir, { recursive: true, force: true });
});

test("opt-in tool error messages pass through secret redaction", async () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
    redaction: { includeErrorMessages: true },
  });
  const failingTool = recorder.wrapTool("failingTool", {
    kind: "read",
    handler: async () => {
      throw new Error(
        "query failed password=supersecret token=tokenfixturevalue where email = 'person@example.com'",
      );
    },
  });

  await assert.rejects(() => failingTool({}, {}), /supersecret/);

  const [record] = readJsonl(path);
  assert.equal((record.error as Record<string, unknown>).name, "Error");
  assert.match(String((record.error as Record<string, unknown>).message), /password=\[redacted\]/);
  assert.match(String((record.error as Record<string, unknown>).message), /token=\[redacted\]/);
  assert.doesNotMatch(JSON.stringify(record), /supersecret|tokenfixturevalue|person@example\.com/);

  rmSync(dir, { recursive: true, force: true });
});

test("authorization context keeps only safe status fields", () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
    redaction: { hashIds: false },
  });

  recorder.recordAudit(
    { event_emitted: true },
    {
      sessionId: "chat-run-1",
      authorization: {
        consent_checked: true,
        approval_token_present: false,
        actor_role: "household_admin",
        privileged_reason: "break-glass token=tokenfixturevalue",
        token: "tokenfixturevalue",
        authorization: "Bearer tokenfixturevalue",
      },
      approvalToken: "raw-approval-token",
    },
  );

  const [record] = readJsonl(path);
  assert.deepEqual(record.authorization, {
    consent_checked: true,
    approval_token_present: false,
    actor_role: "household_admin",
    privileged_reason: "break-glass token=[redacted]",
  });
  assert.doesNotMatch(JSON.stringify(record), /tokenfixturevalue|raw-approval-token|Bearer/);

  rmSync(dir, { recursive: true, force: true });
});

test("semantic IR and expected policy payloads are redacted by default", () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
  });

  recorder.recordQuery("select count(*) from accounts where tenant_id = $1", {
    principal: "acme_analyst",
    semanticIr: {
      metric: "ticket_count",
      filters: {
        tenant_id: "acme",
        customer_email: "person@example.com",
      },
    },
    expectedPolicy: {
      tenant_id: "acme",
      tenant_ids: ["acme"],
      user_ids: ["user-123"],
      api_token: "tokenfixturevalue",
      account_number: 123456789,
      accountID: "acct-1",
      tenantIDs: ["tenant-1"],
      card: { pan: "4111111111111111" },
      note: "export approved with token=free-form-secret and Authorization: Bearer note-secret",
      contact: "email alice@example.com with tokenfixturevalue123 and eyJabc.def.ghi",
      "person@example.com": "email-key",
      tokenfixturekey123: "token-key",
      authorization: "Basic fixturecredential",
      cookie: "session=abc",
      credential: "api-client-secret",
      session: "session-value",
      csrfToken: "csrf-secret",
    },
  });

  const [record] = readJsonl(path);
  const serialized = JSON.stringify(record);
  const semanticFilters = (record.semantic_ir as Record<string, unknown>).filters as Record<string, unknown>;
  const expectedPolicyKeys = Object.keys(record.expected_policy as Record<string, unknown>);
  assert.equal("tenant_id" in semanticFilters, false);
  assert.equal("customer_email" in semanticFilters, false);
  assert.equal(expectedPolicyKeys.includes("tenant_id"), false);
  assert.equal(expectedPolicyKeys.includes("api_token"), false);
  assert.equal(expectedPolicyKeys.includes("authorization"), false);
  assert.equal(expectedPolicyKeys.includes("cookie"), false);
  assert.equal(expectedPolicyKeys.includes("credential"), false);
  assert.equal(expectedPolicyKeys.includes("session"), false);
  assert.equal(expectedPolicyKeys.includes("accountID"), false);
  assert.equal(expectedPolicyKeys.includes("tenantIDs"), false);
  assert.match(serialized, /hmac-sha256:/);
  assert.match(serialized, /\[redacted\]/);
  assert.match(serialized, /token=\[redacted\]/);
  assert.doesNotMatch(
    serialized,
    /person@example\.com|alice@example\.com|fixturecredential|session=abc|api-client-secret|session-value|csrf-secret|tokenfixturevalue|tokenfixturevalue123|tokenfixturekey123|email-key|token-key|free-form-secret|note-secret|eyJabc|4111111111111111|123456789|acct-1|tenant-1|"acme"|"user-123"/,
  );

  rmSync(dir, { recursive: true, force: true });
});

test("mutation and audit plural ID fields are hashed by default", () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
  });

  recorder.recordMutation(
    { table: "accounts", account_ids: ["acct-1"], organization_ids: ["org-1"] },
    { principal: "acme_analyst" },
    { event_emitted: true, user_ids: ["user-1"] },
  );

  const [record] = readJsonl(path);
  const serialized = JSON.stringify(record);
  assert.match(serialized, /hmac-sha256:/);
  assert.doesNotMatch(serialized, /account_ids|organization_ids|user_ids|acct-1|org-1|user-1/);

  rmSync(dir, { recursive: true, force: true });
});

test("opt-in prompt text and result rows scrub bare secrets", () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
    redaction: { includePromptText: true, includeResultRows: true },
  });

  recorder.recordSession({
    sessionId: "chat-run-1",
    promptText: "contact alice@example.com with tokenfixtureprompt123 and 4111111111111111",
  });
  recorder.recordQuery({
    sql: "select note from accounts",
    result: [
      {
        note: "jwt eyJabc.def.ghi email bob@example.com token tokenfixtureresult123",
        userID: "user-123",
        "bob@example.com": "email-key",
      },
    ],
  });

  const records = readJsonl(path);
  assert.equal(records.length, 2);
  assert.doesNotMatch(
    JSON.stringify(records),
    /alice@example\.com|bob@example\.com|tokenfixtureprompt123|tokenfixtureresult123|4111111111111111|eyJabc|user-123|email-key|userID/,
  );
  assert.match(JSON.stringify(records), /\[redacted_email\]/);
  assert.match(JSON.stringify(records), /\[redacted_token\]/);

  rmSync(dir, { recursive: true, force: true });
});

test("argument and result summary keys are sanitized by default", async () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
  });
  const tool = recorder.wrapTool("sensitiveShapeTool", {
    kind: "read",
    handler: async () => [
      {
        amount: 10,
        "person@example.com": "customer",
        api_token: "tokenfixturevalue",
        tenant_id: "tenant-123",
      },
    ],
  });

  await tool(
    {
      merchant: "Coffee Shop",
      "person@example.com": "customer",
      api_token: "tokenfixturevalue",
      tenant_id: "tenant-123",
      nested: { "4111111111111111": true },
    },
    {},
  );

  const [record] = readJsonl(path);
  const argumentFields = (record.argument_shape as { fields: Record<string, unknown> }).fields;
  const resultFields = (record.result as Record<string, string[]>).fields_returned;
  assert.deepEqual(argumentFields.merchant, { type: "string" });
  assert.ok(Object.keys(argumentFields).some((key) => key.startsWith("hmac-sha256:")));
  assert.ok(resultFields.some((field) => field.startsWith("hmac-sha256:")));
  assert.ok(resultFields.includes("[redacted_key]"));
  assert.doesNotMatch(
    JSON.stringify(record),
    /person@example\.com|api_token|tenant_id|4111111111111111|tokenfixturevalue|tenant-123/,
  );

  rmSync(dir, { recursive: true, force: true });
});

test("wrapped Drizzle transaction clients capture queries", async () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "demo-data-agent",
    out: path,
    principal: "household_admin",
    redaction: { hashIds: false },
    tenancy: { tenantColumns: ["transactions.household_id"] },
  });
  const query = {
    toSQL: () => ({
      sql: "select count(*) from transactions where transactions.household_id = $1",
      params: ["household-123"],
    }),
  };
  const db = {
    transaction: async <T>(
      callback: (tx: { execute: (input: typeof query) => Promise<T> }) => Promise<T>,
    ) =>
      callback({
        execute: async () => [{ value: 1 }] as T,
      }),
  };

  const tracedDb = recorder.wrapDrizzleClient(db, () => ({
    sessionId: "chat-run-1",
    tenantIds: ["household-123"],
  }));
  await tracedDb.transaction(async (tx) => tx.execute(query));

  const [record] = readJsonl(path);
  assert.equal(record.record_type, "sql_trace");
  assert.equal(record.sql, "select count(*) from transactions where transactions.household_id = $1");
  assert.deepEqual(record.tenant_ids, ["household-123"]);
  assert.deepEqual((record.query as Record<string, unknown>).tenant_predicates, [
    "transactions.household_id",
  ]);

  rmSync(dir, { recursive: true, force: true });
});

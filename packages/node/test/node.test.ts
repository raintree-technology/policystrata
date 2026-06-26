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
    service: "betteroff-ask-ai",
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
  assert.equal(record.service, "betteroff-ask-ai");
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
  assert.match(((record.actor as Record<string, unknown>).user_id as string) ?? "", /^sha256:/);
  assert.match(((record.tenant_ids as string[])[0] as string) ?? "", /^sha256:/);

  rmSync(dir, { recursive: true, force: true });
});

test("recordSession drops prompt text by default", () => {
  const { dir, path } = tempTracePath();
  const recorder = createPolicyStrataRecorder({
    service: "betteroff-ask-ai",
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
    service: "betteroff-ask-ai",
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

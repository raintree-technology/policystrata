import { AsyncLocalStorage } from "node:async_hooks";
import { createHash, randomUUID } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export type PolicyStrataToolKind = "read" | "write" | "memory" | "external";

export interface PolicyStrataRedactionConfig {
  hashIds?: boolean;
  hashSalt?: string;
  includePromptText?: boolean;
  includeSqlValues?: boolean;
  includeResultRows?: boolean;
  safeFields?: string[];
  idFields?: string[];
}

export interface PolicyStrataTenancyConfig {
  tenantColumns?: string[];
  tenantKeys?: string[];
  tenantTables?: string[];
}

export interface PolicyStrataRecorderOptions {
  service: string;
  environment?: string;
  out?: string;
  source?: string;
  principal?: string;
  tenantIds?: string[];
  redaction?: PolicyStrataRedactionConfig;
  tenancy?: PolicyStrataTenancyConfig;
  writer?: (record: PolicyStrataTraceRecord) => void;
  uuid?: () => string;
  now?: () => Date;
}

export interface PolicyStrataActor {
  user_id?: string;
  household_id?: string;
  organization_id?: string;
  role?: string;
}

export interface PolicyStrataAuthorization {
  consent_checked?: boolean;
  household_actor_required?: boolean;
  write_context_required?: boolean;
  write_tools_enabled?: boolean;
  approval_required?: boolean;
  approval_token_present?: boolean;
  actor_role?: string;
  privileged_reason?: string;
  [key: string]: unknown;
}

export interface PolicyStrataSessionTrace {
  sessionId?: string;
  session_id?: string;
  promptClass?: string;
  prompt_class?: string;
  promptText?: string;
  prompt_text?: string;
  model?: string;
  toolsAvailable?: string[];
  tools_available?: string[];
  toolsCalled?: string[];
  tools_called?: string[];
  writeToolsEnabled?: boolean;
  write_tools_enabled?: boolean;
  approvalPolicy?: string;
  approval_policy?: string;
  principal?: string;
  tenantIds?: string[];
  tenant_ids?: string[];
  actor?: PolicyStrataActor | Record<string, unknown>;
}

export interface PolicyStrataExecutionContext {
  sessionId?: string;
  session_id?: string;
  principal?: string;
  tenantIds?: string[];
  tenant_ids?: string[];
  actor?: PolicyStrataActor | Record<string, unknown>;
  semanticIr?: Record<string, unknown>;
  semantic_ir?: Record<string, unknown>;
  releaseAllowed?: boolean;
  release_allowed?: boolean;
  authorization?: PolicyStrataAuthorization;
  approvalToken?: string;
  approval_token?: string;
  expectedPolicy?: Record<string, unknown>;
  expected_policy?: Record<string, unknown>;
  privilegedReason?: string;
  privileged_reason?: string;
  policystrata?: PolicyStrataExecutionContext;
  [key: string]: unknown;
}

export interface PolicyStrataToolSpec<TArgs, TContext, TResult> {
  kind: PolicyStrataToolKind;
  scope?: string;
  approvalRequired?: boolean;
  approval_required?: boolean;
  inputSchema?: unknown;
  handler: (args: TArgs, ctx: TContext) => TResult | Promise<TResult>;
  describeResult?: (result: TResult) => PolicyStrataResultTrace;
  describeMutation?: (args: TArgs, result: TResult) => PolicyStrataMutationTrace | undefined;
}

export interface PolicyStrataQueryInput {
  sql?: string;
  query?: string;
  params?: unknown[];
  source?: string;
  privileged?: boolean;
  privilegedReason?: string;
  privileged_reason?: string;
  result?: unknown;
  releaseAllowed?: boolean;
  release_allowed?: boolean;
  semanticIr?: Record<string, unknown>;
  semantic_ir?: Record<string, unknown>;
}

export interface PolicyStrataSqlAnalysis {
  sql: string;
  tables: string[];
  selected_columns: string[];
  tenant_predicates: string[];
  warnings: PolicyStrataSqlWarning[];
  raw_sql_unparseable: boolean;
}

export interface PolicyStrataSqlWarning {
  code:
    | "raw_sql_unparseable"
    | "tenant_table_without_tenant_predicate"
    | "tenant_join_without_scoped_condition"
    | "aggregate_without_tenant_predicate"
    | "privileged_client_without_reason";
  message: string;
  table?: string;
}

export interface PolicyStrataResultTrace {
  row_count?: number;
  fields_returned?: string[];
  contains_sensitive_values?: boolean;
  rows?: unknown;
  [key: string]: unknown;
}

export interface PolicyStrataMutationTrace {
  table?: string;
  where_predicates?: string[];
  columns_written?: string[];
  expected_tables?: string[];
  permitted_columns?: string[];
  [key: string]: unknown;
}

export interface PolicyStrataAuditTrace {
  event_emitted?: boolean;
  event_type?: string;
  [key: string]: unknown;
}

export interface PolicyStrataTraceRecord {
  id: string;
  record_type: "sql_trace" | "tool_execution" | "agent_session" | "mutation";
  version: "policystrata.node.trace.v1";
  source: string;
  timestamp: string;
  service: string;
  environment?: string;
  trace_id?: string;
  session_id?: string;
  principal?: string;
  tenant_ids?: string[];
  release_allowed?: boolean;
  sql?: string;
  semantic_ir?: Record<string, unknown>;
  expected_policy?: Record<string, unknown>;
  actor?: PolicyStrataActor;
  tool?: {
    name: string;
    kind: PolicyStrataToolKind;
    scope?: string;
    approval_required: boolean;
  };
  authorization?: PolicyStrataAuthorization;
  query?: PolicyStrataSqlAnalysis & { query_index?: number };
  result?: PolicyStrataResultTrace;
  mutation?: PolicyStrataMutationTrace;
  audit?: PolicyStrataAuditTrace;
  argument_shape?: unknown;
  agent_session?: Record<string, unknown>;
  error?: { name: string; message: string };
  metadata?: Record<string, unknown>;
}

interface NormalizedContext {
  sessionId?: string;
  principal?: string;
  tenantIds: string[];
  actor?: PolicyStrataActor;
  semanticIr?: Record<string, unknown>;
  releaseAllowed?: boolean;
  authorization: PolicyStrataAuthorization;
  expectedPolicy?: Record<string, unknown>;
  privilegedReason?: string;
}

interface CapturedQuery {
  input: PolicyStrataQueryInput;
  analysis: PolicyStrataSqlAnalysis;
}

interface ToolExecutionState {
  traceId: string;
  idPrefix: string;
  startedAt: Date;
  toolName: string;
  toolKind: PolicyStrataToolKind;
  toolScope?: string;
  approvalRequired: boolean;
  argsShape: unknown;
  context: NormalizedContext;
  queries: CapturedQuery[];
}

const DEFAULT_SOURCE = "policystrata.node";
const DEFAULT_TENANT_KEYS = [
  "tenant_id",
  "household_id",
  "organization_id",
  "org_id",
  "workspace_id",
  "user_id",
];
const DEFAULT_ID_FIELDS = [
  "id",
  "user_id",
  "userId",
  "household_id",
  "householdId",
  "organization_id",
  "organizationId",
  "tenant_id",
  "tenantId",
  "account_id",
  "accountId",
];
const SENSITIVE_FIELD_PATTERN =
  /(email|phone|ssn|social|token|secret|password|dob|birth|address|account_number|routing_number|card|pan|pii)/i;
const SQL_AGGREGATE_PATTERN = /\b(count|sum|avg|min|max)\s*\(/i;

export class PolicyStrataRecorder {
  private readonly options: Required<Pick<PolicyStrataRecorderOptions, "service">> &
    Omit<PolicyStrataRecorderOptions, "service">;
  private readonly redaction: Required<PolicyStrataRedactionConfig>;
  private readonly tenancy: Required<PolicyStrataTenancyConfig>;
  private readonly storage = new AsyncLocalStorage<ToolExecutionState>();

  constructor(options: PolicyStrataRecorderOptions) {
    this.options = options;
    this.redaction = {
      hashIds: true,
      hashSalt: "policystrata",
      includePromptText: false,
      includeSqlValues: false,
      includeResultRows: false,
      safeFields: [],
      idFields: DEFAULT_ID_FIELDS,
      ...options.redaction,
    };
    const tenantColumns = options.tenancy?.tenantColumns ?? [];
    this.tenancy = {
      tenantColumns,
      tenantKeys: options.tenancy?.tenantKeys ?? DEFAULT_TENANT_KEYS,
      tenantTables: options.tenancy?.tenantTables ?? tablesFromTenantColumns(tenantColumns),
    };
  }

  wrapTool<TArgs, TContext, TResult>(
    name: string,
    spec: PolicyStrataToolSpec<TArgs, TContext, TResult>,
  ): (args: TArgs, ctx: TContext) => Promise<TResult> {
    return async (args: TArgs, ctx: TContext): Promise<TResult> => {
      const normalized = this.normalizeContext(ctx);
      const traceId = this.createTraceId();
      const state: ToolExecutionState = {
        traceId,
        idPrefix: safeIdentifier(`${name}-${traceId}`),
        startedAt: this.now(),
        toolName: name,
        toolKind: spec.kind,
        toolScope: spec.scope,
        approvalRequired: spec.approvalRequired ?? spec.approval_required ?? false,
        argsShape: argumentShape(args),
        context: normalized,
        queries: [],
      };

      return await this.storage.run(state, async () => {
        let result: TResult | undefined;
        let capturedError: unknown;
        try {
          result = await spec.handler(args, ctx);
          return result;
        } catch (error) {
          capturedError = error;
          throw error;
        } finally {
          const resultTrace =
            result === undefined
              ? undefined
              : spec.describeResult?.(result) ?? summarizeResult(result, this.redaction);
          const mutation = result === undefined ? undefined : spec.describeMutation?.(args, result);
          this.flushToolExecution(state, resultTrace, mutation, capturedError);
        }
      });
    };
  }

  captureQuery(input: string | PolicyStrataQueryInput | unknown): PolicyStrataSqlAnalysis {
    const queryInput = normalizeQueryInput(input);
    const sql = queryInput.sql ?? queryInput.query;
    if (!sql) {
      const analysis = analyzeSql("", this.tenancy, false, Boolean(queryInput.privileged), this.redaction);
      const state = this.storage.getStore();
      if (state) {
        state.queries.push({ input: queryInput, analysis });
      }
      return analysis;
    }
    const analysis = analyzeSql(
      sql,
      this.tenancy,
      true,
      Boolean(queryInput.privileged),
      this.redaction,
      queryInput.privilegedReason ?? queryInput.privileged_reason,
    );
    const state = this.storage.getStore();
    if (state) {
      state.queries.push({ input: queryInput, analysis });
    }
    return analysis;
  }

  recordQuery(
    input: string | PolicyStrataQueryInput | unknown,
    ctx?: PolicyStrataExecutionContext,
  ): PolicyStrataTraceRecord {
    const queryInput = normalizeQueryInput(input);
    const sql = queryInput.sql ?? queryInput.query ?? "";
    const context = this.normalizeContext(ctx);
    const analysis = analyzeSql(
      sql,
      this.tenancy,
      true,
      Boolean(queryInput.privileged),
      this.redaction,
      queryInput.privilegedReason ?? queryInput.privileged_reason ?? context.privilegedReason,
    );
    const resultTrace =
      queryInput.result === undefined ? undefined : summarizeResult(queryInput.result, this.redaction);
    const record = this.buildRecord({
      id: safeIdentifier(`sql-${this.createTraceId()}`),
      recordType: "sql_trace",
      context,
      sql: analysis.sql,
      query: analysis,
      result: resultTrace,
      releaseAllowed: queryInput.releaseAllowed ?? queryInput.release_allowed ?? context.releaseAllowed,
      semanticIr: queryInput.semanticIr ?? queryInput.semantic_ir ?? context.semanticIr,
    });
    this.writeRecord(record);
    return record;
  }

  recordSession(input: PolicyStrataSessionTrace): PolicyStrataTraceRecord {
    const context = this.normalizeContext(input);
    const sessionId = input.sessionId ?? input.session_id ?? context.sessionId ?? this.createTraceId();
    const promptText = input.promptText ?? input.prompt_text;
    const record = this.buildRecord({
      id: safeIdentifier(`session-${sessionId}`),
      recordType: "agent_session",
      context: { ...context, sessionId },
      agentSession: pruneUndefined({
        session_id: sessionId,
        prompt_class: input.promptClass ?? input.prompt_class,
        prompt_text: this.redaction.includePromptText ? promptText : undefined,
        model: input.model,
        tools_available: input.toolsAvailable ?? input.tools_available,
        tools_called: input.toolsCalled ?? input.tools_called,
        write_tools_enabled: input.writeToolsEnabled ?? input.write_tools_enabled,
        approval_policy: input.approvalPolicy ?? input.approval_policy,
      }),
    });
    this.writeRecord(record);
    return record;
  }

  recordMutation(
    mutation: PolicyStrataMutationTrace,
    ctx?: PolicyStrataExecutionContext,
    audit?: PolicyStrataAuditTrace,
  ): PolicyStrataTraceRecord {
    const context = this.normalizeContext(ctx);
    const record = this.buildRecord({
      id: safeIdentifier(`mutation-${this.createTraceId()}`),
      recordType: "mutation",
      context,
      mutation,
      audit,
    });
    this.writeRecord(record);
    return record;
  }

  recordAudit(audit: PolicyStrataAuditTrace, ctx?: PolicyStrataExecutionContext): PolicyStrataTraceRecord {
    return this.recordMutation({}, ctx, audit);
  }

  recordDrizzleQuery(query: unknown, ctx?: PolicyStrataExecutionContext): PolicyStrataSqlAnalysis {
    const input = normalizeQueryInput(query);
    if (ctx) {
      this.recordQuery(input, ctx);
    } else {
      this.captureQuery(input);
    }
    return analyzeSql(input.sql ?? input.query ?? "", this.tenancy, true, false, this.redaction);
  }

  wrapDrizzleClient<T extends object>(
    client: T,
    contextProvider?: () => PolicyStrataExecutionContext | undefined,
  ): T {
    return this.wrapObject(client, contextProvider, new WeakMap<object, object>()) as T;
  }

  analyzeSql(sql: string, privileged = false, privilegedReason?: string): PolicyStrataSqlAnalysis {
    return analyzeSql(sql, this.tenancy, true, privileged, this.redaction, privilegedReason);
  }

  private flushToolExecution(
    state: ToolExecutionState,
    result: PolicyStrataResultTrace | undefined,
    mutation: PolicyStrataMutationTrace | undefined,
    error: unknown,
  ): void {
    if (state.queries.length === 0 || state.toolKind === "write") {
      const record = this.toolExecutionRecord(state, result, mutation, error);
      this.writeRecord(record);
      return;
    }

    state.queries.forEach((captured, index) => {
      const query = { ...captured.analysis, query_index: index };
      const record = this.buildRecord({
        id: safeIdentifier(`${state.idPrefix}-q${index + 1}`),
        traceId: state.traceId,
        recordType: "sql_trace",
        context: state.context,
        tool: {
          name: state.toolName,
          kind: state.toolKind,
          scope: state.toolScope,
          approval_required: state.approvalRequired,
        },
        authorization: this.authorizationForTool(state),
        sql: captured.analysis.sql,
        query,
        result,
        error: errorRecord(error),
        argumentShape: state.argsShape,
        releaseAllowed:
          captured.input.releaseAllowed ?? captured.input.release_allowed ?? state.context.releaseAllowed,
        semanticIr: captured.input.semanticIr ?? captured.input.semantic_ir ?? state.context.semanticIr,
      });
      this.writeRecord(record);
    });
  }

  private toolExecutionRecord(
    state: ToolExecutionState,
    result: PolicyStrataResultTrace | undefined,
    mutation: PolicyStrataMutationTrace | undefined,
    error: unknown,
  ): PolicyStrataTraceRecord {
    const captured = state.queries[0];
    return this.buildRecord({
      id: safeIdentifier(state.idPrefix),
      traceId: state.traceId,
      recordType: state.toolKind === "write" ? "mutation" : "tool_execution",
      context: state.context,
      tool: {
        name: state.toolName,
        kind: state.toolKind,
        scope: state.toolScope,
        approval_required: state.approvalRequired,
      },
      authorization: this.authorizationForTool(state),
      query: captured?.analysis,
      result,
      mutation,
      error: errorRecord(error),
      argumentShape: state.argsShape,
    });
  }

  private authorizationForTool(state: ToolExecutionState): PolicyStrataAuthorization {
    return pruneUndefined({
      ...state.context.authorization,
      household_actor_required: state.toolScope === "household",
      write_context_required: state.toolKind === "write",
      approval_required: state.approvalRequired,
      approval_token_present: state.context.authorization.approval_token_present,
      actor_role: state.context.actor?.role,
    }) as PolicyStrataAuthorization;
  }

  private buildRecord(input: {
    id: string;
    traceId?: string;
    recordType: PolicyStrataTraceRecord["record_type"];
    context: NormalizedContext;
    sql?: string;
    tool?: PolicyStrataTraceRecord["tool"];
    authorization?: PolicyStrataAuthorization;
    query?: PolicyStrataTraceRecord["query"];
    result?: PolicyStrataResultTrace;
    mutation?: PolicyStrataMutationTrace;
    audit?: PolicyStrataAuditTrace;
    error?: PolicyStrataTraceRecord["error"];
    argumentShape?: unknown;
    agentSession?: Record<string, unknown>;
    releaseAllowed?: boolean;
    semanticIr?: Record<string, unknown>;
  }): PolicyStrataTraceRecord {
    return pruneUndefined({
      id: input.id,
      record_type: input.recordType,
      version: "policystrata.node.trace.v1",
      source: this.options.source ?? DEFAULT_SOURCE,
      timestamp: this.now().toISOString(),
      service: this.options.service,
      environment: this.options.environment,
      trace_id: input.traceId ?? input.id,
      session_id: input.context.sessionId,
      principal: input.context.principal,
      tenant_ids: input.context.tenantIds,
      release_allowed: input.releaseAllowed ?? input.context.releaseAllowed,
      sql: input.sql,
      semantic_ir: input.semanticIr ?? input.context.semanticIr,
      expected_policy: input.context.expectedPolicy,
      actor: input.context.actor,
      tool: input.tool,
      authorization: input.authorization ?? input.context.authorization,
      query: input.query,
      result: input.result,
      mutation: input.mutation,
      audit: input.audit,
      argument_shape: input.argumentShape,
      agent_session: input.agentSession,
      error: input.error,
    }) as PolicyStrataTraceRecord;
  }

  private normalizeContext(ctx?: unknown): NormalizedContext {
    const merged = mergePolicyStrataContext(ctx);
    const actor = normalizeActor(valueAsRecord(merged.actor));
    const tenantIds = stringArray(merged.tenantIds ?? merged.tenant_ids ?? this.options.tenantIds);
    const actorTenant = actor?.household_id ?? actor?.organization_id;
    const rawTenantIds = tenantIds.length > 0 ? tenantIds : actorTenant ? [actorTenant] : [];
    const authorization = valueAsRecord(merged.authorization) as PolicyStrataAuthorization | undefined;
    const approvalToken = merged.approvalToken ?? merged.approval_token;
    const privilegedReason = stringValue(merged.privilegedReason ?? merged.privileged_reason);

    return {
      sessionId: stringValue(merged.sessionId ?? merged.session_id),
      principal:
        stringValue(merged.principal) ??
        this.options.principal ??
        actor?.role ??
        (this.redaction.hashIds ? "redacted_principal" : undefined),
      tenantIds: rawTenantIds.map((id) => this.redactId(id)),
      actor: actor ? this.redactActor(actor) : undefined,
      semanticIr: recordValue(merged.semanticIr ?? merged.semantic_ir),
      releaseAllowed: booleanValue(merged.releaseAllowed ?? merged.release_allowed),
      authorization: pruneUndefined({
        ...authorization,
        approval_token_present:
          booleanValue(authorization?.approval_token_present) ?? approvalToken !== undefined,
        privileged_reason: privilegedReason,
      }) as PolicyStrataAuthorization,
      expectedPolicy: recordValue(merged.expectedPolicy ?? merged.expected_policy),
      privilegedReason,
    };
  }

  private redactActor(actor: PolicyStrataActor): PolicyStrataActor {
    return pruneUndefined({
      user_id: actor.user_id ? this.redactId(actor.user_id) : undefined,
      household_id: actor.household_id ? this.redactId(actor.household_id) : undefined,
      organization_id: actor.organization_id ? this.redactId(actor.organization_id) : undefined,
      role: actor.role,
    }) as PolicyStrataActor;
  }

  private redactId(value: string): string {
    if (!this.redaction.hashIds || this.redaction.safeFields.includes(value)) {
      return value;
    }
    return hashValue(value, this.redaction.hashSalt);
  }

  private writeRecord(record: PolicyStrataTraceRecord): void {
    this.options.writer?.(record);
    if (!this.options.out) {
      return;
    }
    mkdirSync(dirname(this.options.out), { recursive: true });
    appendFileSync(this.options.out, `${JSON.stringify(record)}\n`, "utf8");
  }

  private wrapObject(
    target: object,
    contextProvider: (() => PolicyStrataExecutionContext | undefined) | undefined,
    seen: WeakMap<object, object>,
  ): object {
    const cached = seen.get(target);
    if (cached) {
      return cached;
    }
    const recorder = this;
    const proxy = new Proxy(target, {
      get(rawTarget, prop, receiver) {
        const value = Reflect.get(rawTarget, prop, receiver) as unknown;
        if (typeof value !== "function") {
          return isPlainObject(value) ? recorder.wrapObject(value, contextProvider, seen) : value;
        }
        return function wrappedMethod(this: unknown, ...args: unknown[]) {
          const result = value.apply(rawTarget, args) as unknown;
          if (prop === "transaction" && typeof args[0] === "function") {
            return result;
          }
          recorder.captureSqlFromMethod(rawTarget, prop, args, contextProvider);
          return recorder.wrapPotentialQuery(result, contextProvider, seen);
        };
      },
    });
    seen.set(target, proxy);
    return proxy;
  }

  private wrapPotentialQuery(
    value: unknown,
    contextProvider: (() => PolicyStrataExecutionContext | undefined) | undefined,
    seen: WeakMap<object, object>,
  ): unknown {
    if (!isObject(value)) {
      return value;
    }
    if (typeof value.toSQL === "function" || typeof value.execute === "function" || typeof value.then === "function") {
      return this.wrapExecutableQuery(value, contextProvider);
    }
    return this.wrapObject(value, contextProvider, seen);
  }

  private wrapExecutableQuery(
    query: Record<string, unknown>,
    contextProvider: (() => PolicyStrataExecutionContext | undefined) | undefined,
  ): object {
    const recorder = this;
    let captured = false;
    const capture = (): void => {
      if (captured) {
        return;
      }
      captured = true;
      const ctx = contextProvider?.();
      if (ctx) {
        recorder.recordQuery(query, ctx);
      } else {
        recorder.captureQuery(query);
      }
    };
    return new Proxy(query, {
      get(rawTarget, prop, receiver) {
        const value = Reflect.get(rawTarget, prop, receiver) as unknown;
        if ((prop === "execute" || prop === "then") && typeof value === "function") {
          return function wrappedExecute(this: unknown, ...args: unknown[]) {
            capture();
            return value.apply(rawTarget, args) as unknown;
          };
        }
        return value;
      },
    });
  }

  private captureSqlFromMethod(
    target: object,
    prop: string | symbol,
    args: unknown[],
    contextProvider: (() => PolicyStrataExecutionContext | undefined) | undefined,
  ): void {
    if (!["execute", "all", "get", "values", "run"].includes(String(prop))) {
      return;
    }
    const candidate = normalizeQueryInput(args[0] ?? target);
    if (!candidate.sql && !candidate.query) {
      return;
    }
    const ctx = contextProvider?.();
    if (ctx) {
      this.recordQuery(candidate, ctx);
    } else {
      this.captureQuery(candidate);
    }
  }

  private createTraceId(): string {
    return this.options.uuid?.() ?? randomUUID();
  }

  private now(): Date {
    return this.options.now?.() ?? new Date();
  }
}

export function createPolicyStrataRecorder(options: PolicyStrataRecorderOptions): PolicyStrataRecorder {
  return new PolicyStrataRecorder(options);
}

export function analyzePolicyStrataSql(
  sql: string,
  options: {
    tenancy?: PolicyStrataTenancyConfig;
    redaction?: PolicyStrataRedactionConfig;
    privileged?: boolean;
    privilegedReason?: string;
  } = {},
): PolicyStrataSqlAnalysis {
  return analyzeSql(
    sql,
    {
      tenantColumns: options.tenancy?.tenantColumns ?? [],
      tenantKeys: options.tenancy?.tenantKeys ?? DEFAULT_TENANT_KEYS,
      tenantTables: options.tenancy?.tenantTables ?? tablesFromTenantColumns(options.tenancy?.tenantColumns ?? []),
    },
    true,
    Boolean(options.privileged),
    {
      hashIds: true,
      hashSalt: "policystrata",
      includePromptText: false,
      includeSqlValues: false,
      includeResultRows: false,
      safeFields: [],
      idFields: DEFAULT_ID_FIELDS,
      ...options.redaction,
    },
    options.privilegedReason,
  );
}

function analyzeSql(
  sql: string,
  tenancy: Required<PolicyStrataTenancyConfig>,
  parseSql: boolean,
  privileged: boolean,
  redaction: Required<PolicyStrataRedactionConfig>,
  privilegedReason?: string,
): PolicyStrataSqlAnalysis {
  const normalizedSql = normalizeSqlForTrace(sql, redaction);
  const tables = parseSql ? extractTables(normalizedSql) : [];
  const selectedColumns = parseSql ? extractSelectedColumns(normalizedSql) : [];
  const tenantPredicates = parseSql ? extractTenantPredicates(normalizedSql, tenancy) : [];
  const warnings: PolicyStrataSqlWarning[] = [];
  const rawSqlUnparseable = parseSql && normalizedSql.trim() !== "" && tables.length === 0;
  if (rawSqlUnparseable) {
    warnings.push({
      code: "raw_sql_unparseable",
      message: "SQL could not be normalized into tables and predicates by the Node recorder",
    });
  }

  const tenantTables = new Set(tenancy.tenantTables.map((table) => table.toLowerCase()));
  const observedTenantTables = tables.filter((table) => tenantTables.has(unquoteIdentifier(table).toLowerCase()));
  const hasTenantPredicate = tenantPredicates.length > 0;
  for (const table of observedTenantTables) {
    const tableHasPredicate = tenantPredicates.some((predicate) =>
      predicate.toLowerCase().startsWith(`${unquoteIdentifier(table).toLowerCase()}.`),
    );
    if (!tableHasPredicate && !hasTenantPredicate) {
      warnings.push({
        code: "tenant_table_without_tenant_predicate",
        table,
        message: `tenant table ${table} was read without a visible tenant predicate`,
      });
    }
    if (normalizedSql.toLowerCase().includes(` join ${table.toLowerCase()}`) && !tableHasPredicate) {
      warnings.push({
        code: "tenant_join_without_scoped_condition",
        table,
        message: `join to tenant table ${table} does not expose a scoped join or where predicate`,
      });
    }
  }
  if (SQL_AGGREGATE_PATTERN.test(normalizedSql) && observedTenantTables.length > 0 && !hasTenantPredicate) {
    warnings.push({
      code: "aggregate_without_tenant_predicate",
      table: observedTenantTables[0],
      message: "aggregate over tenant table has no visible tenant predicate",
    });
  }
  if (privileged && !privilegedReason) {
    warnings.push({
      code: "privileged_client_without_reason",
      message: "query was executed through a privileged client without a declared reason",
    });
  }

  return {
    sql: normalizedSql,
    tables,
    selected_columns: selectedColumns,
    tenant_predicates: tenantPredicates,
    warnings,
    raw_sql_unparseable: rawSqlUnparseable,
  };
}

function normalizeQueryInput(input: unknown): PolicyStrataQueryInput {
  if (typeof input === "string") {
    return { sql: input };
  }
  if (!isObject(input)) {
    return {};
  }
  const direct = input as PolicyStrataQueryInput;
  const fromToSql = callSqlMethod(input, "toSQL");
  if (fromToSql) {
    return { ...direct, ...fromToSql };
  }
  const fromToQuery = callSqlMethod(input, "toQuery");
  if (fromToQuery) {
    return { ...direct, ...fromToQuery };
  }
  return {
    ...direct,
    sql: typeof direct.sql === "string" ? direct.sql : stringValue(input.sql),
    query: typeof direct.query === "string" ? direct.query : stringValue(input.query),
  };
}

function callSqlMethod(input: Record<string, unknown>, method: string): PolicyStrataQueryInput | undefined {
  const candidate = input[method];
  if (typeof candidate !== "function") {
    return undefined;
  }
  try {
    const value = candidate.call(input) as unknown;
    if (typeof value === "string") {
      return { sql: value };
    }
    if (!isObject(value)) {
      return undefined;
    }
    return {
      sql: stringValue(value.sql ?? value.text),
      query: stringValue(value.query),
      params: Array.isArray(value.params) ? value.params : undefined,
    };
  } catch {
    return undefined;
  }
}

function normalizeSqlForTrace(sql: string, redaction: Required<PolicyStrataRedactionConfig>): string {
  const compact = sql.replace(/\s+/g, " ").trim();
  if (redaction.includeSqlValues) {
    return compact;
  }
  return compact
    .replace(/'(?:''|[^'])*'/g, "?")
    .replace(/\b(true|false)\b/gi, "?")
    .replace(/(?<![$A-Za-z0-9_])\d+(?:\.\d+)?\b/g, "?");
}

function extractTables(sql: string): string[] {
  const tables = new Set<string>();
  for (const match of sql.matchAll(/\b(?:from|join|update|into)\s+((?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)(?:\.(?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*))?)/gi)) {
    const table = match[1];
    if (table) {
      tables.add(unquoteIdentifier(table.split(".").at(-1) ?? table));
    }
  }
  return [...tables].sort();
}

function extractSelectedColumns(sql: string): string[] {
  const match = /^\s*select\s+(.+?)\s+from\s+/i.exec(sql);
  if (!match?.[1]) {
    return [];
  }
  const selected = splitTopLevel(match[1])
    .map((item) => item.replace(/\s+as\s+.+$/i, "").trim())
    .filter(Boolean);
  return [...new Set(selected)].sort();
}

function extractTenantPredicates(
  sql: string,
  tenancy: Required<PolicyStrataTenancyConfig>,
): string[] {
  const candidates = new Set([...tenancy.tenantColumns, ...tenancy.tenantKeys]);
  const predicates = new Set<string>();
  for (const candidate of candidates) {
    const escaped = escapeRegExp(candidate);
    const pattern = new RegExp(`(?<![A-Za-z0-9_.])(${escaped})(?![A-Za-z0-9_])\\s*(?:=|in\\b|is\\b)`, "gi");
    for (const match of sql.matchAll(pattern)) {
      if (match[1]) {
        predicates.add(unquoteIdentifier(match[1]));
      }
    }
  }
  for (const key of tenancy.tenantKeys) {
    const escaped = escapeRegExp(key);
    const pattern = new RegExp(
      `(?<![A-Za-z0-9_.])((?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\\.${escaped})(?![A-Za-z0-9_])\\s*(?:=|in\\b|is\\b)`,
      "gi",
    );
    for (const match of sql.matchAll(pattern)) {
      if (match[1]) {
        predicates.add(unquoteIdentifier(match[1]));
      }
    }
  }
  return [...predicates].sort();
}

function splitTopLevel(input: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let current = "";
  for (const char of input) {
    if (char === "(") {
      depth += 1;
    } else if (char === ")") {
      depth = Math.max(0, depth - 1);
    }
    if (char === "," && depth === 0) {
      parts.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  if (current.trim()) {
    parts.push(current);
  }
  return parts;
}

function summarizeResult(result: unknown, redaction: Required<PolicyStrataRedactionConfig>): PolicyStrataResultTrace {
  const rows = rowsFromResult(result);
  const fields = fieldsFromRows(rows, result);
  return pruneUndefined({
    row_count: rowCountFromResult(result, rows),
    fields_returned: fields,
    contains_sensitive_values: fields.some((field) => SENSITIVE_FIELD_PATTERN.test(field)),
    rows: redaction.includeResultRows ? result : undefined,
  }) as PolicyStrataResultTrace;
}

function rowsFromResult(result: unknown): Record<string, unknown>[] {
  if (Array.isArray(result)) {
    return result.filter(isObject);
  }
  if (!isObject(result)) {
    return [];
  }
  const maybeRows = result.rows;
  if (Array.isArray(maybeRows)) {
    return maybeRows.filter(isObject);
  }
  return [];
}

function fieldsFromRows(rows: Record<string, unknown>[], result: unknown): string[] {
  if (isObject(result) && Array.isArray(result.fields)) {
    return result.fields
      .map((field) => {
        if (typeof field === "string") {
          return field;
        }
        return isObject(field) ? stringValue(field.name) : undefined;
      })
      .filter((field): field is string => Boolean(field))
      .sort();
  }
  const fields = new Set<string>();
  for (const row of rows) {
    Object.keys(row).forEach((key) => fields.add(key));
  }
  return [...fields].sort();
}

function rowCountFromResult(result: unknown, rows: Record<string, unknown>[]): number | undefined {
  if (Array.isArray(result)) {
    return result.length;
  }
  if (isObject(result)) {
    const explicit = result.rowCount ?? result.row_count;
    if (typeof explicit === "number") {
      return explicit;
    }
  }
  return rows.length > 0 ? rows.length : undefined;
}

function argumentShape(value: unknown): unknown {
  if (value === null) {
    return { type: "null" };
  }
  if (Array.isArray(value)) {
    return {
      type: "array",
      length: value.length,
      items: value.length > 0 ? argumentShape(value[0]) : undefined,
    };
  }
  if (isObject(value)) {
    return {
      type: "object",
      fields: Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, argumentShape(value[key])]),
      ),
    };
  }
  return { type: typeof value };
}

function mergePolicyStrataContext(ctx: unknown): Record<string, unknown> {
  if (!isObject(ctx)) {
    return {};
  }
  const nested = isObject(ctx.policystrata) ? ctx.policystrata : {};
  return { ...ctx, ...nested };
}

function normalizeActor(input?: Record<string, unknown>): PolicyStrataActor | undefined {
  if (!input) {
    return undefined;
  }
  return pruneUndefined({
    user_id: stringValue(input.user_id ?? input.userId),
    household_id: stringValue(input.household_id ?? input.householdId),
    organization_id: stringValue(input.organization_id ?? input.organizationId),
    role: stringValue(input.role),
  }) as PolicyStrataActor;
}

function hashValue(value: string, salt: string): string {
  return `sha256:${createHash("sha256").update(`${salt}:${value}`).digest("hex").slice(0, 24)}`;
}

function tablesFromTenantColumns(columns: string[]): string[] {
  return [
    ...new Set(
      columns
        .map((column) => column.split("."))
        .filter((parts) => parts.length > 1)
        .map((parts) => unquoteIdentifier(parts[parts.length - 2] ?? "")),
    ),
  ].filter(Boolean);
}

function safeIdentifier(value: string): string {
  const cleaned = value.replace(/[^A-Za-z0-9_.-]+/g, "-").replace(/^-+/, "");
  const withStart = /^[A-Za-z0-9]/.test(cleaned) ? cleaned : `trace-${cleaned}`;
  return (withStart || `trace-${randomUUID()}`).slice(0, 128);
}

function errorRecord(error: unknown): PolicyStrataTraceRecord["error"] | undefined {
  if (error === undefined) {
    return undefined;
  }
  if (error instanceof Error) {
    return { name: error.name, message: error.message };
  }
  return { name: "Error", message: String(error) };
}

function pruneUndefined<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => pruneUndefined(item)).filter((item) => item !== undefined) as T;
  }
  if (!isObject(value)) {
    return value;
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, item]) => item !== undefined)
      .map(([key, item]) => [key, pruneUndefined(item)]),
  ) as T;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => stringValue(item)).filter((item): item is string => Boolean(item));
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function booleanValue(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return isObject(value) ? value : undefined;
}

function valueAsRecord(value: unknown): Record<string, unknown> | undefined {
  return isObject(value) ? value : undefined;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return isObject(value) && Object.getPrototypeOf(value) === Object.prototype;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function unquoteIdentifier(value: string): string {
  return value.replace(/"/g, "");
}

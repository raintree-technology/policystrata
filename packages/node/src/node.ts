import { AsyncLocalStorage } from "node:async_hooks";
import { createHmac, randomUUID } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export type PolicyStrataToolKind = "read" | "write" | "memory" | "external";

export interface PolicyStrataRedactionConfig {
  hashIds?: boolean;
  hashSalt?: string;
  includeErrorMessages?: boolean;
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
  /(email|phone|ssn|social|token|secret|password|passwd|pwd|auth|authorization|cookie|credential|session|csrf|xsrf|dob|birth|address|account_number|routing_number|card|pan|pii)/i;
const LONG_NUMERIC_KEY_PATTERN = /\b\d{6,}\b/;
const SQL_AGGREGATE_PATTERN = /\b(count|sum|avg|min|max)\s*\(/i;
const SECRET_ASSIGNMENT_PATTERN =
  /\b(api[_-]?key|authorization|password|passwd|pwd|secret|token)\s*[:=]\s*([^\s,;]+)/gi;
const BEARER_TOKEN_PATTERN = /\bbearer\s+[A-Za-z0-9._~+/=-]+/gi;
const BASIC_AUTH_PATTERN = /\bbasic\s+[A-Za-z0-9+/=:_-]+/gi;
const URL_CREDENTIAL_PATTERN = /\b([A-Za-z][A-Za-z0-9+.-]*:\/\/)([^/@\s]+)@/g;
const AUTHORIZATION_BOOLEAN_FIELDS = [
  "consent_checked",
  "household_actor_required",
  "write_context_required",
  "write_tools_enabled",
  "approval_required",
  "approval_token_present",
] as const;
const AUTHORIZATION_STRING_FIELDS = ["actor_role", "privileged_reason"] as const;

export class PolicyStrataRecorder {
  private readonly options: Required<Pick<PolicyStrataRecorderOptions, "service">> &
    Omit<PolicyStrataRecorderOptions, "service">;
  private readonly redaction: Required<PolicyStrataRedactionConfig>;
  private readonly tenancy: Required<PolicyStrataTenancyConfig>;
  private readonly storage = new AsyncLocalStorage<ToolExecutionState>();

  constructor(options: PolicyStrataRecorderOptions) {
    this.options = options;
    const hashSalt = options.redaction?.hashSalt ?? randomUUID();
    this.redaction = {
      hashIds: true,
      hashSalt,
      includeErrorMessages: false,
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
        argsShape: argumentShape(args, this.redaction),
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
        error: errorRecord(error, this.redaction),
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
      error: errorRecord(error, this.redaction),
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
      tenant_ids: input.context.tenantIds.length > 0 ? input.context.tenantIds : undefined,
      release_allowed: input.releaseAllowed ?? input.context.releaseAllowed,
      sql: input.sql,
      semantic_ir: sanitizeSemanticIr(input.semanticIr ?? input.context.semanticIr, this.redaction),
      expected_policy: redactTraceValue(input.context.expectedPolicy, this.redaction),
      actor: input.context.actor,
      tool: input.tool,
      authorization: input.authorization ?? input.context.authorization,
      query: redactTraceValue(input.query, this.redaction) as PolicyStrataTraceRecord["query"],
      result: redactTraceValue(input.result, this.redaction) as PolicyStrataResultTrace | undefined,
      mutation: redactTraceValue(input.mutation, this.redaction),
      audit: redactTraceValue(input.audit, this.redaction),
      argument_shape: input.argumentShape,
      agent_session: redactTraceValue(input.agentSession, this.redaction) as Record<string, unknown> | undefined,
      error: input.error,
    }) as PolicyStrataTraceRecord;
  }

  private normalizeContext(ctx?: unknown): NormalizedContext {
    const merged = mergePolicyStrataContext(ctx);
    const actor = normalizeActor(valueAsRecord(merged.actor));
    const tenantIds = stringArray(merged.tenantIds ?? merged.tenant_ids ?? this.options.tenantIds);
    const actorTenant = actor?.household_id ?? actor?.organization_id;
    const rawTenantIds = tenantIds.length > 0 ? tenantIds : actorTenant ? [actorTenant] : [];
    const authorization = sanitizeAuthorization(valueAsRecord(merged.authorization), this.redaction);
    const approvalToken = merged.approvalToken ?? merged.approval_token;
    const privilegedReason = stringValue(merged.privilegedReason ?? merged.privileged_reason);
    const authorizationPrivilegedReason =
      privilegedReason ?? stringValue(authorization.privileged_reason);

    return {
      sessionId: stringValue(merged.sessionId ?? merged.session_id),
      principal:
        stringValue(merged.principal) ??
        this.options.principal ??
        actor?.role ??
        (this.redaction.hashIds ? "redacted_principal" : undefined),
      tenantIds: this.redaction.hashIds ? [] : rawTenantIds,
      actor: actor ? this.redactActor(actor) : undefined,
      semanticIr: recordValue(merged.semanticIr ?? merged.semantic_ir),
      releaseAllowed: booleanValue(merged.releaseAllowed ?? merged.release_allowed),
      authorization: pruneUndefined({
        ...authorization,
        approval_token_present:
          booleanValue(authorization?.approval_token_present) ?? approvalToken !== undefined,
        privileged_reason: authorizationPrivilegedReason,
      }) as PolicyStrataAuthorization,
      expectedPolicy: recordValue(merged.expectedPolicy ?? merged.expected_policy),
      privilegedReason: authorizationPrivilegedReason,
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
          if (prop === "transaction" && typeof args[0] === "function") {
            const callback = args[0] as (...callbackArgs: unknown[]) => unknown;
            const wrappedArgs = [...args];
            wrappedArgs[0] = (tx: unknown, ...callbackArgs: unknown[]) =>
              callback(recorder.wrapTransactionClient(tx, contextProvider, seen), ...callbackArgs);
            return value.apply(rawTarget, wrappedArgs) as unknown;
          }
          const result = value.apply(rawTarget, args) as unknown;
          recorder.captureSqlFromMethod(rawTarget, prop, args, contextProvider);
          return recorder.wrapPotentialQuery(result, contextProvider, seen);
        };
      },
    });
    seen.set(target, proxy);
    return proxy;
  }

  private wrapTransactionClient(
    tx: unknown,
    contextProvider: (() => PolicyStrataExecutionContext | undefined) | undefined,
    seen: WeakMap<object, object>,
  ): unknown {
    return isObject(tx) ? this.wrapObject(tx, contextProvider, seen) : tx;
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
      hashSalt: options.redaction?.hashSalt ?? randomUUID(),
      includeErrorMessages: false,
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
  const compact = stripSqlComments(sql).replace(/\s+/g, " ").trim();
  if (redaction.includeSqlValues) {
    return sanitizeSecretTokens(compact);
  }
  return sanitizeSecretTokens(
    redactSqlDollarQuotedLiterals(compact)
      .replace(/'(?:''|[^'])*'/g, "?")
      .replace(/\b(true|false)\b/gi, "?")
      .replace(/(?<![$A-Za-z0-9_])\d+(?:\.\d+)?\b/g, "?"),
  );
}

function redactSqlDollarQuotedLiterals(sql: string): string {
  let output = "";
  let i = 0;
  while (i < sql.length) {
    const tag = readDollarQuoteTag(sql, i);
    if (!tag) {
      output += sql[i];
      i += 1;
      continue;
    }
    const end = sql.indexOf(tag, i + tag.length);
    output += "?";
    i = end === -1 ? sql.length : end + tag.length;
  }
  return output;
}

function stripSqlComments(sql: string): string {
  let output = "";
  let i = 0;
  let inSingleQuote = false;
  let inDoubleQuote = false;
  let dollarQuoteTag: string | undefined;

  while (i < sql.length) {
    if (dollarQuoteTag) {
      if (sql.startsWith(dollarQuoteTag, i)) {
        output += dollarQuoteTag;
        i += dollarQuoteTag.length;
        dollarQuoteTag = undefined;
        continue;
      }
      output += sql[i];
      i += 1;
      continue;
    }

    const char = sql[i];
    const next = sql[i + 1];

    if (inSingleQuote) {
      output += char;
      if (char === "'" && next === "'") {
        output += next;
        i += 2;
        continue;
      }
      if (char === "'") {
        inSingleQuote = false;
      }
      i += 1;
      continue;
    }

    if (inDoubleQuote) {
      output += char;
      if (char === '"') {
        inDoubleQuote = false;
      }
      i += 1;
      continue;
    }

    if (char === "-" && next === "-") {
      output += " ";
      i += 2;
      while (i < sql.length && sql[i] !== "\n" && sql[i] !== "\r") {
        i += 1;
      }
      continue;
    }

    if (char === "/" && next === "*") {
      output += " ";
      i += 2;
      while (i < sql.length && !(sql[i] === "*" && sql[i + 1] === "/")) {
        i += 1;
      }
      i = Math.min(i + 2, sql.length);
      continue;
    }

    if (char === "'") {
      inSingleQuote = true;
      output += char;
      i += 1;
      continue;
    }

    if (char === '"') {
      inDoubleQuote = true;
      output += char;
      i += 1;
      continue;
    }

    if (char === "$") {
      const tag = readDollarQuoteTag(sql, i);
      if (tag) {
        dollarQuoteTag = tag;
        output += tag;
        i += tag.length;
        continue;
      }
    }

    output += char;
    i += 1;
  }

  return output;
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
  const fields = fieldsFromRows(rows, result, redaction);
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

function fieldsFromRows(
  rows: Record<string, unknown>[],
  result: unknown,
  redaction: Required<PolicyStrataRedactionConfig>,
): string[] {
  if (isObject(result) && Array.isArray(result.fields)) {
    return result.fields
      .map((field) => {
        if (typeof field === "string") {
          return sanitizeTraceKey(field, redaction);
        }
        const name = isObject(field) ? stringValue(field.name) : undefined;
        return name ? sanitizeTraceKey(name, redaction) : undefined;
      })
      .filter((field): field is string => Boolean(field))
      .sort();
  }
  const fields = new Set<string>();
  for (const row of rows) {
    Object.keys(row).forEach((key) => fields.add(sanitizeTraceKey(key, redaction)));
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

function argumentShape(value: unknown, redaction: Required<PolicyStrataRedactionConfig>): unknown {
  if (value === null) {
    return { type: "null" };
  }
  if (Array.isArray(value)) {
    return {
      type: "array",
      length: value.length,
      items: value.length > 0 ? argumentShape(value[0], redaction) : undefined,
    };
  }
  if (isObject(value)) {
    return {
      type: "object",
      fields: Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [sanitizeTraceKey(key, redaction), argumentShape(value[key], redaction)]),
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

function sanitizeAuthorization(
  input: Record<string, unknown> | undefined,
  redaction: Required<PolicyStrataRedactionConfig>,
): PolicyStrataAuthorization {
  if (!input) {
    return {};
  }
  const output: Record<string, unknown> = {};
  for (const field of AUTHORIZATION_BOOLEAN_FIELDS) {
    const value = booleanValue(input[field]);
    if (value !== undefined) {
      output[field] = value;
    }
  }
  for (const field of AUTHORIZATION_STRING_FIELDS) {
    const value = stringValue(input[field]);
    if (value !== undefined) {
      output[field] = sanitizeTraceString(value, redaction);
    }
  }
  return output as PolicyStrataAuthorization;
}

function sanitizeSemanticIr(
  value: Record<string, unknown> | undefined,
  redaction: Required<PolicyStrataRedactionConfig>,
): Record<string, unknown> | undefined {
  if (!value) {
    return undefined;
  }
  const redacted = redactTraceValue(value, redaction);
  if (!isObject(redacted)) {
    return undefined;
  }
  return redacted;
}

function redactTraceValue(
  value: unknown,
  redaction: Required<PolicyStrataRedactionConfig>,
  key?: string,
): unknown {
  if (key && redaction.hashIds && isIdLikeTraceKey(key, redaction)) {
    if (Array.isArray(value)) {
      return value.map((item) =>
        typeof item === "string" ? hashValue(item, redaction.hashSalt) : "[redacted]",
      );
    }
    if (typeof value === "string") {
      return hashValue(value, redaction.hashSalt);
    }
    return "[redacted]";
  }
  if (key && isSensitiveTraceKey(key)) {
    return "[redacted]";
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactTraceValue(item, redaction, key));
  }
  if (isObject(value)) {
    return redactTraceObject(value, redaction);
  }
  if (typeof value === "string") {
    return sanitizeTraceString(value, redaction);
  }
  return value;
}

function redactTraceObject(
  value: Record<string, unknown>,
  redaction: Required<PolicyStrataRedactionConfig>,
): Record<string, unknown> {
  const output: Record<string, unknown> = {};
  const seen = new Map<string, number>();
  for (const [itemKey, item] of Object.entries(value)) {
    const sanitizedKey = sanitizeTraceKey(itemKey, redaction);
    const count = (seen.get(sanitizedKey) ?? 0) + 1;
    seen.set(sanitizedKey, count);
    const outputKey = count === 1 ? sanitizedKey : `${sanitizedKey}_${count}`;
    output[outputKey] = redactTraceValue(item, redaction, itemKey);
  }
  return output;
}

function isIdLikeTraceKey(key: string, redaction: Required<PolicyStrataRedactionConfig>): boolean {
  return (
    redaction.idFields.includes(key) ||
    /(^|_)(id|ids)$/i.test(key) ||
    /[A-Za-z0-9](?:Id|Ids|ID|IDs)$/.test(key)
  );
}

function isSensitiveTraceKey(key: string): boolean {
  return (
    SENSITIVE_FIELD_PATTERN.test(key) ||
    LONG_NUMERIC_KEY_PATTERN.test(key) ||
    containsEmailLikeValue(key)
  );
}

function sanitizeTraceKey(key: string, redaction: Required<PolicyStrataRedactionConfig>): string {
  if (isSensitiveTraceKey(key)) {
    return "[redacted_key]";
  }
  if (redaction.hashIds && isIdLikeTraceKey(key, redaction)) {
    return hashValue(key, redaction.hashSalt);
  }
  return sanitizeTraceString(key, redaction);
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
  return `hmac-sha256:${createHmac("sha256", salt).update(value).digest("hex").slice(0, 24)}`;
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

function errorRecord(
  error: unknown,
  redaction: Required<PolicyStrataRedactionConfig>,
): PolicyStrataTraceRecord["error"] | undefined {
  if (error === undefined) {
    return undefined;
  }
  const rawMessage = error instanceof Error ? error.message : String(error);
  const message = redaction.includeErrorMessages
    ? sanitizeErrorMessage(rawMessage, redaction)
    : "redacted";
  if (error instanceof Error) {
    return { name: error.name, message };
  }
  return { name: "Error", message };
}

function sanitizeErrorMessage(
  message: string,
  redaction: Required<PolicyStrataRedactionConfig>,
): string {
  return sanitizeTraceString(message, redaction);
}

function sanitizeTraceString(
  message: string,
  redaction: Required<PolicyStrataRedactionConfig>,
): string {
  return sanitizeSecretTokens(normalizeSqlForTrace(message, redaction))
    .replace(URL_CREDENTIAL_PATTERN, "$1[redacted]@")
    .replace(BEARER_TOKEN_PATTERN, "Bearer [redacted]")
    .replace(BASIC_AUTH_PATTERN, "Basic [redacted]")
    .replace(SECRET_ASSIGNMENT_PATTERN, "$1=[redacted]")
    .slice(0, 512);
}

function sanitizeSecretTokens(message: string): string {
  return redactEmailLikeValues(message)
    .replace(URL_CREDENTIAL_PATTERN, "$1[redacted]@")
    .replace(BEARER_TOKEN_PATTERN, "Bearer [redacted]")
    .replace(SECRET_ASSIGNMENT_PATTERN, "$1=[redacted]")
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, "[redacted_token]")
    .replace(/\b(?:sk|pk|tok|key|secret|token)[_-]?[A-Za-z0-9._~+/=-]{8,}\b/gi, "[redacted_token]")
    .replace(/\b\d{8,}\b/g, "[redacted_number]");
}

function redactEmailLikeValues(message: string): string {
  let output = "";
  let last = 0;
  let i = 0;
  while (i < message.length) {
    if (message[i] !== "@") {
      i += 1;
      continue;
    }

    const start = emailLocalStart(message, i - 1);
    const end = emailDomainEnd(message, i + 1);
    if (start < i && end > i + 1 && emailDomainHasDotWithTld(message, i + 1, end)) {
      output += `${message.slice(last, start)}[redacted_email]`;
      last = end;
      i = end;
      continue;
    }

    i += 1;
  }
  return output + message.slice(last);
}

function containsEmailLikeValue(message: string): boolean {
  let i = 0;
  while (i < message.length) {
    if (message[i] !== "@") {
      i += 1;
      continue;
    }
    const start = emailLocalStart(message, i - 1);
    const end = emailDomainEnd(message, i + 1);
    if (start < i && end > i + 1 && emailDomainHasDotWithTld(message, i + 1, end)) {
      return true;
    }
    i += 1;
  }
  return false;
}

function emailLocalStart(message: string, index: number): number {
  let i = index;
  while (i >= 0 && isEmailLocalChar(message.charCodeAt(i))) {
    i -= 1;
  }
  return i + 1;
}

function emailDomainEnd(message: string, index: number): number {
  let i = index;
  while (i < message.length && isEmailDomainChar(message.charCodeAt(i))) {
    i += 1;
  }
  return i;
}

function emailDomainHasDotWithTld(message: string, start: number, end: number): boolean {
  const lastDot = message.lastIndexOf(".", end - 1);
  if (lastDot <= start || end - lastDot - 1 < 2) {
    return false;
  }
  for (let i = lastDot + 1; i < end; i += 1) {
    if (!isAsciiLetter(message.charCodeAt(i))) {
      return false;
    }
  }
  return true;
}

function readDollarQuoteTag(sql: string, start: number): string | undefined {
  if (sql[start] !== "$") {
    return undefined;
  }
  let i = start + 1;
  if (sql[i] === "$") {
    return "$$";
  }
  if (!isSqlIdentifierStart(sql.charCodeAt(i))) {
    return undefined;
  }
  i += 1;
  while (i < sql.length && isSqlIdentifierPart(sql.charCodeAt(i))) {
    i += 1;
  }
  return sql[i] === "$" ? sql.slice(start, i + 1) : undefined;
}

function isSqlIdentifierStart(code: number): boolean {
  return code === 95 || isAsciiLetter(code);
}

function isSqlIdentifierPart(code: number): boolean {
  return isSqlIdentifierStart(code) || isAsciiDigit(code);
}

function isEmailLocalChar(code: number): boolean {
  return (
    isAsciiLetter(code) ||
    isAsciiDigit(code) ||
    code === 37 ||
    code === 43 ||
    code === 45 ||
    code === 46 ||
    code === 95
  );
}

function isEmailDomainChar(code: number): boolean {
  return isAsciiLetter(code) || isAsciiDigit(code) || code === 45 || code === 46;
}

function isAsciiLetter(code: number): boolean {
  return (code >= 65 && code <= 90) || (code >= 97 && code <= 122);
}

function isAsciiDigit(code: number): boolean {
  return code >= 48 && code <= 57;
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

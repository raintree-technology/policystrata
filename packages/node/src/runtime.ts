import { isRecord, optionalProperty } from "./internal.js";

export type PolicyStrataRuntimeMode = "shadow" | "enforce";
export type PolicyStrataRuntimeDefaultDecision = "deny";
export type PolicyStrataRuntimeToolKind = "read" | "write" | "export" | "memory" | "external";
export type PolicyStrataRuntimeDecisionPoint = "pre_model" | "execution";
export type PolicyStrataRuntimeApprovalState = "not_required" | "pending" | "satisfied";
export type PolicyStrataRuntimeWriteState = "disabled" | "enabled";
export type PolicyStrataRuntimeEventAction =
  | "allow"
  | "deny"
  | "redact"
  | "require_approval"
  | "quarantine"
  | "log_only";
export type PolicyStrataPolicyLayer =
  | "auth_context"
  | "prompt"
  | "plan"
  | "retrieval"
  | "memory"
  | "tool_call"
  | "browser_action"
  | "code_execution"
  | "sql"
  | "database_rule"
  | "schema_binding"
  | "transformation"
  | "output_filter"
  | "egress"
  | "trace";

export const policyStrataRuntimeEventActions = [
  "allow",
  "deny",
  "redact",
  "require_approval",
  "quarantine",
  "log_only",
] as const satisfies readonly PolicyStrataRuntimeEventAction[];

export const policyStrataPolicyLayers = [
  "auth_context",
  "prompt",
  "plan",
  "retrieval",
  "memory",
  "tool_call",
  "browser_action",
  "code_execution",
  "sql",
  "database_rule",
  "schema_binding",
  "transformation",
  "output_filter",
  "egress",
  "trace",
] as const satisfies readonly PolicyStrataPolicyLayer[];

export interface PolicyStrataRuntimeSemanticIr {
  metric?: unknown;
  dimensions?: unknown;
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeSemanticConstraints {
  metrics?: readonly string[];
  dimensions?: readonly string[];
}

export interface PolicyStrataRuntimeReleaseConstraints {
  boundaries?: readonly string[];
  resultKinds?: readonly string[];
  lineageSources?: readonly string[];
  maxRows?: number;
  requireLineage?: boolean;
  allowSensitive?: boolean;
  allowRawRows?: boolean;
}

export interface PolicyStrataRuntimeAction {
  name: string;
  allowedRoles: readonly string[];
  kind?: PolicyStrataRuntimeToolKind | string;
  approvalRequired?: boolean;
  requiresWriteGrant?: boolean;
  semanticConstraints?: PolicyStrataRuntimeSemanticConstraints;
  releaseConstraints?: PolicyStrataRuntimeReleaseConstraints;
  metrics?: readonly string[];
  dimensions?: readonly string[];
  source?: string;
}

export interface PolicyStrataRuntimeResource {
  name: string;
  type?: string;
  actions: readonly PolicyStrataRuntimeAction[];
  source?: string;
}

export interface PolicyStrataRuntimeTool {
  name: string;
  kind: PolicyStrataRuntimeToolKind;
  allowedRoles: readonly string[];
  approvalRequired?: boolean;
  metrics?: readonly string[];
  dimensions?: readonly string[];
  source?: string;
}

export interface PolicyStrataRuntimeManifest {
  schemaVersion: string;
  version: string | number;
  roleAliases?: Record<string, string>;
  resources?: readonly PolicyStrataRuntimeResource[];
  tools?: readonly PolicyStrataRuntimeTool[];
  controls?: Record<string, unknown>;
  defaultDecision: PolicyStrataRuntimeDefaultDecision;
}

export interface PolicyStrataRuntimeSubject {
  id?: string;
  role?: string | null;
  roles?: readonly string[];
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeResourceRef {
  name?: string;
  id?: string;
  type?: string;
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeReleaseResult {
  kind?: string;
  rowCount?: number;
  containsSensitiveValues?: boolean;
  fields?: readonly string[];
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeReleaseLineage {
  sources?: readonly string[];
  containsRawRows?: boolean;
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeReleaseContext {
  boundary?: string;
  result?: PolicyStrataRuntimeReleaseResult | null;
  lineage?: PolicyStrataRuntimeReleaseLineage | null;
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeContext {
  allowWriteTools?: boolean;
  allow_write_tools?: boolean;
  approvalRequiredSatisfied?: boolean;
  approval_required_satisfied?: boolean;
  semanticIr?: PolicyStrataRuntimeSemanticIr | null;
  semantic_ir?: PolicyStrataRuntimeSemanticIr | null;
  release?: PolicyStrataRuntimeReleaseContext | null;
  [key: string]: unknown;
}

export interface PolicyStrataAuthorizeInput {
  subject?: PolicyStrataRuntimeSubject | string | null;
  action: string;
  resource: string | PolicyStrataRuntimeResourceRef;
  context?: PolicyStrataRuntimeContext | null;
  mode?: PolicyStrataRuntimeMode;
}

export interface PolicyStrataAuthorizeDecision {
  allowed: boolean;
  reasons: string[];
  action: string;
  resource: string;
  normalizedRoles: string[];
  manifestVersion: string;
  enforcementMode: PolicyStrataRuntimeMode;
}

export interface PolicyStrataAuthorizeToolInput {
  toolName: string;
  action?: string;
  userId?: string | null;
  householdId?: string | null;
  role?: string | null;
  toolKind?: PolicyStrataRuntimeToolKind | string | null;
  allowWriteTools?: boolean;
  writeState?: PolicyStrataRuntimeWriteState;
  approvalRequiredSatisfied?: boolean;
  approvalState?: PolicyStrataRuntimeApprovalState;
  decisionPoint?: PolicyStrataRuntimeDecisionPoint;
  semanticIr?: PolicyStrataRuntimeSemanticIr | null;
  mode?: PolicyStrataRuntimeMode;
}

export interface PolicyStrataAuthorizeToolDecision extends PolicyStrataAuthorizeDecision {
  toolName: string;
  normalizedRole?: string;
  toolKind?: string;
  userId?: string;
  householdId?: string;
  writeState: PolicyStrataRuntimeWriteState;
  approvalState: PolicyStrataRuntimeApprovalState;
  decisionPoint: PolicyStrataRuntimeDecisionPoint;
}

export interface PolicyStrataAuthorizeReleaseInput {
  subject?: PolicyStrataRuntimeSubject | string | null;
  resource: string | PolicyStrataRuntimeResourceRef;
  boundary: string;
  result?: PolicyStrataRuntimeReleaseResult | null;
  lineage?: PolicyStrataRuntimeReleaseLineage | null;
  context?: PolicyStrataRuntimeContext | null;
  mode?: PolicyStrataRuntimeMode;
}

export interface PolicyStrataAuthorizeReleaseDecision extends PolicyStrataAuthorizeDecision {
  boundary: string;
}

export interface PolicyStrataAuthorizer {
  authorize(input: PolicyStrataAuthorizeInput): PolicyStrataAuthorizeDecision;
  authorizeTool(input: PolicyStrataAuthorizeToolInput): PolicyStrataAuthorizeToolDecision;
  authorizeRelease(input: PolicyStrataAuthorizeReleaseInput): PolicyStrataAuthorizeReleaseDecision;
  evaluateRuntimeEvent(input: PolicyStrataRuntimeEventInput): PolicyStrataRuntimeEventEvaluation;
}

export interface PolicyStrataRuntimeActor {
  userId?: string;
  tenantId?: string;
  role?: string;
  scopes?: readonly string[];
  entitlements?: readonly string[];
  delegatedBy?: string;
  serviceAccount?: string;
  purpose?: string;
  region?: string;
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeResourceEventRef {
  kind: string;
  name: string;
  id?: string;
  uri?: string;
  tenantId?: string;
  tags?: readonly string[];
  entitlement?: string;
  requiredEntitlements?: readonly string[];
  version?: string;
  region?: string;
  [key: string]: unknown;
}

export interface PolicyStrataRuntimeAgent {
  key: string;
  name?: string;
  kind?: string;
  version?: string;
}

export interface PolicyStrataRuntimeEventDecision {
  action: PolicyStrataRuntimeEventAction;
  reason: string;
  control?: {
    id: string;
    mode?: "release_gate" | "runtime_enforcement" | "monitor";
    objective?: string;
  };
  policyRefs?: readonly string[];
  redactions?: readonly string[];
  approvalRef?: string;
  queryRisk?: string;
}

export interface PolicyStrataRuntimeExpectedDecision {
  allowed?: boolean;
  action?: PolicyStrataRuntimeEventAction;
  controlId?: string;
  reason?: string;
  reasonIncludes?: readonly string[];
  redactions?: readonly string[];
  policyRefs?: readonly string[];
}

export interface PolicyStrataRuntimeEventFields {
  schemaVersion: string;
  eventId: string;
  project: string;
  observedAt: string;
  agent: PolicyStrataRuntimeAgent;
  layer: PolicyStrataPolicyLayer;
  operation: string;
  summary: string;
  releaseCandidate?: string;
  environment?: string;
  decision?: PolicyStrataRuntimeEventDecision;
  expectedDecision?: PolicyStrataRuntimeExpectedDecision;
  actor?: PolicyStrataRuntimeActor;
  resource?: PolicyStrataRuntimeResourceEventRef;
  dataClasses?: readonly string[];
  policyRefs?: readonly string[];
  control?: Record<string, unknown>;
  traceId?: string;
  spanId?: string;
  eventRef?: string;
  witnessRefs?: readonly string[];
  toolInputSchemaRef?: string;
  toolOutputSchemaRef?: string;
  mcpInputSchemaRef?: string;
  mcpOutputSchemaRef?: string;
  payloadHash?: string;
  artifactRefs?: readonly string[];
  findingIds?: readonly string[];
  payload?: Record<string, unknown>;
  approvalRequiredSatisfied?: boolean;
  promptInjection?: boolean;
  tainted?: boolean;
}

export interface PolicyStrataRuntimeEventInput extends PolicyStrataRuntimeEventFields {
  [key: string]: unknown;
}

type OpenRuntimeEvent<T> = T & Record<string, unknown>;

type PolicyStrataRuntimeEventBuilderFields = Omit<
  PolicyStrataRuntimeEventFields,
  "schemaVersion" | "observedAt"
> & {
  schemaVersion?: string;
  observedAt?: string;
};

type PolicyStrataLayerRuntimeEventBuilderFields = Omit<
  PolicyStrataRuntimeEventFields,
  "schemaVersion" | "observedAt" | "layer" | "operation"
> & {
  schemaVersion?: string;
  observedAt?: string;
  operation?: string;
};

export type PolicyStrataRuntimeEventBuilderInput =
  OpenRuntimeEvent<PolicyStrataRuntimeEventBuilderFields>;

export type PolicyStrataLayerRuntimeEventBuilderInput =
  OpenRuntimeEvent<PolicyStrataLayerRuntimeEventBuilderFields>;

export type PolicyStrataSqlRuntimeEventInput = OpenRuntimeEvent<
  Omit<PolicyStrataLayerRuntimeEventBuilderFields, "payload"> & {
    sql: string;
    payload?: Record<string, unknown>;
    rowCount?: number;
    rowLimit?: number;
  }
>;

export type PolicyStrataToolRuntimeEventInput = OpenRuntimeEvent<
  Omit<
    PolicyStrataLayerRuntimeEventBuilderFields,
    "resource" | "toolInputSchemaRef" | "toolOutputSchemaRef" | "mcpInputSchemaRef" | "mcpOutputSchemaRef"
  > & {
    toolName: string;
    toolKind?: PolicyStrataRuntimeToolKind;
    resource?: Partial<PolicyStrataRuntimeResourceEventRef>;
    inputSchemaRef?: string;
    outputSchemaRef?: string;
    mcpInputSchemaRef?: string;
    mcpOutputSchemaRef?: string;
  }
>;

export type PolicyStrataRetrievalRuntimeEventInput = OpenRuntimeEvent<
  Omit<PolicyStrataLayerRuntimeEventBuilderFields, "resource"> & {
    resourceName: string;
    resource?: Partial<PolicyStrataRuntimeResourceEventRef>;
    tenantId?: string;
    requiredEntitlements?: readonly string[];
  }
>;

export type PolicyStrataEgressRuntimeEventInput = OpenRuntimeEvent<
  Omit<PolicyStrataLayerRuntimeEventBuilderFields, "resource"> & {
    destination: string;
    destinationClass?: string;
    resource?: Partial<PolicyStrataRuntimeResourceEventRef>;
  }
>;

export type PolicyStrataClearanceEvidencePackRuntimeEventInput = OpenRuntimeEvent<
  Omit<
    PolicyStrataLayerRuntimeEventBuilderFields,
    "artifactRefs" | "operation" | "payloadHash" | "resource" | "summary"
  > & {
    evidencePackRef: string;
    runId?: string;
    sha256?: string;
    summary?: string;
  }
>;

export interface PolicyStrataRuntimeEventEvaluation {
  eventId: string;
  allowed: boolean;
  action: PolicyStrataRuntimeEventAction;
  reason: string;
  reasons: string[];
  layer: PolicyStrataPolicyLayer;
  operation: string;
  controlId?: string;
  policyRefs: string[];
  redactions: string[];
  queryRisk?: string;
  decision: PolicyStrataRuntimeEventDecision;
  event: PolicyStrataRuntimeEventInput & { decision: PolicyStrataRuntimeEventDecision };
}

export function buildRuntimeEvent(input: PolicyStrataRuntimeEventBuilderInput): PolicyStrataRuntimeEventInput {
  const { schemaVersion, observedAt, ...event } = input;
  return {
    ...event,
    schemaVersion: schemaVersion ?? "0.2.0",
    observedAt: observedAt ?? new Date().toISOString(),
  };
}

export function parsePolicyStrataRuntimeEvent(value: unknown): PolicyStrataRuntimeEventInput {
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime event must be an object");
  }
  const schemaVersion = requiredEventString(value, "schemaVersion");
  const eventId = requiredEventString(value, "eventId");
  const project = requiredEventString(value, "project");
  const observedAt = requiredEventString(value, "observedAt");
  const operation = requiredEventString(value, "operation");
  const summary = requiredEventString(value, "summary");
  if (!isPolicyLayer(value.layer)) {
    throw new Error(`PolicyStrata runtime event has invalid layer: ${String(value.layer)}`);
  }
  const agent = parseRuntimeAgent(value.agent);
  const releaseCandidate = parseOptionalString(value.releaseCandidate, "event releaseCandidate");
  const environment = parseOptionalString(value.environment, "event environment");
  const decision = parseRuntimeEventDecision(value.decision);
  const expectedDecision = parseRuntimeExpectedDecision(value.expectedDecision);
  const actor = parseRuntimeActor(value.actor);
  const resource = parseRuntimeEventResource(value.resource);
  const dataClasses = parseOptionalStringArray(value.dataClasses, "event dataClasses");
  const policyRefs = parseOptionalStringArray(value.policyRefs, "event policyRefs");
  const control = optionalRecord(value.control, "event control");
  const traceId = parseOptionalString(value.traceId, "event traceId");
  const spanId = parseOptionalString(value.spanId, "event spanId");
  const eventRef = parseOptionalString(value.eventRef, "event eventRef");
  const witnessRefs = parseOptionalStringArray(value.witnessRefs, "event witnessRefs");
  const toolInputSchemaRef = parseOptionalString(
    value.toolInputSchemaRef,
    "event toolInputSchemaRef",
  );
  const toolOutputSchemaRef = parseOptionalString(
    value.toolOutputSchemaRef,
    "event toolOutputSchemaRef",
  );
  const mcpInputSchemaRef = parseOptionalString(
    value.mcpInputSchemaRef,
    "event mcpInputSchemaRef",
  );
  const mcpOutputSchemaRef = parseOptionalString(
    value.mcpOutputSchemaRef,
    "event mcpOutputSchemaRef",
  );
  const payloadHash = parseOptionalString(value.payloadHash, "event payloadHash");
  const artifactRefs = parseOptionalStringArray(value.artifactRefs, "event artifactRefs");
  const findingIds = parseOptionalStringArray(value.findingIds, "event findingIds");
  const payload = optionalRecord(value.payload, "event payload");
  const approvalRequiredSatisfied = parseOptionalBoolean(
    value.approvalRequiredSatisfied,
    "event approvalRequiredSatisfied",
  );
  const promptInjection = parseOptionalBoolean(value.promptInjection, "event promptInjection");
  const tainted = parseOptionalBoolean(value.tainted, "event tainted");

  return {
    ...unknownProperties(value, RUNTIME_EVENT_KNOWN_FIELDS),
    schemaVersion,
    eventId,
    project,
    observedAt,
    agent,
    layer: value.layer,
    operation,
    summary,
    ...optionalProperty("releaseCandidate", releaseCandidate),
    ...optionalProperty("environment", environment),
    ...optionalProperty("decision", decision),
    ...optionalProperty("expectedDecision", expectedDecision),
    ...optionalProperty("actor", actor),
    ...optionalProperty("resource", resource),
    ...optionalProperty("dataClasses", dataClasses),
    ...optionalProperty("policyRefs", policyRefs),
    ...optionalProperty("control", control),
    ...optionalProperty("traceId", traceId),
    ...optionalProperty("spanId", spanId),
    ...optionalProperty("eventRef", eventRef),
    ...optionalProperty("witnessRefs", witnessRefs),
    ...optionalProperty("toolInputSchemaRef", toolInputSchemaRef),
    ...optionalProperty("toolOutputSchemaRef", toolOutputSchemaRef),
    ...optionalProperty("mcpInputSchemaRef", mcpInputSchemaRef),
    ...optionalProperty("mcpOutputSchemaRef", mcpOutputSchemaRef),
    ...optionalProperty("payloadHash", payloadHash),
    ...optionalProperty("artifactRefs", artifactRefs),
    ...optionalProperty("findingIds", findingIds),
    ...optionalProperty("payload", payload),
    ...optionalProperty("approvalRequiredSatisfied", approvalRequiredSatisfied),
    ...optionalProperty("promptInjection", promptInjection),
    ...optionalProperty("tainted", tainted),
  };
}

const RUNTIME_EVENT_KNOWN_FIELDS = new Set([
  "schemaVersion",
  "eventId",
  "project",
  "observedAt",
  "agent",
  "layer",
  "operation",
  "summary",
  "releaseCandidate",
  "environment",
  "decision",
  "expectedDecision",
  "actor",
  "resource",
  "dataClasses",
  "policyRefs",
  "control",
  "traceId",
  "spanId",
  "eventRef",
  "witnessRefs",
  "toolInputSchemaRef",
  "toolOutputSchemaRef",
  "mcpInputSchemaRef",
  "mcpOutputSchemaRef",
  "payloadHash",
  "artifactRefs",
  "findingIds",
  "payload",
  "approvalRequiredSatisfied",
  "promptInjection",
  "tainted",
]);
const RUNTIME_AGENT_KNOWN_FIELDS = new Set(["key", "name", "kind", "version"]);
const RUNTIME_ACTOR_KNOWN_FIELDS = new Set([
  "userId",
  "tenantId",
  "role",
  "scopes",
  "entitlements",
  "delegatedBy",
  "serviceAccount",
  "purpose",
  "region",
]);
const RUNTIME_RESOURCE_KNOWN_FIELDS = new Set([
  "kind",
  "name",
  "id",
  "uri",
  "tenantId",
  "tags",
  "entitlement",
  "requiredEntitlements",
  "version",
  "region",
]);

function parseRuntimeAgent(value: unknown): PolicyStrataRuntimeAgent {
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime event agent must be an object");
  }
  const key = requiredEventString(value, "key", "agent");
  const name = parseOptionalString(value.name, "event agent.name");
  const kind = parseOptionalString(value.kind, "event agent.kind");
  const version = parseOptionalString(value.version, "event agent.version");
  return {
    ...unknownProperties(value, RUNTIME_AGENT_KNOWN_FIELDS),
    key,
    ...optionalProperty("name", name),
    ...optionalProperty("kind", kind),
    ...optionalProperty("version", version),
  };
}

function parseRuntimeActor(value: unknown): PolicyStrataRuntimeActor | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime event actor must be an object");
  }
  const userId = parseOptionalString(value.userId, "event actor.userId");
  const tenantId = parseOptionalString(value.tenantId, "event actor.tenantId");
  const role = parseOptionalString(value.role, "event actor.role");
  const scopes = parseOptionalStringArray(value.scopes, "event actor.scopes");
  const entitlements = parseOptionalStringArray(value.entitlements, "event actor.entitlements");
  const delegatedBy = parseOptionalString(value.delegatedBy, "event actor.delegatedBy");
  const serviceAccount = parseOptionalString(
    value.serviceAccount,
    "event actor.serviceAccount",
  );
  const purpose = parseOptionalString(value.purpose, "event actor.purpose");
  const region = parseOptionalString(value.region, "event actor.region");
  return {
    ...unknownProperties(value, RUNTIME_ACTOR_KNOWN_FIELDS),
    ...optionalProperty("userId", userId),
    ...optionalProperty("tenantId", tenantId),
    ...optionalProperty("role", role),
    ...optionalProperty("scopes", scopes),
    ...optionalProperty("entitlements", entitlements),
    ...optionalProperty("delegatedBy", delegatedBy),
    ...optionalProperty("serviceAccount", serviceAccount),
    ...optionalProperty("purpose", purpose),
    ...optionalProperty("region", region),
  };
}

function parseRuntimeEventResource(
  value: unknown,
): PolicyStrataRuntimeResourceEventRef | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime event resource must be an object");
  }
  const kind = requiredEventString(value, "kind", "resource");
  const name = requiredEventString(value, "name", "resource");
  const id = parseOptionalString(value.id, "event resource.id");
  const uri = parseOptionalString(value.uri, "event resource.uri");
  const tenantId = parseOptionalString(value.tenantId, "event resource.tenantId");
  const tags = parseOptionalStringArray(value.tags, "event resource.tags");
  const entitlement = parseOptionalString(value.entitlement, "event resource.entitlement");
  const requiredEntitlements = parseOptionalStringArray(
    value.requiredEntitlements,
    "event resource.requiredEntitlements",
  );
  const version = parseOptionalString(value.version, "event resource.version");
  const region = parseOptionalString(value.region, "event resource.region");
  return {
    ...unknownProperties(value, RUNTIME_RESOURCE_KNOWN_FIELDS),
    kind,
    name,
    ...optionalProperty("id", id),
    ...optionalProperty("uri", uri),
    ...optionalProperty("tenantId", tenantId),
    ...optionalProperty("tags", tags),
    ...optionalProperty("entitlement", entitlement),
    ...optionalProperty("requiredEntitlements", requiredEntitlements),
    ...optionalProperty("version", version),
    ...optionalProperty("region", region),
  };
}

function parseRuntimeEventDecision(
  value: unknown,
): PolicyStrataRuntimeEventDecision | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value) || !isRuntimeEventAction(value.action)) {
    throw new Error("PolicyStrata runtime event decision has an invalid action");
  }
  const reason = requiredEventString(value, "reason", "decision");
  const control = parseRuntimeDecisionControl(value.control);
  const policyRefs = parseOptionalStringArray(value.policyRefs, "event decision.policyRefs");
  const redactions = parseOptionalStringArray(value.redactions, "event decision.redactions");
  const approvalRef = parseOptionalString(value.approvalRef, "event decision.approvalRef");
  const queryRisk = parseOptionalString(value.queryRisk, "event decision.queryRisk");
  return {
    action: value.action,
    reason,
    ...optionalProperty("control", control),
    ...optionalProperty("policyRefs", policyRefs),
    ...optionalProperty("redactions", redactions),
    ...optionalProperty("approvalRef", approvalRef),
    ...optionalProperty("queryRisk", queryRisk),
  };
}

function parseRuntimeDecisionControl(
  value: unknown,
): PolicyStrataRuntimeEventDecision["control"] | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime event decision.control must be an object");
  }
  const id = requiredEventString(value, "id", "decision.control");
  if (value.mode !== undefined && !isRuntimeDecisionControlMode(value.mode)) {
    throw new Error("PolicyStrata runtime event decision.control.mode is invalid");
  }
  const mode = value.mode;
  const objective = parseOptionalString(value.objective, "event decision.control.objective");
  return {
    id,
    ...optionalProperty("mode", mode),
    ...optionalProperty("objective", objective),
  };
}

function parseRuntimeExpectedDecision(
  value: unknown,
): PolicyStrataRuntimeExpectedDecision | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime event expectedDecision must be an object");
  }
  const allowed = parseOptionalBoolean(value.allowed, "event expectedDecision.allowed");
  const action = value.action;
  if (action !== undefined && !isRuntimeEventAction(action)) {
    throw new Error("PolicyStrata runtime event expectedDecision.action is invalid");
  }
  const controlId = parseOptionalString(value.controlId, "event expectedDecision.controlId");
  const reason = parseOptionalString(value.reason, "event expectedDecision.reason");
  const reasonIncludes = parseOptionalStringArray(
    value.reasonIncludes,
    "event expectedDecision.reasonIncludes",
  );
  const redactions = parseOptionalStringArray(
    value.redactions,
    "event expectedDecision.redactions",
  );
  const policyRefs = parseOptionalStringArray(
    value.policyRefs,
    "event expectedDecision.policyRefs",
  );
  return {
    ...optionalProperty("allowed", allowed),
    ...optionalProperty("action", action),
    ...optionalProperty("controlId", controlId),
    ...optionalProperty("reason", reason),
    ...optionalProperty("reasonIncludes", reasonIncludes),
    ...optionalProperty("redactions", redactions),
    ...optionalProperty("policyRefs", policyRefs),
  };
}

function requiredEventString(
  value: Record<string, unknown>,
  key: string,
  parent = "event",
): string {
  const result = stringValue(value[key]);
  if (!result) {
    const path = parent === "event" ? key : `${parent}.${key}`;
    throw new Error(`PolicyStrata runtime event ${path} must be a non-empty string`);
  }
  return result;
}

function isPolicyLayer(value: unknown): value is PolicyStrataPolicyLayer {
  return policyStrataPolicyLayers.some((layer) => layer === value);
}

function isRuntimeEventAction(value: unknown): value is PolicyStrataRuntimeEventAction {
  return policyStrataRuntimeEventActions.some((action) => action === value);
}

function isRuntimeDecisionControlMode(
  value: unknown,
): value is "release_gate" | "runtime_enforcement" | "monitor" {
  return value === "release_gate" || value === "runtime_enforcement" || value === "monitor";
}

function unknownProperties(
  value: Record<string, unknown>,
  knownFields: ReadonlySet<string>,
): Record<string, unknown> {
  const properties: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) {
    if (!knownFields.has(key)) {
      properties[key] = item;
    }
  }
  return properties;
}

export function sqlRuntimeEvent(input: PolicyStrataSqlRuntimeEventInput): PolicyStrataRuntimeEventInput {
  const { sql, payload, rowCount, rowLimit, ...event } = input;
  return buildRuntimeEvent({
    ...event,
    layer: "sql",
    operation: input.operation ?? "read",
    payload: { ...(payload ?? {}), sql },
    ...(rowCount !== undefined ? { rowCount } : {}),
    ...(rowLimit !== undefined ? { rowLimit } : {}),
  });
}

export function toolRuntimeEvent(input: PolicyStrataToolRuntimeEventInput): PolicyStrataRuntimeEventInput {
  const {
    toolName,
    toolKind = "read",
    resource,
    inputSchemaRef,
    outputSchemaRef,
    mcpInputSchemaRef,
    mcpOutputSchemaRef,
    ...event
  } = input;
  return buildRuntimeEvent({
    ...event,
    layer: "tool_call",
    operation: input.operation ?? toolKind,
    resource: {
      kind: "mcp_tool",
      name: toolName,
      ...(resource ?? {}),
    },
    ...(inputSchemaRef ? { toolInputSchemaRef: inputSchemaRef } : {}),
    ...(outputSchemaRef ? { toolOutputSchemaRef: outputSchemaRef } : {}),
    ...(mcpInputSchemaRef ? { mcpInputSchemaRef } : {}),
    ...(mcpOutputSchemaRef ? { mcpOutputSchemaRef } : {}),
  });
}

export function retrievalRuntimeEvent(
  input: PolicyStrataRetrievalRuntimeEventInput,
): PolicyStrataRuntimeEventInput {
  const { resourceName, resource, tenantId, requiredEntitlements, ...event } = input;
  return buildRuntimeEvent({
    ...event,
    layer: "retrieval",
    operation: input.operation ?? "read",
    resource: {
      kind: "retrieval_result",
      name: resourceName,
      ...(tenantId ? { tenantId } : {}),
      ...(requiredEntitlements ? { requiredEntitlements } : {}),
      ...(resource ?? {}),
    },
  });
}

export function egressRuntimeEvent(input: PolicyStrataEgressRuntimeEventInput): PolicyStrataRuntimeEventInput {
  const { destination, destinationClass, resource, ...event } = input;
  return buildRuntimeEvent({
    ...event,
    layer: "egress",
    operation: input.operation ?? "send",
    resource: {
      kind: "egress_destination",
      name: destination,
      uri: destination,
      ...(destinationClass ? { destinationClass } : {}),
      ...(resource ?? {}),
    },
  });
}

export function clearanceEvidencePackRuntimeEvent(
  input: PolicyStrataClearanceEvidencePackRuntimeEventInput,
): PolicyStrataRuntimeEventInput {
  const { evidencePackRef, runId, sha256, summary, ...event } = input;
  return buildRuntimeEvent({
    ...event,
    layer: "trace",
    operation: "evidence_pack",
    summary: summary ?? "Clearance evidence pack metadata is available locally",
    resource: {
      kind: "clearance_evidence_pack",
      name: evidencePackRef,
      ...(runId ? { id: runId } : {}),
    },
    artifactRefs: [evidencePackRef],
    ...(sha256 ? { payloadHash: sha256 } : {}),
  });
}

interface NormalizedRuntimeAction {
  name: string;
  kind: string | undefined;
  allowedRoles: readonly string[];
  approvalRequired: boolean;
  requiresWriteGrant: boolean;
  semanticConstraints: PolicyStrataRuntimeSemanticConstraints | undefined;
  releaseConstraints: PolicyStrataRuntimeReleaseConstraints | undefined;
}

interface NormalizedRuntimeResource {
  name: string;
  type: string | undefined;
  actions: Map<string, NormalizedRuntimeAction>;
}

export function parsePolicyStrataRuntimeManifest(value: unknown): PolicyStrataRuntimeManifest {
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime manifest must be an object");
  }
  const schemaVersion = stringValue(value.schemaVersion);
  if (!schemaVersion) {
    throw new Error("PolicyStrata runtime manifest is missing schemaVersion");
  }
  const version = value.version;
  if (
    (typeof version !== "string" || version.length === 0) &&
    (typeof version !== "number" || !Number.isFinite(version))
  ) {
    throw new Error("PolicyStrata runtime manifest version must be a string or number");
  }
  if (value.defaultDecision !== "deny") {
    throw new Error("PolicyStrata runtime manifests must default to deny");
  }

  const roleAliases = parseRoleAliases(value.roleAliases);
  const resources = parseRuntimeResources(value.resources);
  const tools = parseRuntimeTools(value.tools);
  const controls = optionalRecord(value.controls, "manifest controls");
  const manifest: PolicyStrataRuntimeManifest = {
    schemaVersion,
    version,
    defaultDecision: "deny",
    ...(roleAliases ? { roleAliases } : {}),
    ...(resources ? { resources } : {}),
    ...(tools ? { tools } : {}),
    ...(controls ? { controls } : {}),
  };
  validateManifest(manifest);
  return manifest;
}

function parseRoleAliases(value: unknown): Record<string, string> | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error("PolicyStrata runtime manifest roleAliases must map strings to strings");
  }
  const aliases: Record<string, string> = {};
  for (const [role, alias] of Object.entries(value)) {
    if (typeof alias !== "string") {
      throw new Error("PolicyStrata runtime manifest roleAliases must map strings to strings");
    }
    aliases[role] = alias;
  }
  return aliases;
}

function parseRuntimeResources(value: unknown): PolicyStrataRuntimeResource[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value)) {
    throw new Error("PolicyStrata runtime manifest resources must be an array");
  }
  return value.map(parseRuntimeResource);
}

function parseRuntimeResource(value: unknown): PolicyStrataRuntimeResource {
  const resource = recordValue(value);
  const name = stringValue(resource.name);
  if (!name || !Array.isArray(resource.actions)) {
    throw new Error("PolicyStrata runtime resources require a name and actions array");
  }
  const type = parseOptionalString(resource.type, `resource ${name} type`);
  const source = parseOptionalString(resource.source, `resource ${name} source`);
  return {
    name,
    actions: resource.actions.map((action) => parseRuntimeAction(action, name)),
    ...(type ? { type } : {}),
    ...(source ? { source } : {}),
  };
}

function parseRuntimeAction(value: unknown, resourceName: string): PolicyStrataRuntimeAction {
  const action = recordValue(value);
  const name = stringValue(action.name);
  if (!name || !isNonEmptyStringArray(action.allowedRoles)) {
    throw new Error(`PolicyStrata runtime resource ${resourceName} has an invalid action`);
  }
  const kind = parseOptionalString(action.kind, `action ${name} kind`);
  const approvalRequired = parseOptionalBoolean(
    action.approvalRequired,
    `action ${name} approvalRequired`,
  );
  const requiresWriteGrant = parseOptionalBoolean(
    action.requiresWriteGrant,
    `action ${name} requiresWriteGrant`,
  );
  const semanticConstraints = parseSemanticConstraints(
    action.semanticConstraints,
    `action ${name} semanticConstraints`,
  );
  const releaseConstraints = parseReleaseConstraints(
    action.releaseConstraints,
    `action ${name} releaseConstraints`,
  );
  const metrics = parseOptionalStringArray(action.metrics, `action ${name} metrics`);
  const dimensions = parseOptionalStringArray(action.dimensions, `action ${name} dimensions`);
  const source = parseOptionalString(action.source, `action ${name} source`);
  return {
    name,
    allowedRoles: action.allowedRoles,
    ...(kind ? { kind } : {}),
    ...(approvalRequired !== undefined ? { approvalRequired } : {}),
    ...(requiresWriteGrant !== undefined ? { requiresWriteGrant } : {}),
    ...(semanticConstraints ? { semanticConstraints } : {}),
    ...(releaseConstraints ? { releaseConstraints } : {}),
    ...(metrics ? { metrics } : {}),
    ...(dimensions ? { dimensions } : {}),
    ...(source ? { source } : {}),
  };
}

function parseRuntimeTools(value: unknown): PolicyStrataRuntimeTool[] | undefined {
  if (value === undefined) return undefined;
  if (!Array.isArray(value)) {
    throw new Error("PolicyStrata runtime manifest tools must be an array");
  }
  return value.map(parseRuntimeTool);
}

function parseRuntimeTool(value: unknown): PolicyStrataRuntimeTool {
  const tool = recordValue(value);
  const name = stringValue(tool.name);
  if (!name || !isRuntimeToolKind(tool.kind) || !isNonEmptyStringArray(tool.allowedRoles)) {
    throw new Error("PolicyStrata runtime manifest contains an invalid tool");
  }
  const approvalRequired = parseOptionalBoolean(
    tool.approvalRequired,
    `tool ${name} approvalRequired`,
  );
  const metrics = parseOptionalStringArray(tool.metrics, `tool ${name} metrics`);
  const dimensions = parseOptionalStringArray(tool.dimensions, `tool ${name} dimensions`);
  const source = parseOptionalString(tool.source, `tool ${name} source`);
  return {
    name,
    kind: tool.kind,
    allowedRoles: tool.allowedRoles,
    ...(approvalRequired !== undefined ? { approvalRequired } : {}),
    ...(metrics ? { metrics } : {}),
    ...(dimensions ? { dimensions } : {}),
    ...(source ? { source } : {}),
  };
}

function parseSemanticConstraints(
  value: unknown,
  label: string,
): PolicyStrataRuntimeSemanticConstraints | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error(`PolicyStrata runtime ${label} must be an object`);
  }
  const metrics = parseOptionalStringArray(value.metrics, `${label}.metrics`);
  const dimensions = parseOptionalStringArray(value.dimensions, `${label}.dimensions`);
  return {
    ...(metrics ? { metrics } : {}),
    ...(dimensions ? { dimensions } : {}),
  };
}

function parseReleaseConstraints(
  value: unknown,
  label: string,
): PolicyStrataRuntimeReleaseConstraints | undefined {
  if (value === undefined) return undefined;
  if (!isRecord(value)) {
    throw new Error(`PolicyStrata runtime ${label} must be an object`);
  }
  const boundaries = parseOptionalStringArray(value.boundaries, `${label}.boundaries`);
  const resultKinds = parseOptionalStringArray(value.resultKinds, `${label}.resultKinds`);
  const lineageSources = parseOptionalStringArray(value.lineageSources, `${label}.lineageSources`);
  const maxRows = value.maxRows;
  if (
    maxRows !== undefined &&
    (typeof maxRows !== "number" || !Number.isInteger(maxRows) || maxRows < 0)
  ) {
    throw new Error(`PolicyStrata runtime ${label}.maxRows must be a non-negative integer`);
  }
  const requireLineage = parseOptionalBoolean(value.requireLineage, `${label}.requireLineage`);
  const allowSensitive = parseOptionalBoolean(value.allowSensitive, `${label}.allowSensitive`);
  const allowRawRows = parseOptionalBoolean(value.allowRawRows, `${label}.allowRawRows`);
  return {
    ...(boundaries ? { boundaries } : {}),
    ...(resultKinds ? { resultKinds } : {}),
    ...(lineageSources ? { lineageSources } : {}),
    ...(typeof maxRows === "number" ? { maxRows } : {}),
    ...(requireLineage !== undefined ? { requireLineage } : {}),
    ...(allowSensitive !== undefined ? { allowSensitive } : {}),
    ...(allowRawRows !== undefined ? { allowRawRows } : {}),
  };
}

function parseOptionalString(value: unknown, label: string): string | undefined {
  if (value !== undefined && (typeof value !== "string" || value.length === 0)) {
    throw new Error(`PolicyStrata runtime ${label} must be a non-empty string`);
  }
  return typeof value === "string" ? value : undefined;
}

function parseOptionalBoolean(value: unknown, label: string): boolean | undefined {
  if (value !== undefined && typeof value !== "boolean") {
    throw new Error(`PolicyStrata runtime ${label} must be a boolean`);
  }
  return typeof value === "boolean" ? value : undefined;
}

function parseOptionalStringArray(value: unknown, label: string): string[] | undefined {
  if (
    value !== undefined &&
    (!Array.isArray(value) ||
      value.some((item) => typeof item !== "string" || item.length === 0))
  ) {
    throw new Error(`PolicyStrata runtime ${label} must be an array of non-empty strings`);
  }
  return Array.isArray(value) ? value : undefined;
}

function optionalRecord(value: unknown, label: string): Record<string, unknown> | undefined {
  if (value !== undefined && !isRecord(value)) {
    throw new Error(`PolicyStrata runtime ${label} must be an object`);
  }
  return isRecord(value) ? value : undefined;
}

function isRuntimeToolKind(value: unknown): value is PolicyStrataRuntimeToolKind {
  return (
    value === "read" ||
    value === "write" ||
    value === "export" ||
    value === "memory" ||
    value === "external"
  );
}

function isNonEmptyStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((item) => typeof item === "string" && item.length > 0)
  );
}

export function createPolicyStrataAuthorizer(
  manifest: PolicyStrataRuntimeManifest,
): PolicyStrataAuthorizer {
  validateManifest(manifest);

  const resourcesByName = normalizeResources(manifest);
  const knownRoles = collectKnownRoles(manifest, resourcesByName);

  function authorize(input: PolicyStrataAuthorizeInput): PolicyStrataAuthorizeDecision {
    const mode = input.mode ?? "shadow";
    const resourceName = resourceRefName(input.resource);
    const decisionResourceName = resourceName ?? "";
    const subjectRoles = subjectRoleValues(input.subject);
    const normalizedRoles = normalizeRoles(subjectRoles, manifest.roleAliases);
    const reasons: string[] = [];
    const resource = resourceName ? resourcesByName.get(resourceName) : undefined;
    const action = resource?.actions.get(input.action);

    if (!resourceName) {
      reasons.push("missing resource");
    } else if (!resource) {
      reasons.push(`unknown resource: ${resourceName}`);
    }

    if (!input.action) {
      reasons.push("missing action");
    } else if (resource && !action) {
      reasons.push(`unknown action: ${input.action} for resource ${resource.name}`);
    }

    if (subjectRoles.length === 0) {
      reasons.push("missing role");
    } else {
      for (let index = 0; index < subjectRoles.length; index += 1) {
        const normalizedRole = normalizedRoles[index];
        if (normalizedRole && !knownRoles.has(normalizedRole)) {
          reasons.push(`unknown role: ${subjectRoles[index]}`);
        }
      }
    }

    if (action && normalizedRoles.length > 0) {
      const allowedRoles = new Set(action.allowedRoles);
      const hasAllowedRole = normalizedRoles.some((role) => allowedRoles.has(role));
      if (!hasAllowedRole) {
        reasons.push(
          `roles ${normalizedRoles.join(", ")} are not allowed to ${action.name} ${decisionResourceName}`,
        );
      }
      if (action.requiresWriteGrant && writeGrantSatisfied(input.context) !== true) {
        reasons.push(`action ${action.name} on ${decisionResourceName} requires allowWriteTools`);
      }
      if (action.approvalRequired && approvalSatisfied(input.context) !== true) {
        reasons.push(`action ${action.name} on ${decisionResourceName} requires approval`);
      }
      reasons.push(...semanticReasons(decisionResourceName, action, semanticIr(input.context)));
      reasons.push(...releaseReasons(decisionResourceName, action, releaseContext(input.context)));
    }

    return {
      allowed: reasons.length === 0,
      reasons,
      action: input.action,
      resource: decisionResourceName,
      normalizedRoles,
      manifestVersion: String(manifest.version),
      enforcementMode: mode,
    };
  }

  return {
    authorize,
    authorizeTool(input) {
      const action = input.action ?? toolActionName(resourcesByName, input.toolName);
      const runtimeResource = resourcesByName.get(input.toolName);
      const runtimeAction = runtimeResource?.actions.get(action);
      const decisionPoint = input.decisionPoint ?? "execution";
      const writeState = input.writeState ?? (input.allowWriteTools === true ? "enabled" : "disabled");
      const approvalState =
        input.approvalState ??
        (input.approvalRequiredSatisfied === true
          ? "satisfied"
          : runtimeAction?.approvalRequired === true
            ? "pending"
            : "not_required");
      const decision = authorize({
        subject: { role: input.role ?? null },
        action,
        resource: input.toolName,
        context: {
          allowWriteTools: writeState === "enabled",
          approvalRequiredSatisfied:
            decisionPoint === "execution" ? approvalState === "satisfied" : true,
          ...(input.semanticIr !== undefined ? { semanticIr: input.semanticIr } : {}),
        },
        ...(input.mode ? { mode: input.mode } : {}),
      });
      const reasons = decision.reasons.map((reason) =>
        reason === `unknown resource: ${input.toolName}` ? `unknown tool: ${input.toolName}` : reason,
      );
      if (runtimeAction?.kind && input.toolKind && input.toolKind !== runtimeAction.kind) {
        reasons.push(
          `tool kind context ${input.toolKind} does not match manifest kind ${runtimeAction.kind} for ${input.toolName}`,
        );
      }
      const userId = optionalString(input.userId);
      const householdId = optionalString(input.householdId);

      return {
        ...decision,
        allowed: reasons.length === 0,
        reasons,
        toolName: input.toolName,
        ...(decision.normalizedRoles[0]
          ? { normalizedRole: decision.normalizedRoles[0] }
          : {}),
        ...(runtimeAction?.kind ? { toolKind: runtimeAction.kind } : {}),
        ...(userId ? { userId } : {}),
        ...(householdId ? { householdId } : {}),
        writeState,
        approvalState,
        decisionPoint,
      };
    },
    authorizeRelease(input) {
      const decision = authorize({
        ...(input.subject !== undefined ? { subject: input.subject } : {}),
        action: "release",
        resource: input.resource,
        context: {
          ...(input.context ?? {}),
          release: {
            boundary: input.boundary,
            ...(input.result !== undefined ? { result: input.result } : {}),
            ...(input.lineage !== undefined ? { lineage: input.lineage } : {}),
          },
        },
        ...(input.mode ? { mode: input.mode } : {}),
      });

      return {
        ...decision,
        boundary: input.boundary,
      };
    },
    evaluateRuntimeEvent(input) {
      return evaluateRuntimeEvent(manifest, input);
    },
  };
}

export function authorize(
  manifest: PolicyStrataRuntimeManifest,
  input: PolicyStrataAuthorizeInput,
): PolicyStrataAuthorizeDecision {
  return createPolicyStrataAuthorizer(manifest).authorize(input);
}

export function authorizeTool(
  manifest: PolicyStrataRuntimeManifest,
  input: PolicyStrataAuthorizeToolInput,
): PolicyStrataAuthorizeToolDecision {
  return createPolicyStrataAuthorizer(manifest).authorizeTool(input);
}

export function authorizeRelease(
  manifest: PolicyStrataRuntimeManifest,
  input: PolicyStrataAuthorizeReleaseInput,
): PolicyStrataAuthorizeReleaseDecision {
  return createPolicyStrataAuthorizer(manifest).authorizeRelease(input);
}

export function evaluateRuntimeEvent(
  manifest: PolicyStrataRuntimeManifest,
  input: PolicyStrataRuntimeEventInput,
): PolicyStrataRuntimeEventEvaluation {
  if (!policyStrataPolicyLayers.includes(input.layer)) {
    throw new Error(`unknown runtime layer: ${input.layer}`);
  }

  const controls = recordValue(manifest.controls);
  const actor = recordValue(input.actor);
  const resource = recordValue(input.resource);
  const reasons: string[] = [];
  const redactions: string[] = [];
  let queryRisk: string | undefined;
  let action: PolicyStrataRuntimeEventAction = "allow";
  let controlId: string | undefined;

  function apply(nextAction: PolicyStrataRuntimeEventAction, reason: string, nextControlId: string) {
    reasons.push(reason);
    if (eventActionRank(nextAction) > eventActionRank(action)) {
      action = nextAction;
      controlId = nextControlId;
    }
  }

  if (controlBool(controls, "runtime", "killSwitch") || controlBool(controls, "runtime", "kill_switch")) {
    apply("deny", "runtime kill switch is enabled", "runtime_kill_switch");
  }

  if (controlEnabled(controls, "authContext", true)) {
    const missing = missingAuthFields(actor, controls);
    if (missing.length > 0) {
      apply("deny", `missing auth context fields: ${missing.join(", ")}`, "auth_context_required");
    }
  }

  if (input.layer === "retrieval" && controlEnabled(controls, "retrieval", true)) {
    if (tenantMismatch(actor, resource)) {
      apply("deny", "retrieval resource tenant does not match actor tenant", "retrieval_entitlement_required");
    }
    const missing = missingEntitlements(actor, resource);
    if (missing.length > 0) {
      apply(
        "deny",
        `actor is missing retrieval entitlements: ${missing.join(", ")}`,
        "retrieval_entitlement_required",
      );
    }
  }

  if (input.layer === "tool_call" && controlEnabled(controls, "tools", true)) {
    const toolName = resourceName(resource);
    const allowedTools = controlStringSet(controls, "tools", "allowlist");
    const approvalTools = controlStringSet(controls, "tools", "approvalRequired");
    if (toolName && allowedTools.size > 0 && !allowedTools.has(toolName)) {
      apply("require_approval", `tool ${toolName} is not in the runtime allowlist`, "mcp_tool_allowlist_required");
    }
    if (toolName && approvalTools.has(toolName) && !eventApprovalSatisfied(input)) {
      apply("require_approval", `tool ${toolName} requires approval`, "mcp_tool_allowlist_required");
    }
  }

  if (input.layer === "sql" && controlEnabled(controls, "sql", true)) {
    const sqlText = eventText(input, "sql", "query", "statement", "observed");
    const tenantColumn = controlString(controls, "sql", "tenantColumn") ?? "tenant_id";
    queryRisk = classifySqlQueryRisk(sqlText);
    if (sqlText && !sqlHasTenantPredicate(sqlText, tenantColumn)) {
      apply("deny", `SQL statement is missing tenant predicate ${tenantColumn}`, "tenant_scope_required");
    }
    if (sqlText && controlBool(controls, "sql", "requireParameterized")) {
      const parameterizationIssues = sqlParameterizationIssues(sqlText);
      if (parameterizationIssues.length > 0) {
        apply(
          "deny",
          `SQL statement contains unparameterized literals: ${parameterizationIssues.join(", ")}`,
          "sql_parameterization_required",
        );
      }
    }
    if (tenantMismatch(actor, resource)) {
      apply("deny", "SQL resource tenant does not match actor tenant", "tenant_scope_required");
    }
    const allowedRisks = controlStringSet(controls, "sql", "allowedQueryRisks");
    const deniedRisks = controlStringSet(controls, "sql", "deniedQueryRisks");
    if (deniedRisks.has(queryRisk) || (allowedRisks.size > 0 && !allowedRisks.has(queryRisk))) {
      apply("deny", `SQL query risk ${queryRisk} is not allowed`, "sql_query_risk");
    }
    const maxRows = controlNumber(controls, "sql", "maxRows");
    const rowCount = eventNumber(input, "rowLimit", "row_limit", "limit", "rowCount", "returnedRows");
    if (maxRows !== undefined && rowCount !== undefined && rowCount > maxRows) {
      apply("deny", `SQL row count ${rowCount} exceeds maxRows ${maxRows}`, "sql_row_limit");
    }
  }

  if (input.layer === "database_rule" && controlEnabled(controls, "databaseRule", true)) {
    const requireRls = controlBool(controls, "databaseRule", "requireRls");
    const rlsEnabled = eventBool(input, "rlsEnabled", "rls_enabled");
    const rlsExpected = eventBool(input, "rlsExpected", "rls_expected");
    if (input.rlsDrift === true || input.rls_drift === true) {
      apply("deny", "RLS drift signal is present", "rls_drift");
    }
    if ((requireRls || rlsExpected) && !rlsEnabled) {
      apply("deny", "RLS is expected but not enabled", "rls_drift");
    }
  }

  if (input.layer === "schema_binding" && controlEnabled(controls, "schemaBinding", true)) {
    const expected = controlExpectedVersion(controls, resource);
    const actual = stringValue(resource.version) ?? stringValue(resource.schemaVersion);
    if (expected && actual && actual !== expected) {
      apply(
        "log_only",
        `schema binding ${resourceName(resource)} uses ${actual}, expected ${expected}`,
        "schema_binding_current",
      );
    }
  }

  if (input.layer === "memory" && controlEnabled(controls, "memory", true) && tenantMismatch(actor, resource)) {
    apply("quarantine", "memory item tenant does not match actor tenant", "memory_tenant_isolation");
  }

  if (input.layer === "egress" && controlEnabled(controls, "egress", true)) {
    const destination = resourceUriOrName(resource);
    const allowedDestinations = controlStringSet(controls, "egress", "allowedDestinations");
    const allowedClasses = controlStringSet(controls, "egress", "allowedDestinationClasses");
    const destinationClass =
      stringValue(resource.destinationClass) ??
      stringValue(resource.classification) ??
      stringValue(input.destinationClass);
    if (destination && allowedDestinations.size > 0 && !allowedDestinations.has(destination)) {
      apply("deny", `egress destination ${destination} is not approved`, "egress_approval_required");
    }
    if (destinationClass && allowedClasses.size > 0 && !allowedClasses.has(destinationClass)) {
      apply(
        "deny",
        `egress destination class ${destinationClass} is not approved`,
        "egress_destination_class",
      );
    }
    if (controlBool(controls, "egress", "approvalRequired") && !eventApprovalSatisfied(input)) {
      apply("require_approval", "egress requires approval", "egress_approval_required");
    }
  }

  const data = recordValue(controls.data);
  const dataClasses = new Set(input.dataClasses ?? []);
  const denied = stringArray(data.deniedClasses).filter((item) => dataClasses.has(item));
  const redact = stringArray(data.redactClasses).filter((item) => dataClasses.has(item));
  const secrets = stringArray(data.secretClasses).filter((item) => dataClasses.has(item));
  if (denied.length > 0) {
    apply("deny", `blocked data classes present: ${denied.join(", ")}`, "data_class_policy");
  }
  if (redact.length > 0 || secrets.length > 0) {
    redactions.push(...secrets, ...redact);
    apply("redact", `redaction required for data classes: ${redactions.join(", ")}`, "pii_secret_minimization");
  }

  if (controlEnabled(controls, "dataResidency", false)) {
    const allowedRegions = controlStringSet(controls, "dataResidency", "allowedRegions");
    const region = stringValue(actor.region) ?? stringValue(resource.region);
    if (region && allowedRegions.size > 0 && !allowedRegions.has(region)) {
      apply("deny", `region ${region} is outside allowed residency set`, "data_residency");
    }
  }

  const taint = recordValue(controls.taint);
  if (taint.blockPromptInjection === true && eventBool(input, "promptInjection", "prompt_injection")) {
    apply("quarantine", "prompt injection signal is present", "prompt_injection_taint");
  }
  if (taint.blockTaintedToolResults === true && eventBool(input, "tainted", "toolResultTainted")) {
    apply("quarantine", "tainted tool result signal is present", "tool_result_taint");
  }

  if (action === "allow" && controlBool(controls, "runtime", "logAllowed")) {
    action = "log_only";
    controlId = "runtime_log_allowed";
    reasons.push("allowed action logged by runtime policy");
  }

  const allowed = action === "allow" || action === "log_only";
  const reason = reasons[0] ?? "runtime policy allowed action";
  const decision: PolicyStrataRuntimeEventDecision = {
    action,
    reason,
    ...(controlId ? { control: { id: controlId, mode: "runtime_enforcement" } } : {}),
    ...(input.policyRefs ? { policyRefs: input.policyRefs } : {}),
    ...(redactions.length > 0 ? { redactions } : {}),
    ...(queryRisk ? { queryRisk } : {}),
  };
  return {
    eventId: input.eventId,
    allowed,
    action,
    reason,
    reasons,
    layer: input.layer,
    operation: input.operation,
    ...(controlId ? { controlId } : {}),
    policyRefs: [...(input.policyRefs ?? [])],
    redactions,
    ...(queryRisk ? { queryRisk } : {}),
    decision,
    event: {
      ...input,
      decision,
    },
  };
}

export function evaluateRuntimeEvents(
  manifest: PolicyStrataRuntimeManifest,
  inputs: readonly PolicyStrataRuntimeEventInput[],
): PolicyStrataRuntimeEventEvaluation[] {
  return inputs.map((input) => evaluateRuntimeEvent(manifest, input));
}

export function expectedRuntimeDecisionMismatches(
  input: PolicyStrataRuntimeEventInput,
  evaluation: PolicyStrataRuntimeEventEvaluation,
): string[] {
  const expected = recordValue(input.expectedDecision);
  if (Object.keys(expected).length === 0) return [];

  const mismatches: string[] = [];
  if (Object.hasOwn(expected, "allowed") && typeof expected.allowed !== "boolean") {
    mismatches.push("expectedDecision.allowed must be a boolean");
  } else if (typeof expected.allowed === "boolean" && expected.allowed !== evaluation.allowed) {
    mismatches.push(`expected allowed=${expected.allowed}, got allowed=${evaluation.allowed}`);
  }

  const expectedAction = stringValue(expected.action);
  if (expectedAction && expectedAction !== evaluation.action) {
    mismatches.push(`expected action=${expectedAction}, got action=${evaluation.action}`);
  }

  const expectedControlId = stringValue(expected.controlId);
  if (expectedControlId && expectedControlId !== evaluation.controlId) {
    mismatches.push(`expected controlId=${expectedControlId}, got controlId=${evaluation.controlId ?? "none"}`);
  }

  const expectedReason = stringValue(expected.reason);
  if (expectedReason && expectedReason !== evaluation.reason) {
    mismatches.push(`expected reason=${JSON.stringify(expectedReason)}, got reason=${JSON.stringify(evaluation.reason)}`);
  }

  const reasonText = [evaluation.reason, ...evaluation.reasons].join("\n");
  for (const snippet of stringArray(expected.reasonIncludes)) {
    if (!reasonText.includes(snippet)) {
      mismatches.push(`expected reason to include ${JSON.stringify(snippet)}`);
    }
  }

  for (const redaction of stringArray(expected.redactions)) {
    if (!evaluation.redactions.includes(redaction)) {
      mismatches.push(`expected redaction ${JSON.stringify(redaction)}`);
    }
  }

  for (const policyRef of stringArray(expected.policyRefs)) {
    if (!evaluation.policyRefs.includes(policyRef)) {
      mismatches.push(`expected policyRef ${JSON.stringify(policyRef)}`);
    }
  }

  return mismatches;
}

function validateManifest(manifest: PolicyStrataRuntimeManifest): void {
  if (manifest.defaultDecision !== "deny") {
    throw new Error("PolicyStrata runtime manifests must default to deny");
  }
  if (!manifest.resources?.length && !manifest.tools?.length) {
    throw new Error("PolicyStrata runtime manifests must declare resources or tools");
  }
  normalizeResources(manifest);
}

function normalizeResources(
  manifest: PolicyStrataRuntimeManifest,
): Map<string, NormalizedRuntimeResource> {
  const resourcesByName = new Map<string, NormalizedRuntimeResource>();

  for (const resource of manifest.resources ?? []) {
    addResource(resourcesByName, {
      name: resource.name,
      type: resource.type,
      actions: new Map(resource.actions.map((action) => [action.name, normalizeAction(action)])),
    });
  }

  for (const tool of manifest.tools ?? []) {
    addResource(resourcesByName, {
      name: tool.name,
      type: "tool",
      actions: new Map([
        [
          tool.kind,
          normalizeAction({
            name: tool.kind,
            kind: tool.kind,
            allowedRoles: tool.allowedRoles,
            ...(tool.approvalRequired !== undefined
              ? { approvalRequired: tool.approvalRequired }
              : {}),
            requiresWriteGrant: tool.kind === "write",
            ...(tool.metrics ? { metrics: tool.metrics } : {}),
            ...(tool.dimensions ? { dimensions: tool.dimensions } : {}),
          }),
        ],
      ]),
    });
  }

  return resourcesByName;
}

function normalizeAction(action: PolicyStrataRuntimeAction): NormalizedRuntimeAction {
  if (!action.name) throw new Error("PolicyStrata runtime action is missing name");
  if (action.allowedRoles.length === 0) {
    throw new Error(`PolicyStrata runtime action has no allowed roles: ${action.name}`);
  }
  return {
    name: action.name,
    kind: action.kind,
    allowedRoles: action.allowedRoles,
    approvalRequired: action.approvalRequired === true,
    requiresWriteGrant: action.requiresWriteGrant === true || action.kind === "write",
    semanticConstraints:
      action.semanticConstraints ?? semanticConstraintsFromLegacyFields(action.metrics, action.dimensions),
    releaseConstraints: action.releaseConstraints,
  };
}

function semanticConstraintsFromLegacyFields(
  metrics: readonly string[] | undefined,
  dimensions: readonly string[] | undefined,
): PolicyStrataRuntimeSemanticConstraints | undefined {
  if (!metrics && !dimensions) return undefined;
  return {
    ...(metrics ? { metrics } : {}),
    ...(dimensions ? { dimensions } : {}),
  };
}

function addResource(
  resourcesByName: Map<string, NormalizedRuntimeResource>,
  resource: NormalizedRuntimeResource,
): void {
  if (!resource.name) throw new Error("PolicyStrata runtime resource is missing name");
  if (resourcesByName.has(resource.name)) {
    throw new Error(`duplicate PolicyStrata runtime resource: ${resource.name}`);
  }
  if (resource.actions.size === 0) {
    throw new Error(`PolicyStrata runtime resource has no actions: ${resource.name}`);
  }
  resourcesByName.set(resource.name, resource);
}

function collectKnownRoles(
  manifest: PolicyStrataRuntimeManifest,
  resourcesByName: Map<string, NormalizedRuntimeResource>,
): Set<string> {
  const knownRoles = new Set<string>();
  for (const role of Object.values(manifest.roleAliases ?? {})) knownRoles.add(role);
  for (const resource of resourcesByName.values()) {
    for (const action of resource.actions.values()) {
      for (const role of action.allowedRoles) knownRoles.add(role);
    }
  }
  return knownRoles;
}

function resourceRefName(resource: string | PolicyStrataRuntimeResourceRef): string | undefined {
  if (typeof resource === "string") return resource || undefined;
  return resource.name ?? resource.id;
}

function subjectRoleValues(subject: PolicyStrataRuntimeSubject | string | null | undefined): string[] {
  if (!subject) return [];
  if (typeof subject === "string") return [subject];

  const roles = new Set<string>();
  if (subject.role) roles.add(subject.role);
  for (const role of subject.roles ?? []) {
    if (role) roles.add(role);
  }
  return [...roles];
}

function normalizeRoles(
  roles: readonly string[],
  aliases: Record<string, string> | undefined,
): string[] {
  return roles.map((role) => aliases?.[role] ?? role);
}

function writeGrantSatisfied(context: PolicyStrataRuntimeContext | null | undefined): boolean | undefined {
  return context?.allowWriteTools ?? context?.allow_write_tools;
}

function approvalSatisfied(context: PolicyStrataRuntimeContext | null | undefined): boolean | undefined {
  return context?.approvalRequiredSatisfied ?? context?.approval_required_satisfied;
}

function semanticIr(
  context: PolicyStrataRuntimeContext | null | undefined,
): PolicyStrataRuntimeSemanticIr | null | undefined {
  return context?.semanticIr ?? context?.semantic_ir;
}

function releaseContext(
  context: PolicyStrataRuntimeContext | null | undefined,
): PolicyStrataRuntimeReleaseContext | null | undefined {
  return context?.release;
}

function toolActionName(
  resourcesByName: Map<string, NormalizedRuntimeResource>,
  toolName: string,
): string {
  const resource = resourcesByName.get(toolName);
  if (!resource) return "run";
  const nonReleaseActions = [...resource.actions.keys()].filter((action) => action !== "release");
  if (nonReleaseActions.length === 1) return nonReleaseActions[0] ?? "run";
  if (resource.actions.size !== 1) return "run";
  return [...resource.actions.keys()][0] ?? "run";
}

function optionalString(value: string | null | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

function semanticReasons(
  resourceName: string,
  action: NormalizedRuntimeAction,
  semanticIrValue: PolicyStrataRuntimeSemanticIr | null | undefined,
): string[] {
  if (!semanticIrValue) return [];
  const constraints = action.semanticConstraints;
  if (!constraints) return [];

  const reasons: string[] = [];
  const metric = typeof semanticIrValue.metric === "string" ? semanticIrValue.metric : undefined;
  if (metric && constraints.metrics && constraints.metrics.length > 0 && !constraints.metrics.includes(metric)) {
    reasons.push(`metric ${metric} is not declared for ${action.name} ${resourceName}`);
  }

  const dimensions = Array.isArray(semanticIrValue.dimensions)
    ? semanticIrValue.dimensions.filter((value): value is string => typeof value === "string")
    : [];
  if (dimensions.length > 0 && constraints.dimensions && constraints.dimensions.length > 0) {
    const allowedDimensions = new Set(constraints.dimensions);
    for (const dimension of dimensions) {
      if (!allowedDimensions.has(dimension)) {
        reasons.push(`dimension ${dimension} is not declared for ${action.name} ${resourceName}`);
      }
    }
  }
  return reasons;
}

function releaseReasons(
  resourceName: string,
  action: NormalizedRuntimeAction,
  release: PolicyStrataRuntimeReleaseContext | null | undefined,
): string[] {
  const constraints = action.releaseConstraints;
  if (!constraints) return [];

  const reasons: string[] = [];
  if (!release) {
    return [`missing release context for ${action.name} ${resourceName}`];
  }

  const boundary = release.boundary;
  if (!boundary) {
    reasons.push(`missing release boundary for ${action.name} ${resourceName}`);
  } else if (
    constraints.boundaries &&
    constraints.boundaries.length > 0 &&
    !constraints.boundaries.includes(boundary)
  ) {
    reasons.push(`release boundary ${boundary} is not declared for ${action.name} ${resourceName}`);
  }

  const result = release.result;
  const resultKind = result?.kind;
  if (
    resultKind &&
    constraints.resultKinds &&
    constraints.resultKinds.length > 0 &&
    !constraints.resultKinds.includes(resultKind)
  ) {
    reasons.push(`result kind ${resultKind} is not declared for ${action.name} ${resourceName}`);
  }

  const rowCount = result?.rowCount;
  if (typeof rowCount === "number" && constraints.maxRows !== undefined && rowCount > constraints.maxRows) {
    reasons.push(`row count ${rowCount} exceeds release max rows ${constraints.maxRows}`);
  }
  if (result?.containsSensitiveValues === true && constraints.allowSensitive !== true) {
    reasons.push(`release result contains sensitive values for ${action.name} ${resourceName}`);
  }

  const lineage = release.lineage;
  const lineageSources = Array.isArray(lineage?.sources)
    ? lineage.sources.filter((source): source is string => typeof source === "string")
    : [];
  if (constraints.requireLineage === true && lineageSources.length === 0) {
    reasons.push(`release lineage is required for ${action.name} ${resourceName}`);
  }
  if (lineage?.containsRawRows === true && constraints.allowRawRows !== true) {
    reasons.push(`release lineage contains raw rows for ${action.name} ${resourceName}`);
  }
  if (lineageSources.length > 0 && constraints.lineageSources && constraints.lineageSources.length > 0) {
    const allowedSources = new Set(constraints.lineageSources);
    for (const source of lineageSources) {
      if (!allowedSources.has(source)) {
        reasons.push(`lineage source ${source} is not declared for ${action.name} ${resourceName}`);
      }
    }
  }

  return reasons;
}

function recordValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.length > 0);
}

function eventActionRank(action: PolicyStrataRuntimeEventAction): number {
  switch (action) {
    case "allow":
      return 0;
    case "log_only":
      return 1;
    case "redact":
      return 2;
    case "require_approval":
      return 3;
    case "quarantine":
      return 4;
    case "deny":
      return 5;
  }
}

function controlEnabled(
  controls: Record<string, unknown>,
  name: string,
  defaultValue: boolean,
): boolean {
  const raw = controls[name];
  if (typeof raw === "boolean") return raw;
  const config = recordValue(raw);
  return typeof config.enabled === "boolean" ? config.enabled : defaultValue;
}

function controlRecord(
  controls: Record<string, unknown>,
  name: string,
): Record<string, unknown> {
  return recordValue(controls[name]);
}

function controlString(
  controls: Record<string, unknown>,
  control: string,
  key: string,
): string | undefined {
  return stringValue(controlRecord(controls, control)[key]);
}

function controlBool(
  controls: Record<string, unknown>,
  control: string,
  key: string,
): boolean {
  return controlRecord(controls, control)[key] === true;
}

function controlNumber(
  controls: Record<string, unknown>,
  control: string,
  key: string,
): number | undefined {
  const value = controlRecord(controls, control)[key];
  return typeof value === "number" && Number.isInteger(value) ? value : undefined;
}

function controlStringSet(
  controls: Record<string, unknown>,
  control: string,
  key: string,
): Set<string> {
  return new Set(stringArray(controlRecord(controls, control)[key]));
}

function missingAuthFields(
  actor: Record<string, unknown>,
  controls: Record<string, unknown>,
): string[] {
  const required = stringArray(controlRecord(controls, "authContext").requiredFields);
  const fields = required.length > 0 ? required : ["userId", "tenantId", "role"];
  return fields.filter((field) => !stringValue(actor[field]) && !stringValue(actor[camelToSnake(field)]));
}

function camelToSnake(value: string): string {
  return value.replace(/[A-Z]/g, (match) => `_${match.toLowerCase()}`).replace(/^_/, "");
}

function tenantMismatch(
  actor: Record<string, unknown>,
  resource: Record<string, unknown>,
): boolean {
  const actorTenant = stringValue(actor.tenantId) ?? stringValue(actor.tenant_id);
  const resourceTenant = stringValue(resource.tenantId) ?? stringValue(resource.tenant_id);
  return Boolean(actorTenant && resourceTenant && actorTenant !== resourceTenant);
}

function missingEntitlements(
  actor: Record<string, unknown>,
  resource: Record<string, unknown>,
): string[] {
  const actorEntitlements = new Set(stringArray(actor.entitlements));
  const requiredEntitlements = stringArray(resource.requiredEntitlements);
  const required =
    requiredEntitlements.length > 0 ? requiredEntitlements : stringArray(resource.required_entitlements);
  const entitlement = stringValue(resource.entitlement);
  const finalRequired = required.length > 0 ? required : entitlement ? [entitlement] : [];
  return finalRequired.filter((item) => !actorEntitlements.has(item));
}

function resourceName(resource: Record<string, unknown>): string | undefined {
  return stringValue(resource.name) ?? stringValue(resource.id);
}

function resourceUriOrName(resource: Record<string, unknown>): string | undefined {
  return stringValue(resource.uri) ?? resourceName(resource);
}

function eventApprovalSatisfied(input: PolicyStrataRuntimeEventInput): boolean {
  if (eventBool(input, "approvalRequiredSatisfied", "approval_required_satisfied")) return true;
  const decision = recordValue(input.decision);
  return Boolean(stringValue(decision.approvalRef) ?? stringValue(input.approvalRef));
}

function eventBool(input: PolicyStrataRuntimeEventInput, ...keys: string[]): boolean {
  const payload = recordValue(input.payload);
  for (const key of keys) {
    const value = input[key] ?? payload[key];
    if (typeof value === "boolean") return value;
  }
  return false;
}

function eventText(input: PolicyStrataRuntimeEventInput, ...keys: string[]): string | undefined {
  const payload = recordValue(input.payload);
  for (const key of keys) {
    const value = stringValue(input[key]) ?? stringValue(payload[key]);
    if (value) return value;
  }
  return undefined;
}

function eventNumber(input: PolicyStrataRuntimeEventInput, ...keys: string[]): number | undefined {
  const payload = recordValue(input.payload);
  for (const key of keys) {
    const value = input[key] ?? payload[key];
    if (typeof value === "number" && Number.isInteger(value)) return value;
  }
  return undefined;
}

function classifySqlQueryRisk(sqlText: string | undefined): string {
  if (!sqlText) return "unknown";
  const normalized = normalizedSqlForDetection(sqlText).trimStart();
  if (/^(copy|unload|export)\b/.test(normalized) || /\binto\s+out(?:file|put)\b/.test(normalized)) {
    return "export";
  }
  if (/^(insert|update|delete|merge|truncate|drop|alter|create|grant|revoke)\b/.test(normalized)) {
    return "write";
  }
  if (/^(select|with|show|describe|explain)\b/.test(normalized)) {
    return "read";
  }
  return "unknown";
}

function sqlHasTenantPredicate(sqlText: string, tenantColumn: string): boolean {
  const normalized = normalizedSqlForDetection(sqlText);
  const escaped = escapeRegExp(tenantColumn.toLowerCase());
  const identifier = String.raw`(?:["'\[]?[\w.]+["'\]]?\.)?["'\[]?${escaped}["'\]]?`;
  const predicate = new RegExp(String.raw`\b(?:where|and|or|on)\s+[^;]*${identifier}\s*(?:=|in\b|is\b|between\b)`);
  return predicate.test(normalized);
}

function normalizedSqlForDetection(sqlText: string): string {
  return stripSqlComments(sqlText)
    .replace(/'(?:''|[^'])*'/g, "?")
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function sqlParameterizationIssues(sqlText: string): string[] {
  const text = stripSqlComments(sqlText);
  const issues: string[] = [];
  if (/'(?:''|[^'])*'/.test(text)) {
    issues.push("string_literal");
  }
  if (/(?:=|<|>|<=|>=|<>|!=)\s*\d+(?:\.\d+)?\b/.test(text)) {
    issues.push("numeric_literal");
  }
  return issues;
}

function stripSqlComments(sqlText: string): string {
  const chunks: string[] = [];
  let segmentStart = 0;
  let index = 0;

  while (index < sqlText.length) {
    const char = sqlText[index];
    const next = sqlText[index + 1];
    if (char === "/" && next === "*") {
      if (segmentStart < index) {
        chunks.push(sqlText.slice(segmentStart, index));
      }
      chunks.push(" ");
      index += 2;
      while (index < sqlText.length - 1 && !(sqlText[index] === "*" && sqlText[index + 1] === "/")) {
        index += 1;
      }
      index = index < sqlText.length - 1 ? index + 2 : sqlText.length;
      segmentStart = index;
      continue;
    }
    if (char === "-" && next === "-") {
      if (segmentStart < index) {
        chunks.push(sqlText.slice(segmentStart, index));
      }
      chunks.push(" ");
      index += 2;
      while (index < sqlText.length && sqlText[index] !== "\n") {
        index += 1;
      }
      segmentStart = index;
      continue;
    }
    index += 1;
  }

  if (segmentStart < sqlText.length) {
    chunks.push(sqlText.slice(segmentStart));
  }
  return chunks.join("");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function controlExpectedVersion(
  controls: Record<string, unknown>,
  resource: Record<string, unknown>,
): string | undefined {
  const schemaBinding = controlRecord(controls, "schemaBinding");
  const versions = recordValue(schemaBinding.currentVersions);
  const name = resourceName(resource);
  return (name ? stringValue(versions[name]) : undefined) ?? stringValue(schemaBinding.currentVersion);
}

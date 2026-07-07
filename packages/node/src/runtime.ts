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

export interface PolicyStrataRuntimeEventInput {
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
  payloadHash?: string;
  artifactRefs?: readonly string[];
  findingIds?: readonly string[];
  payload?: Record<string, unknown>;
  approvalRequiredSatisfied?: boolean;
  promptInjection?: boolean;
  tainted?: boolean;
  [key: string]: unknown;
}

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
  decision: PolicyStrataRuntimeEventDecision;
  event: PolicyStrataRuntimeEventInput & { decision: PolicyStrataRuntimeEventDecision };
}

interface NormalizedRuntimeAction {
  name: string;
  kind?: string;
  allowedRoles: readonly string[];
  approvalRequired: boolean;
  requiresWriteGrant: boolean;
  semanticConstraints?: PolicyStrataRuntimeSemanticConstraints;
  releaseConstraints?: PolicyStrataRuntimeReleaseConstraints;
}

interface NormalizedRuntimeResource {
  name: string;
  type?: string;
  actions: Map<string, NormalizedRuntimeAction>;
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
        subject: { role: input.role },
        action,
        resource: input.toolName,
        context: {
          allowWriteTools: writeState === "enabled",
          approvalRequiredSatisfied:
            decisionPoint === "execution" ? approvalState === "satisfied" : true,
          semanticIr: input.semanticIr,
        },
        mode: input.mode,
      });
      const reasons = decision.reasons.map((reason) =>
        reason === `unknown resource: ${input.toolName}` ? `unknown tool: ${input.toolName}` : reason,
      );
      if (runtimeAction?.kind && input.toolKind && input.toolKind !== runtimeAction.kind) {
        reasons.push(
          `tool kind context ${input.toolKind} does not match manifest kind ${runtimeAction.kind} for ${input.toolName}`,
        );
      }

      return {
        ...decision,
        allowed: reasons.length === 0,
        reasons,
        toolName: input.toolName,
        normalizedRole: decision.normalizedRoles[0],
        toolKind: runtimeAction?.kind,
        userId: optionalString(input.userId),
        householdId: optionalString(input.householdId),
        writeState,
        approvalState,
        decisionPoint,
      };
    },
    authorizeRelease(input) {
      const decision = authorize({
        subject: input.subject,
        action: "release",
        resource: input.resource,
        context: {
          ...(input.context ?? {}),
          release: {
            boundary: input.boundary,
            result: input.result,
            lineage: input.lineage,
          },
        },
        mode: input.mode,
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
  let action: PolicyStrataRuntimeEventAction = "allow";
  let controlId: string | undefined;

  function apply(nextAction: PolicyStrataRuntimeEventAction, reason: string, nextControlId: string) {
    reasons.push(reason);
    if (eventActionRank(nextAction) > eventActionRank(action)) {
      action = nextAction;
      controlId = nextControlId;
    }
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
    if (sqlText && !sqlText.toLowerCase().includes(tenantColumn.toLowerCase())) {
      apply("deny", `SQL statement is missing tenant predicate ${tenantColumn}`, "tenant_scope_required");
    }
    if (tenantMismatch(actor, resource)) {
      apply("deny", "SQL resource tenant does not match actor tenant", "tenant_scope_required");
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
    if (destination && allowedDestinations.size > 0 && !allowedDestinations.has(destination)) {
      apply("deny", `egress destination ${destination} is not approved`, "egress_approval_required");
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
  };
  return {
    eventId: input.eventId,
    allowed,
    action,
    reason,
    reasons,
    layer: input.layer,
    operation: input.operation,
    controlId,
    policyRefs: [...(input.policyRefs ?? [])],
    redactions,
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
            approvalRequired: tool.approvalRequired,
            requiresWriteGrant: tool.kind === "write",
            metrics: tool.metrics,
            dimensions: tool.dimensions,
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
  return { metrics, dimensions };
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
  if (nonReleaseActions.length === 1) return nonReleaseActions[0];
  if (resource.actions.size !== 1) return "run";
  return [...resource.actions.keys()][0];
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
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
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

function controlExpectedVersion(
  controls: Record<string, unknown>,
  resource: Record<string, unknown>,
): string | undefined {
  const schemaBinding = controlRecord(controls, "schemaBinding");
  const versions = recordValue(schemaBinding.currentVersions);
  const name = resourceName(resource);
  return (name ? stringValue(versions[name]) : undefined) ?? stringValue(schemaBinding.currentVersion);
}

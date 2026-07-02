export type PolicyStrataRuntimeMode = "shadow" | "enforce";
export type PolicyStrataRuntimeDefaultDecision = "deny";
export type PolicyStrataRuntimeToolKind = "read" | "write" | "export" | "memory" | "external";

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
  role?: string | null;
  allowWriteTools?: boolean;
  approvalRequiredSatisfied?: boolean;
  semanticIr?: PolicyStrataRuntimeSemanticIr | null;
  mode?: PolicyStrataRuntimeMode;
}

export interface PolicyStrataAuthorizeToolDecision extends PolicyStrataAuthorizeDecision {
  toolName: string;
  normalizedRole?: string;
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
      const decision = authorize({
        subject: { role: input.role },
        action,
        resource: input.toolName,
        context: {
          allowWriteTools: input.allowWriteTools,
          approvalRequiredSatisfied: input.approvalRequiredSatisfied,
          semanticIr: input.semanticIr,
        },
        mode: input.mode,
      });
      const reasons = decision.reasons.map((reason) =>
        reason === `unknown resource: ${input.toolName}` ? `unknown tool: ${input.toolName}` : reason,
      );

      return {
        ...decision,
        allowed: reasons.length === 0,
        reasons,
        toolName: input.toolName,
        normalizedRole: decision.normalizedRoles[0],
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
  };
}

export function authorize(
  manifest: PolicyStrataRuntimeManifest,
  input: PolicyStrataAuthorizeInput,
): PolicyStrataAuthorizeDecision {
  return createPolicyStrataAuthorizer(manifest).authorize(input);
}

export function authorizeRelease(
  manifest: PolicyStrataRuntimeManifest,
  input: PolicyStrataAuthorizeReleaseInput,
): PolicyStrataAuthorizeReleaseDecision {
  return createPolicyStrataAuthorizer(manifest).authorizeRelease(input);
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

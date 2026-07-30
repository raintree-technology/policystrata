import { createHash, timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import {
  evaluateRuntimeEvent,
  evaluateRuntimeEvents,
  parsePolicyStrataRuntimeEvent,
  type PolicyStrataRuntimeEventDecision,
  type PolicyStrataRuntimeEventEvaluation,
  type PolicyStrataRuntimeEventInput,
  type PolicyStrataRuntimeManifest,
  type PolicyStrataPolicyLayer,
} from "policystrata/runtime";

export const POLICYSTRATA_GATEWAY_VERSION = "0.1.3";

export type AgentTrustGatewayMode = "shadow" | "enforce";

export interface RuntimeEventBatchPayload {
  events: readonly PolicyStrataRuntimeEventInput[];
}

export type NativeIntegrationProvider =
  | "github"
  | "vercel"
  | "datadog"
  | "snowflake"
  | "slack"
  | "jira"
  | "aws"
  | "gcp"
  | "azure";

export interface NativeIntegrationEvidenceInput {
  provider: NativeIntegrationProvider;
  project: string;
  connectionId: string;
  eventType?: string;
  observedAt?: string;
  decision?: PolicyStrataRuntimeEventDecision["action"];
  summary?: string;
  evidenceRefs?: readonly string[];
  payload?: Record<string, unknown>;
}

export type RuntimeEventPayload = PolicyStrataRuntimeEventInput | RuntimeEventBatchPayload;

export type RuntimeEventWithDecision = PolicyStrataRuntimeEventInput & {
  decision: PolicyStrataRuntimeEventDecision;
};

export interface GatewayDecisionResult {
  ok: boolean;
  mode: AgentTrustGatewayMode;
  events: RuntimeEventWithDecision[];
  decisions: PolicyStrataRuntimeEventEvaluation[];
}

export interface RuntimeEventUploadOptions {
  apiUrl: string;
  token?: string;
  organizationId?: string;
  path?: string;
  idempotencyKey?: string;
  maxBodyBytes?: number;
  includePayload?: boolean;
  allowBoundaryViolations?: boolean;
  fetch?: typeof fetch;
}

export interface RuntimeEventUploadResult {
  ok: boolean;
  status: number;
  body: unknown;
}

export interface AgentTrustGatewayOptions {
  manifest: PolicyStrataRuntimeManifest;
  mode?: AgentTrustGatewayMode;
  upload?: RuntimeEventUploadOptions;
  gatewayToken?: string;
  failOnUploadError?: boolean;
  maxBodyBytes?: number;
}

export interface StartedAgentTrustGateway {
  server: Server;
  url: string;
  close(): Promise<void>;
}

export interface MetadataBoundaryFinding {
  path: string;
  reason: string;
  severity: "high" | "critical";
}

export class PolicyStrataGatewayBlockedError extends Error {
  readonly result: GatewayDecisionResult;

  constructor(result: GatewayDecisionResult) {
    super(result.decisions.map((decision) => decision.reason).join("; ") || "runtime policy blocked event");
    this.name = "PolicyStrataGatewayBlockedError";
    this.result = result;
  }
}

export function nativeIntegrationRuntimeEvent(
  input: NativeIntegrationEvidenceInput,
): PolicyStrataRuntimeEventInput {
  const eventType = input.eventType ?? defaultIntegrationEventType(input.provider);
  const evidenceRefs = input.evidenceRefs ?? [`integration://${input.provider}/${input.connectionId}`];
  const payload = {
    storageMode: "metadata_only",
    provider: input.provider,
    connectionId: input.connectionId,
    ...(input.payload ?? {}),
  };
  const event: PolicyStrataRuntimeEventInput = {
    schemaVersion: "0.2.0",
    eventId: `integration-${input.provider}-${input.connectionId}-${sha256Json(payload).slice(0, 16)}`,
    project: input.project,
    observedAt: input.observedAt ?? new Date().toISOString(),
    agent: {
      key: `${input.provider}-integration`,
      name: `${input.provider} integration`,
      kind: "integration",
    },
    layer: defaultIntegrationLayer(input.provider),
    operation: eventType,
    summary: input.summary ?? `${input.provider} evidence synchronized for ${input.project}`,
    decision: {
      action: input.decision ?? defaultIntegrationDecision(input.provider),
      reason: `${input.provider} provider evidence`,
      control: {
        id: `${input.provider}.native_integration`,
        mode: "release_gate",
        objective: "Use native provider evidence in Clearance gates",
      },
    },
    provider: input.provider,
    integrationConnectionId: input.connectionId,
    externalRefs: evidenceRefs.map((ref) => ({
      provider: input.provider,
      ref,
      kind: "evidence",
      connectionId: input.connectionId,
    })),
    artifactRefs: [...evidenceRefs],
    payloadHash: sha256Json(payload),
  };
  return event;
}

export function decideRuntimeEvent(
  manifest: PolicyStrataRuntimeManifest,
  event: PolicyStrataRuntimeEventInput,
  mode: AgentTrustGatewayMode = "enforce",
): GatewayDecisionResult {
  const decision = evaluateRuntimeEvent(manifest, event);
  return decisionResult([decision], mode);
}

export function decideRuntimeEvents(
  manifest: PolicyStrataRuntimeManifest,
  events: readonly PolicyStrataRuntimeEventInput[],
  mode: AgentTrustGatewayMode = "enforce",
): GatewayDecisionResult {
  return decisionResult(evaluateRuntimeEvents(manifest, events), mode);
}

export function decideRuntimePayload(
  manifest: PolicyStrataRuntimeManifest,
  payload: unknown,
  mode: AgentTrustGatewayMode = "enforce",
): GatewayDecisionResult {
  return decideRuntimeEvents(manifest, runtimeEventsFromPayload(payload), mode);
}

export async function guardRuntimePayload(
  manifest: PolicyStrataRuntimeManifest,
  payload: unknown,
  mode: AgentTrustGatewayMode = "enforce",
): Promise<GatewayDecisionResult> {
  const result = decideRuntimePayload(manifest, payload, mode);
  if (mode === "enforce" && !result.ok) {
    throw new PolicyStrataGatewayBlockedError(result);
  }
  return result;
}

export function runtimeEventsFromPayload(payload: unknown): PolicyStrataRuntimeEventInput[] {
  if (Array.isArray(payload)) {
    return payload.map(parsePolicyStrataRuntimeEvent);
  }
  const record = recordValue(payload);
  if (Array.isArray(record.events)) {
    return record.events.map(parsePolicyStrataRuntimeEvent);
  }
  return [parsePolicyStrataRuntimeEvent(payload)];
}

export function redactRuntimeEventForUpload(event: RuntimeEventWithDecision): RuntimeEventWithDecision {
  const {
    expectedDecision: _expectedDecision,
    expected_decision: _expectedDecisionSnake,
    payload: _payload,
    ...redacted
  } = event;
  return redacted;
}

export function scanMetadataBoundary(payload: unknown): MetadataBoundaryFinding[] {
  const findings: MetadataBoundaryFinding[] = [];
  for (const [path, value] of walkPayload(payload)) {
    const key = path.split(".").at(-1) ?? path;
    if (SENSITIVE_KEY_PATTERN.test(key)) {
      findings.push({
        path,
        reason: `sensitive field name: ${key}`,
        severity: "critical",
      });
    }
    if (typeof value === "string") {
      for (const [pattern, label] of SECRET_VALUE_PATTERNS) {
        if (pattern.test(value)) {
          findings.push({
            path,
            reason: `possible ${label}`,
            severity: "critical",
          });
        }
      }
    }
  }
  return findings;
}

export function assertMetadataBoundary(payload: unknown): void {
  const findings = scanMetadataBoundary(payload);
  if (findings.length > 0) {
    const first = findings[0];
    if (!first) {
      throw new Error("metadata-only boundary violation");
    }
    throw new Error(`metadata-only boundary violation at ${first.path}: ${first.reason}`);
  }
}

function runtimeEventForUpload(
  event: RuntimeEventWithDecision,
  includePayload: boolean,
): RuntimeEventWithDecision {
  const { expectedDecision: _expectedDecision, ...withoutExpectation } = event;
  if (includePayload) return withoutExpectation;
  return redactRuntimeEventForUpload(event);
}

export async function uploadRuntimeEvents(
  options: RuntimeEventUploadOptions & { events: readonly RuntimeEventWithDecision[] },
): Promise<RuntimeEventUploadResult> {
  const client = options.fetch ?? fetch;
  const events = options.events.map((event) => runtimeEventForUpload(event, options.includePayload === true));
  const uploadBody = JSON.stringify({
    gateway: {
      name: "@policystrata/agent-trust-gateway",
      version: POLICYSTRATA_GATEWAY_VERSION,
    },
    events,
  });
  const maxBodyBytes = options.maxBodyBytes ?? 1_000_000;
  if (Buffer.byteLength(uploadBody, "utf8") > maxBodyBytes) {
    throw new Error(`runtime event upload payload is too large: exceeds ${maxBodyBytes} bytes`);
  }
  if (options.allowBoundaryViolations !== true) {
    assertMetadataBoundary({ events });
  }
  const response = await client(runtimeEventsEndpoint(options), {
    method: "POST",
    headers: uploadHeaders(options),
    body: uploadBody,
  });
  const body = await responseBody(response);
  return {
    ok: response.ok,
    status: response.status,
    body,
  };
}

export function createAgentTrustGatewayHandler(
  options: AgentTrustGatewayOptions,
): (request: IncomingMessage, response: ServerResponse) => void {
  const mode = options.mode ?? "enforce";
  const maxBodyBytes = options.maxBodyBytes ?? 1_000_000;
  const gatewayToken = resolveGatewayToken(options.gatewayToken);

  return (request, response) => {
    void handleRequest(request, response, options, mode, maxBodyBytes, gatewayToken);
  };
}

export function createAgentTrustGatewayServer(options: AgentTrustGatewayOptions): Server {
  return createServer(createAgentTrustGatewayHandler(options));
}

export async function startAgentTrustGateway(
  options: AgentTrustGatewayOptions & { host?: string; port?: number },
): Promise<StartedAgentTrustGateway> {
  const server = createAgentTrustGatewayServer(options);
  const host = options.host ?? "127.0.0.1";
  const port = options.port ?? 8787;
  if (!isLoopbackHost(host) && !resolveGatewayToken(options.gatewayToken)) {
    throw new Error("POLICYSTRATA_GATEWAY_TOKEN or --gateway-token is required when binding beyond loopback");
  }
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      server.off("error", reject);
      resolve();
    });
  });
  const address = server.address();
  if (!address || typeof address === "string") {
    throw new Error("runtime gateway did not bind to a TCP address");
  }
  return {
    server,
    url: `http://${address.address}:${address.port}`,
    close: () =>
      new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
      }),
  };
}

async function handleRequest(
  request: IncomingMessage,
  response: ServerResponse,
  options: AgentTrustGatewayOptions,
  mode: AgentTrustGatewayMode,
  maxBodyBytes: number,
  gatewayToken: string | undefined,
): Promise<void> {
  try {
    const url = new URL(request.url ?? "/", "http://localhost");
    if (request.method === "GET" && url.pathname === "/healthz") {
      sendJson(response, 200, { ok: true, service: "policystrata-agent-trust-gateway" });
      return;
    }
    if (request.method !== "POST" || url.pathname !== "/v1/decide") {
      sendJson(response, 404, { ok: false, error: "not_found" });
      return;
    }
    if (gatewayToken && !isAuthorizedGatewayRequest(request, gatewayToken)) {
      sendJson(response, 401, { ok: false, error: "unauthorized" });
      return;
    }

    const payload = await readJsonBody(request, maxBodyBytes);
    const result = decideRuntimePayload(options.manifest, payload, mode);
    let upload: RuntimeEventUploadResult | undefined;
    if (options.upload) {
      upload = await uploadRuntimeEvents({ ...options.upload, events: result.events });
    }
    const uploadFailed = Boolean(upload && !upload.ok && options.failOnUploadError);
    const status = uploadFailed ? 502 : !result.ok && mode === "enforce" ? 403 : 200;
    sendJson(response, status, {
      ...result,
      ...(upload
        ? { upload: { ok: upload.ok, status: upload.status, body: upload.body } }
        : {}),
    });
  } catch (error) {
    sendJson(response, 400, {
      ok: false,
      error: error instanceof Error ? error.message : "invalid runtime gateway request",
    });
  }
}

function decisionResult(
  decisions: readonly PolicyStrataRuntimeEventEvaluation[],
  mode: AgentTrustGatewayMode,
): GatewayDecisionResult {
  return {
    ok: decisions.every((decision) => decision.allowed),
    mode,
    events: decisions.map((decision) => decision.event),
    decisions: [...decisions],
  };
}

function runtimeEventsEndpoint(options: RuntimeEventUploadOptions): string {
  return new URL(options.path ?? "/api/v1/runtime-events", options.apiUrl).toString();
}

function uploadHeaders(options: RuntimeEventUploadOptions): HeadersInit {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (options.token) {
    headers.authorization = `Bearer ${options.token}`;
  }
  if (options.organizationId) {
    headers["x-clearance-organization-id"] = options.organizationId;
  }
  if (options.idempotencyKey) {
    headers["idempotency-key"] = options.idempotencyKey;
  }
  return headers;
}

function resolveGatewayToken(explicitToken: string | undefined): string | undefined {
  return explicitToken || process.env.POLICYSTRATA_GATEWAY_TOKEN;
}

function isLoopbackHost(host: string): boolean {
  const normalized = host.trim().toLowerCase();
  return (
    normalized === "localhost" ||
    normalized === "127.0.0.1" ||
    normalized === "::1" ||
    normalized === "[::1]"
  );
}

function isAuthorizedGatewayRequest(request: IncomingMessage, gatewayToken: string): boolean {
  const authorization = request.headers.authorization ?? "";
  const credential = authorization.toLowerCase().startsWith("bearer ")
    ? authorization.slice(7).trim()
    : "";
  if (!credential) return false;
  const left = Buffer.from(credential);
  const right = Buffer.from(gatewayToken);
  return left.length === right.length && timingSafeEqual(left, right);
}

async function responseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function readJsonBody(request: IncomingMessage, maxBodyBytes: number): Promise<unknown> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.byteLength;
    if (total > maxBodyBytes) {
      throw new Error("runtime gateway request body is too large");
    }
    chunks.push(buffer);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw.trim()) {
    throw new Error("runtime gateway request body is empty");
  }
  const parsed: unknown = JSON.parse(raw);
  return parsed;
}

function sendJson(response: ServerResponse, status: number, payload: unknown): void {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(`${JSON.stringify(payload)}\n`);
}

function recordValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

const SENSITIVE_KEY_PATTERN =
  /(?:^|[_\-.])(api[_\-.]?key|authorization|bearer|cookie|credential|customer[_\-.]?rows|doc[_\-.]?text|documents?|full[_\-.]?trace|input[_\-.]?schema|output[_\-.]?schema|password|passwd|private[_\-.]?schema|prompt|raw[_\-.]?docs?|raw[_\-.]?documents?|raw[_\-.]?payload|raw[_\-.]?prompt|rows|sampled[_\-.]?rows|secret|source[_\-.]?credentials|token|tool[_\-.]?(?:input|output|payload|request|response))(?:$|[_\-.])/i;

const SECRET_VALUE_PATTERNS: readonly [RegExp, string][] = [
  [/\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b/i, "bearer token"],
  [/\b(?:api[_-]?key|password|passwd|secret|token)\s*[:=]\s*[^\s,;]+/i, "secret assignment"],
  [/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/, "JWT"],
  [/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i, "email address"],
  [/\b(?:\d[ -]*?){13,19}\b/, "possible payment card"],
  [/\bsk-[A-Za-z0-9_-]{16,}\b/, "API key"],
  [/\bgh[pousr]_[A-Za-z0-9_]{20,}\b/, "API key"],
  [/\bAKIA[0-9A-Z]{16}\b/, "API key"],
  [/https?:\/\/[^\s?#]+[^\s]*[?&](?:api[_-]?key|token|secret|password)=[^&\s]+/i, "secret in URL"],
];

function* walkPayload(value: unknown, prefix = "$"): Generator<[string, unknown]> {
  yield [prefix, value];
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      yield* walkPayload(value[index], `${prefix}[${index}]`);
    }
    return;
  }
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value)) {
    yield* walkPayload(child, `${prefix}.${key}`);
  }
}

function defaultIntegrationEventType(provider: NativeIntegrationProvider): string {
  switch (provider) {
    case "github":
      return "github.check_gate";
    case "vercel":
      return "vercel.deployment_gate";
    case "datadog":
      return "datadog.monitor_signal";
    case "snowflake":
      return "snowflake.data_policy_signal";
    case "slack":
      return "slack.approval_channel";
    case "jira":
      return "jira.workflow_gate";
    case "aws":
      return "aws.control_plane_signal";
    case "gcp":
      return "gcp.control_plane_signal";
    case "azure":
      return "azure.control_plane_signal";
    default:
      return exhaustiveProvider(provider);
  }
}

function defaultIntegrationLayer(provider: NativeIntegrationProvider): PolicyStrataPolicyLayer {
  switch (provider) {
    case "snowflake":
      return "sql";
    case "aws":
    case "gcp":
    case "azure":
    case "vercel":
      return "egress";
    case "datadog":
    case "github":
    case "slack":
    case "jira":
      return "trace";
    default:
      return exhaustiveProvider(provider);
  }
}

function defaultIntegrationDecision(provider: NativeIntegrationProvider): PolicyStrataRuntimeEventDecision["action"] {
  switch (provider) {
    case "github":
    case "vercel":
      return "allow";
    case "datadog":
    case "snowflake":
    case "slack":
    case "jira":
    case "aws":
    case "gcp":
    case "azure":
      return "require_approval";
    default:
      return exhaustiveProvider(provider);
  }
}

function sha256Json(value: unknown): string {
  return createHash("sha256")
    .update(JSON.stringify(value, Object.keys(recordValue(value)).sort()))
    .digest("hex");
}

function exhaustiveProvider(provider: never): never {
  throw new Error(`Unsupported native integration provider: ${provider}`);
}

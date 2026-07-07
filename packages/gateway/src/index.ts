import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import type { AddressInfo } from "node:net";

import {
  evaluateRuntimeEvent,
  evaluateRuntimeEvents,
  type PolicyStrataRuntimeEventDecision,
  type PolicyStrataRuntimeEventEvaluation,
  type PolicyStrataRuntimeEventInput,
  type PolicyStrataRuntimeManifest,
} from "policystrata/runtime";

export type AgentTrustGatewayMode = "shadow" | "enforce";

export interface RuntimeEventBatchPayload {
  events: readonly PolicyStrataRuntimeEventInput[];
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
  includePayload?: boolean;
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
  failOnUploadError?: boolean;
  maxBodyBytes?: number;
}

export interface StartedAgentTrustGateway {
  server: Server;
  url: string;
  close(): Promise<void>;
}

export class PolicyStrataGatewayBlockedError extends Error {
  readonly result: GatewayDecisionResult;

  constructor(result: GatewayDecisionResult) {
    super(result.decisions.map((decision) => decision.reason).join("; ") || "runtime policy blocked event");
    this.name = "PolicyStrataGatewayBlockedError";
    this.result = result;
  }
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
    return payload.map(assertRuntimeEvent);
  }
  const record = recordValue(payload);
  if (Array.isArray(record.events)) {
    return record.events.map(assertRuntimeEvent);
  }
  return [assertRuntimeEvent(payload)];
}

export function redactRuntimeEventForUpload(event: RuntimeEventWithDecision): RuntimeEventWithDecision {
  const { expectedDecision: _expectedDecision, payload: _payload, ...redacted } = event;
  return redacted;
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
  const response = await client(runtimeEventsEndpoint(options), {
    method: "POST",
    headers: uploadHeaders(options),
    body: JSON.stringify({ events }),
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

  return (request, response) => {
    void handleRequest(request, response, options, mode, maxBodyBytes);
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
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      server.off("error", reject);
      resolve();
    });
  });
  const address = server.address() as AddressInfo;
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
      upload: upload ? { ok: upload.ok, status: upload.status, body: upload.body } : undefined,
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

function assertRuntimeEvent(value: unknown): PolicyStrataRuntimeEventInput {
  const event = recordValue(value);
  for (const key of ["schemaVersion", "eventId", "project", "observedAt", "agent", "layer", "operation", "summary"]) {
    if (event[key] === undefined) {
      throw new Error(`runtime event is missing ${key}`);
    }
  }
  return event as unknown as PolicyStrataRuntimeEventInput;
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
    headers["x-assurance-organization-id"] = options.organizationId;
  }
  return headers;
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
  return JSON.parse(raw) as unknown;
}

function sendJson(response: ServerResponse, status: number, payload: unknown): void {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(`${JSON.stringify(payload)}\n`);
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

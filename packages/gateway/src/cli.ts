#!/usr/bin/env node
import { readFile, writeFile } from "node:fs/promises";

import {
  decideRuntimePayload,
  startAgentTrustGateway,
  type AgentTrustGatewayMode,
  type RuntimeEventUploadOptions,
} from "./index.js";
import { parsePolicyStrataRuntimeManifest } from "policystrata/runtime";

type Flags = Record<string, string | boolean>;

async function main(argv: string[]): Promise<number> {
  const command = argv[0];
  const flags = parseFlags(argv.slice(1));
  if (!command || flags.help === true || flags.h === true) {
    printHelp();
    return command ? 0 : 2;
  }

  if (command === "decide") {
    const manifest = parsePolicyStrataRuntimeManifest(
      await readJson(requiredString(flags, "manifest")),
    );
    const eventPayload = await readJson(requiredString(flags, "event"));
    const mode = modeFlag(flags);
    const result = decideRuntimePayload(manifest, eventPayload, mode);
    const body = `${JSON.stringify(result, null, 2)}\n`;
    const out = optionalString(flags, "out");
    if (out) {
      await writeFile(out, body, "utf8");
    } else {
      process.stdout.write(body);
    }
    return result.ok || mode === "shadow" ? 0 : 1;
  }

  if (command === "serve") {
    const manifest = parsePolicyStrataRuntimeManifest(
      await readJson(requiredString(flags, "manifest")),
    );
    const upload = uploadOptions(flags);
    const host = optionalString(flags, "host");
    const gatewayToken =
      optionalString(flags, "gateway-token") ?? process.env.POLICYSTRATA_GATEWAY_TOKEN;
    const gateway = await startAgentTrustGateway({
      manifest,
      ...(host ? { host } : {}),
      port: numberFlag(flags, "port") ?? 8787,
      mode: modeFlag(flags),
      ...(upload ? { upload } : {}),
      ...(gatewayToken ? { gatewayToken } : {}),
      failOnUploadError: flags["fail-on-upload-error"] === true,
    });
    process.stderr.write(`PolicyStrata Agent Trust Gateway listening at ${gateway.url}\n`);
    await waitForShutdown(gateway.close);
    return 0;
  }

  throw new Error(`unknown command: ${command}`);
}

function parseFlags(argv: string[]): Flags {
  const flags: Flags = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (item === undefined) {
      throw new Error(`missing argument at index ${index}`);
    }
    if (!item.startsWith("--")) {
      throw new Error(`unexpected argument: ${item}`);
    }
    const key = item.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) {
      flags[key] = true;
      continue;
    }
    flags[key] = next;
    index += 1;
  }
  return flags;
}

function uploadOptions(flags: Flags): RuntimeEventUploadOptions | undefined {
  const apiUrl = optionalString(flags, "api-url");
  if (!apiUrl) return undefined;
  const token = optionalString(flags, "token") ?? process.env.POLICYSTRATA_CONTROL_PLANE_TOKEN;
  const organizationId = optionalString(flags, "organization-id");
  return {
    apiUrl,
    ...(token ? { token } : {}),
    ...(organizationId ? { organizationId } : {}),
    includePayload: flags["include-payload"] === true,
  };
}

function modeFlag(flags: Flags): AgentTrustGatewayMode {
  if (flags.shadow === true) return "shadow";
  const raw = optionalString(flags, "mode");
  if (raw === "shadow" || raw === "enforce") return raw;
  if (raw) {
    throw new Error("--mode must be shadow or enforce");
  }
  return "enforce";
}

function numberFlag(flags: Flags, key: string): number | undefined {
  const raw = optionalString(flags, key);
  if (!raw) return undefined;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`--${key} must be a non-negative integer`);
  }
  return parsed;
}

function requiredString(flags: Flags, key: string): string {
  const value = optionalString(flags, key);
  if (!value) {
    throw new Error(`missing --${key}`);
  }
  return value;
}

function optionalString(flags: Flags, key: string): string | undefined {
  const value = flags[key];
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

async function readJson(path: string): Promise<unknown> {
  const parsed: unknown = JSON.parse(await readFile(path, "utf8"));
  return parsed;
}

function waitForShutdown(close: () => Promise<void>): Promise<void> {
  return new Promise((resolve, reject) => {
    const stop = () => {
      close().then(resolve, reject);
    };
    process.once("SIGINT", stop);
    process.once("SIGTERM", stop);
  });
}

function printHelp(): void {
  process.stdout.write(`PolicyStrata Agent Trust Gateway

Usage:
  agent-trust-gateway decide --manifest manifest.json --event event.json [--out decisions.json] [--mode enforce|shadow]
  agent-trust-gateway serve --manifest manifest.json [--host 127.0.0.1] [--port 8787] [--api-url http://localhost:3000]

Options:
  --shadow                    Alias for --mode shadow.
  --api-url                   PolicyStrata control-plane base URL for redacted event uploads.
  --token                     Control-plane bearer token. Defaults to POLICYSTRATA_CONTROL_PLANE_TOKEN.
  --organization-id           Optional organization header for the control plane.
  --include-payload           Upload event payloads instead of stripping them. Off by default.
  --gateway-token             Bearer token required by /v1/decide. Defaults to POLICYSTRATA_GATEWAY_TOKEN.
  --fail-on-upload-error      Return 502 when the control-plane upload fails.
`);
}

main(process.argv.slice(2)).then(
  (code) => {
    process.exitCode = code;
  },
  (error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  },
);

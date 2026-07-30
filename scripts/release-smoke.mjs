#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const flags = new Set(process.argv.slice(2));

if (flags.size === 0 || flags.has("--help")) {
  process.stdout.write(`PolicyStrata release smoke checks

Usage:
  node scripts/release-smoke.mjs --python-artifact --npm-artifacts
  node scripts/release-smoke.mjs --npm-runtime-artifact
  node scripts/release-smoke.mjs --gateway-artifact
  node scripts/release-smoke.mjs --published-pypi --published-npm-runtime --published-gateway

Environment overrides:
  POLICYSTRATA_PYPI_VERSION
  POLICYSTRATA_NPM_VERSION
  POLICYSTRATA_GATEWAY_VERSION
  POLICYSTRATA_RELEASE_SMOKE_RETRIES
`);
  process.exit(flags.has("--help") ? 0 : 2);
}

if (flags.has("--python-artifact")) {
  smokePythonArtifact();
}
if (flags.has("--npm-artifacts")) {
  smokeNpmRuntimeArtifact();
  smokeGatewayArtifact();
}
if (flags.has("--npm-runtime-artifact")) {
  smokeNpmRuntimeArtifact();
}
if (flags.has("--gateway-artifact")) {
  smokeGatewayArtifact();
}
if (flags.has("--published-pypi")) {
  smokePublishedPyPI();
}
if (flags.has("--published-npm-runtime")) {
  smokePublishedNpmRuntime();
}
if (flags.has("--published-gateway")) {
  smokePublishedGateway();
}

function smokePythonArtifact() {
  const dist = join(root, "dist");
  rmSync(dist, { recursive: true, force: true });
  run("uv", ["build"]);
  const distributions = readdirSync(dist)
    .filter((file) => file.endsWith(".whl") || file.endsWith(".tar.gz"))
    .map((file) => join(dist, file));
  run("uv", ["run", "twine", "check", "--strict", ...distributions]);
  const wheel = distributions.find((file) => file.endsWith(".whl"));
  if (!wheel) throw new Error("uv build did not produce a wheel");
  const sourceDistribution = distributions.find((file) => file.endsWith(".tar.gz"));
  if (!sourceDistribution) throw new Error("uv build did not produce a source distribution");
  assertPythonSourceDistribution(sourceDistribution);

  const temp = mkdtempSync(join(tmpdir(), "policystrata-python-artifact-"));
  try {
    const fixtures = writeRuntimeFixtures(temp);
    const venv = join(temp, ".venv");
    run("uv", ["venv", venv]);
    const python = join(venv, process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
    const policystrata = join(venv, process.platform === "win32" ? "Scripts/policystrata.exe" : "bin/policystrata");
    run("uv", ["pip", "install", "--python", python, wheel]);
    run(policystrata, ["schema", "--kind", "runtime-event", "--out", join(temp, "runtime-event.schema.json")]);
    run(policystrata, [
      "runtime-evaluate",
      "--manifest",
      fixtures.manifest,
      "--event",
      fixtures.events,
      "--assert-expected",
      "--out",
      join(temp, "runtime-decisions.json"),
    ]);
    run(policystrata, ["doctor", "--config", fixtures.config, "--out", join(temp, "doctor.json")]);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

function assertPythonSourceDistribution(archive) {
  const result = spawnSync("tar", ["-tzf", archive], {
    cwd: root,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(`could not list source distribution: ${result.stderr || `tar exited with ${result.status}`}`);
  }

  const archiveRoot = `${basename(archive).slice(0, -".tar.gz".length)}/`;
  const allowedRootFiles = new Set([
    "CITATION.cff",
    "LICENSE",
    "MANIFEST.in",
    "PKG-INFO",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
    "setup.cfg",
  ]);
  const violations = result.stdout
    .split("\n")
    .filter(Boolean)
    .filter((entry) => {
      if (entry === archiveRoot.slice(0, -1)) return false;
      if (!entry.startsWith(archiveRoot)) return true;
      const relative = entry.slice(archiveRoot.length);
      if (!relative) return false;
      const [topLevel] = relative.split("/");
      return topLevel !== "src" && !allowedRootFiles.has(relative);
    });
  if (violations.length > 0) {
    throw new Error(`source distribution contains unreviewed paths:\n${violations.join("\n")}`);
  }
}

function smokeNpmRuntimeArtifact() {
  const nodePackage = join(root, "packages/node");
  const nodeTarball = packPackage(nodePackage);
  const temp = mkdtempSync(join(tmpdir(), "policystrata-npm-artifacts-"));
  try {
    writeFileSync(join(temp, "package.json"), JSON.stringify({ private: true, type: "module" }), "utf8");
    run("npm", ["install", "--ignore-scripts", nodeTarball], { cwd: temp });
    const fixtures = writeRuntimeFixtures(temp);
    runNodeRuntimeSmoke(temp, fixtures);
  } finally {
    rmSync(temp, { recursive: true, force: true });
    rmSync(nodeTarball, { force: true });
  }
}

function smokeGatewayArtifact() {
  const nodePackage = join(root, "packages/node");
  const gatewayPackage = join(root, "packages/gateway");
  const nodeTarball = packPackage(nodePackage);
  const gatewayTarball = packPackage(gatewayPackage);
  const temp = mkdtempSync(join(tmpdir(), "policystrata-gateway-artifact-"));
  try {
    writeFileSync(join(temp, "package.json"), JSON.stringify({ private: true, type: "module" }), "utf8");
    run("npm", ["install", "--ignore-scripts", nodeTarball, gatewayTarball], { cwd: temp });
    const fixtures = writeRuntimeFixtures(temp);
    runNodeRuntimeSmoke(temp, fixtures);
    runGatewaySmoke(temp, fixtures);
  } finally {
    rmSync(temp, { recursive: true, force: true });
    rmSync(nodeTarball, { force: true });
    rmSync(gatewayTarball, { force: true });
  }
}

function smokePublishedPyPI() {
  const version = process.env.POLICYSTRATA_PYPI_VERSION || pyprojectVersion();
  const temp = mkdtempSync(join(tmpdir(), "policystrata-published-pypi-"));
  try {
    const fixtures = writeRuntimeFixtures(temp);
    const venv = join(temp, ".venv");
    run("uv", ["venv", venv]);
    const python = join(venv, process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
    const policystrata = join(venv, process.platform === "win32" ? "Scripts/policystrata.exe" : "bin/policystrata");
    retry(() =>
      run("uv", ["pip", "install", "--python", python, "--refresh-package", "policystrata", `policystrata==${version}`]),
    );
    run(policystrata, ["schema", "--kind", "runtime-event", "--out", join(temp, "runtime-event.schema.json")]);
    run(policystrata, [
      "runtime-evaluate",
      "--manifest",
      fixtures.manifest,
      "--event",
      fixtures.events,
      "--assert-expected",
      "--out",
      join(temp, "runtime-decisions.json"),
    ]);
    run(policystrata, ["doctor", "--config", fixtures.config, "--out", join(temp, "doctor.json")]);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

function smokePublishedNpmRuntime() {
  const version = process.env.POLICYSTRATA_NPM_VERSION || readPackageJson(join(root, "packages/node")).version;
  const temp = mkdtempSync(join(tmpdir(), "policystrata-published-npm-runtime-"));
  try {
    const install = installPublishedNpmPackages(temp, [`policystrata@${version}`]);
    const fixtures = writeRuntimeFixtures(install);
    runNodeRuntimeSmoke(install, fixtures);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

function smokePublishedGateway() {
  const runtimeVersion = process.env.POLICYSTRATA_NPM_VERSION || readPackageJson(join(root, "packages/node")).version;
  const gatewayVersion =
    process.env.POLICYSTRATA_GATEWAY_VERSION || readPackageJson(join(root, "packages/gateway")).version;
  const temp = mkdtempSync(join(tmpdir(), "policystrata-published-gateway-"));
  try {
    const install = installPublishedNpmPackages(temp, [
      `policystrata@${runtimeVersion}`,
      `@policystrata/agent-trust-gateway@${gatewayVersion}`,
    ]);
    const fixtures = writeRuntimeFixtures(install);
    runNodeRuntimeSmoke(install, fixtures);
    runGatewaySmoke(install, fixtures);
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
}

function installPublishedNpmPackages(temp, packages) {
  return retry((attempt) => {
    const install = join(temp, `install-${attempt}`);
    const cache = join(temp, `npm-cache-${attempt}`);
    mkdirSync(install);
    writeFileSync(join(install, "package.json"), JSON.stringify({ private: true, type: "module" }), "utf8");
    for (const packageSpec of packages) {
      run("npm", ["view", packageSpec, "version", "--prefer-online", "--cache", cache], { cwd: install });
    }
    run("npm", ["install", "--ignore-scripts", "--prefer-online", "--cache", cache, ...packages], {
      cwd: install,
    });
    return install;
  });
}

function runNodeRuntimeSmoke(temp, fixtures) {
  const script = join(temp, "runtime-smoke.mjs");
  writeFileSync(
    script,
    `import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { evaluateRuntimeEvents, expectedRuntimeDecisionMismatches } from "policystrata/runtime";

const manifest = JSON.parse(readFileSync(${JSON.stringify(fixtures.manifest)}, "utf8"));
const events = JSON.parse(readFileSync(${JSON.stringify(fixtures.events)}, "utf8")).events;
const evaluations = evaluateRuntimeEvents(manifest, events);
assert.equal(evaluations.length, events.length);
assert.deepEqual(events.flatMap((event, index) => expectedRuntimeDecisionMismatches(event, evaluations[index])), []);
`,
    "utf8",
  );
  run("node", [script], { cwd: temp });
}

function runGatewaySmoke(temp, fixtures) {
  const script = join(temp, "gateway-smoke.mjs");
  writeFileSync(
    script,
    `import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { decideRuntimeEvent } from "@policystrata/agent-trust-gateway";

const manifest = JSON.parse(readFileSync(${JSON.stringify(fixtures.manifest)}, "utf8"));
const event = JSON.parse(readFileSync(${JSON.stringify(fixtures.allowedEvent)}, "utf8"));
const result = decideRuntimeEvent(manifest, event, "enforce");
assert.equal(result.ok, true);
assert.equal(result.events[0].expectedDecision?.action, "allow");
`,
    "utf8",
  );
  run("node", [script], { cwd: temp });
  const bin = join(temp, "node_modules/.bin/agent-trust-gateway");
  if (!existsSync(bin)) throw new Error("agent-trust-gateway binary was not installed");
  run(
    bin,
    [
      "decide",
      "--manifest",
      fixtures.manifest,
      "--event",
      fixtures.events,
      "--mode",
      "shadow",
      "--out",
      join(temp, "gateway-decisions.json"),
    ],
    {
      cwd: temp,
    },
  );
}

function writeRuntimeFixtures(directory) {
  const manifest = {
    schemaVersion: "policystrata.runtime_manifest.v1",
    version: "release-smoke.1",
    defaultDecision: "deny",
    resources: [
      {
        name: "support_tickets",
        type: "table",
        actions: [{ name: "read", allowedRoles: ["support_manager"] }],
      },
    ],
    controls: {
      authContext: { requiredFields: ["userId", "tenantId", "role", "purpose"] },
      sql: { tenantColumn: "tenant_id" },
    },
  };
  const allowedEvent = runtimeEvent({
    eventId: "evt_release_allow",
    payload: { sql: "select * from support_tickets where tenant_id = 'tenant_a'" },
    expectedDecision: { allowed: true, action: "allow" },
  });
  const deniedEvent = runtimeEvent({
    eventId: "evt_release_deny",
    payload: { sql: "select * from support_tickets" },
    expectedDecision: { allowed: false, action: "deny", reasonIncludes: ["missing tenant predicate"] },
  });
  const manifestPath = join(directory, "runtime-manifest.json");
  const eventsPath = join(directory, "runtime-events.json");
  const allowedEventPath = join(directory, "runtime-event-allow.json");
  const configPath = join(directory, "policystrata.yaml");
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");
  writeFileSync(eventsPath, `${JSON.stringify({ events: [allowedEvent, deniedEvent] }, null, 2)}\n`, "utf8");
  writeFileSync(allowedEventPath, `${JSON.stringify(allowedEvent, null, 2)}\n`, "utf8");
  writeFileSync(
    configPath,
    `version: 1
domain: support_saas
runtime_manifests:
  files:
    - runtime-manifest.json
runtime_events:
  files:
    - runtime-events.json
fuzz:
  enabled: false
`,
    "utf8",
  );
  return {
    manifest: manifestPath,
    events: eventsPath,
    allowedEvent: allowedEventPath,
    config: configPath,
  };
}

function runtimeEvent(overrides) {
  return {
    schemaVersion: "0.2.0",
    eventId: "evt_release",
    project: "support-bi",
    observedAt: "2026-07-06T15:58:52Z",
    agent: { key: "support-bi-copilot" },
    layer: "sql",
    operation: "read",
    summary: "Release smoke runtime event",
    actor: {
      userId: "user_1",
      tenantId: "tenant_a",
      role: "support_manager",
      purpose: "support",
    },
    resource: { kind: "table", name: "support_tickets" },
    dataClasses: [],
    ...overrides,
  };
}

function packPackage(directory) {
  for (const file of readdirSync(directory)) {
    if (file.endsWith(".tgz")) rmSync(join(directory, file), { force: true });
  }
  run("bun", ["pm", "pack"], { cwd: directory });
  const tarballs = readdirSync(directory)
    .filter((file) => file.endsWith(".tgz"))
    .map((file) => join(directory, file));
  if (tarballs.length !== 1) {
    throw new Error(`expected one package tarball in ${directory}, found ${tarballs.map(basename).join(", ")}`);
  }
  return tarballs[0];
}

function retry(operation) {
  const attempts = Number(process.env.POLICYSTRATA_RELEASE_SMOKE_RETRIES || "15");
  if (!Number.isInteger(attempts) || attempts < 1) {
    throw new Error("POLICYSTRATA_RELEASE_SMOKE_RETRIES must be a positive integer");
  }
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return operation(attempt);
    } catch (error) {
      if (attempt === attempts) throw error;
      const delaySeconds = Math.min(30, attempt * 5);
      process.stderr.write(`release smoke attempt ${attempt} failed; retrying in ${delaySeconds}s\n`);
      spawnSync("sleep", [String(delaySeconds)], { stdio: "inherit" });
    }
  }
  throw new Error("release smoke retry loop exited unexpectedly");
}

function run(command, args, options = {}) {
  process.stderr.write(`$ ${[command, ...args].join(" ")}\n`);
  const result = spawnSync(command, args, {
    cwd: options.cwd || root,
    env: { ...process.env, ...(options.env || {}) },
    stdio: "inherit",
  });
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} exited with ${result.status}`);
  }
}

function readPackageJson(directory) {
  return JSON.parse(readFileSync(join(directory, "package.json"), "utf8"));
}

function pyprojectVersion() {
  const match = readFileSync(join(root, "pyproject.toml"), "utf8").match(/^version = "([^"]+)"/m);
  if (!match) throw new Error("could not read pyproject version");
  return match[1];
}

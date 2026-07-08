# Clearance Runner Contract

PolicyStrata can emit a local Clearance runner contract for enterprise pilots where sensitive
inputs stay in the customer environment. The contract is metadata-only by default: it records hashes,
artifact references, summaries, decisions, and exit-code intent, not raw prompts, documents, rows,
tool payloads, credentials, or private schemas.

PolicyStrata OSS remains usable without Clearance. Clearance is optional hosted infrastructure for
review state, waivers, approvals, audit logs, procurement, billing, and trust-center reporting. The
OSS package produces evidence near sensitive systems; the hosted app should receive only the
metadata contract unless a deployment explicitly enables a stronger, reviewed artifact mode.

Every `policystrata run` writes:

- `.clearance/clearance-run.json`
- `.clearance/evidence-pack.json`

Both Clearance artifacts include the PolicyStrata package version. The run contract records runner
metadata, exit-code intent, upload mode, and the evidence-pack reference. The evidence pack includes
`storageMode: metadata_only`, run metadata, summary counts, release decision state, a stable `runId`,
artifact hashes, byte counts, and local artifact paths with `upload: false`. Witness files are
referenced as redacted local artifacts.

## Config

Create `clearance.runner.yaml` for pilot-specific metadata:

```yaml
schemaVersion: clearance.runner.v1
organizationId: org_demo
projectId: support-bi
environment: prod
releaseCandidate: commit-abc123
apiUrl: https://clearance.example
outputDir: .clearance
uploadMode: metadata_only
uploadArtifacts: false
offline: true
failMode: fail_closed
engines:
  - policystrata
gates:
  - id: tenant_scope
    mode: block
  - id: pii_minimization
    mode: block
```

Unknown config fields are ignored for forward compatibility. Identifiers are validated as safe
PolicyStrata identifiers. `outputDir` must be relative to the run directory and must not contain
`..`.

## Run Metadata

`policystrata run` can attach Clearance metadata while preserving the existing deterministic
benchmark behavior:

```bash
uv run policystrata run \
  --domain support_saas \
  --suite seeded \
  --out runs/support \
  --project-id support-bi \
  --organization-id org_demo \
  --environment prod \
  --release-candidate rc-2026-07-08 \
  --commit-sha abc123 \
  --clearance-output-dir .clearance \
  --offline
```

You can also provide the same metadata through `--clearance-config clearance.runner.yaml`. Explicit
CLI flags override values loaded from the config file.

`runId` is stable for the same package version, run metadata, summary, artifact hashes, project, and
release metadata. It intentionally excludes absolute filesystem paths.

## Commands

Validate config:

```bash
uv run policystrata clearance-runner validate --config clearance.runner.yaml
```

Regenerate and print/write a metadata-only evidence pack:

```bash
uv run policystrata clearance-runner evidence-pack \
  --run-dir runs/support \
  --config clearance.runner.yaml \
  --out runs/support/evidence-pack.json
```

Audit any JSON/YAML payload before upload:

```bash
uv run policystrata clearance-runner audit-payload --payload runtime-events.json
```

The audit fails when it sees sensitive field names or common secret/PII value patterns such as raw
prompts, raw documents, tool payloads, credentials, bearer tokens, JWTs, API keys, email addresses,
possible payment cards, or secrets embedded in URLs.

Upload metadata to a compatible runner endpoint:

```bash
CLEARANCE_RUNNER_TOKEN=runner_token \
uv run policystrata clearance-runner upload \
  --run-dir runs/support \
  --config clearance.runner.yaml \
  --payload runtime-events.json
```

The upload payload is an OSS-side contract, not a hosted-app internal API. By default it posts to
`/v1/runner/uploads`, sets an idempotency key, includes the local run and evidence-pack metadata,
strips runtime-event `payload`, strips fixture-only `expectedDecision`, validates the
metadata-only boundary, and enforces a 1 MB payload limit before opening a network connection.
Uploads require a runner token from `--token` or `CLEARANCE_RUNNER_TOKEN`. Missing tokens, upload
failures, and auth failures return exit code `4`.

Protected branches default fail-closed. If `uploadMode: local_only` is used on a configured
protected branch such as `main`, the upload command exits `4` unless the caller provides an explicit
audit note:

```bash
uv run policystrata clearance-runner upload \
  --run-dir runs/support \
  --config clearance.runner.yaml \
  --local-override-note "approved break-glass local evidence run"
```

The override note is recorded in `.clearance/clearance-run.json`, the evidence pack, and the upload
payload.

Generate JSON Schema for Clearance contracts:

```bash
uv run policystrata schema --kind clearance-runner-config --out schemas/clearance.runner.schema.json
uv run policystrata schema --kind clearance-run --out schemas/clearance-run.schema.json
uv run policystrata schema --kind clearance-evidence-pack --out schemas/clearance-evidence-pack.schema.json
uv run policystrata schema --kind clearance-upload --out schemas/clearance-upload.schema.json
```

The artifact manifest rejects absolute or escaping references by construction, rejects symlink
escapes, records SHA-256 and byte length for each local artifact, and keeps `upload: false` by
default. When present, evidence packs also reference:

- `policystrata/findings.json`
- `witnesses.redacted.json`
- `runtime-events.json`

## Redacted Artifact Mode

The default local artifact mode is redacted metadata. PolicyStrata may keep detailed local files
inside the run directory for debugging, but Clearance-facing artifacts should reference only
metadata-friendly files such as `witnesses.redacted.json`, `policystrata/findings.json`, and
`runtime-events.json`. Those files are still treated as local artifacts with `upload: false` unless
a deployment changes the artifact policy after review.

Use the metadata-boundary audit before moving any artifact across a trust boundary:

```bash
uv run policystrata clearance-runner audit-payload --payload runs/support/runtime-events.json
```

If the audit fails, remove raw fields or replace them with hashes, artifact refs, schema refs,
finding IDs, policy refs, redaction classes, and decision summaries. Do not bypass the audit for CI
or production uploads.

## Exit Codes

The runner contract records the Clearance pilot exit-code mapping:

- `0`: pass or review-only
- `1`: fail
- `2`: blocked
- `3`: invalid config, returned by `clearance-runner validate` for malformed runner configs
- `4`: upload/auth failure

The local benchmark runner still uses the existing PolicyStrata CLI behavior. The
`clearance-runner evidence-pack` command returns the contract exit code implied by the generated
evidence pack. When `--out` is used, it prints a concise CI summary with `out`, `exitCode`,
`state`, `blocked`, and `needsReview`.

## What Never Belongs In Uploaded Metadata

Do not upload these fields or values through the metadata-only contract:

- raw prompts or prompt transcripts
- raw documents, retrieved chunks, sampled rows, customer rows, or full traces
- tool, MCP, browser, code-execution, or connector request/response payloads
- source credentials, bearer tokens, JWTs, API keys, cookies, passwords, or secret-bearing URLs
- private database schemas or private input/output schemas
- fixture-only `expectedDecision` values

Use hashes, local artifact refs, witness refs, finding IDs, policy refs, summaries, redaction
classes, and decision envelopes instead.

## Compatibility Policy

JSON/YAML contracts are additive by default. Consumers should tolerate unknown fields on evidence
objects intended for forward compatibility. Breaking changes require a schema-version bump and
valid/invalid fixture updates under `tests/fixtures/schemas`.

## Troubleshooting

- `clearance-runner validate` exits `3`: the runner config is malformed. Check
  `schemaVersion`, safe identifier fields, and that `outputDir` is relative and does not contain
  `..`.
- `clearance-runner upload` exits `4`: the runner token is missing, the endpoint returned an error,
  the payload exceeded the configured size limit, the metadata-boundary audit failed, or a protected
  branch blocked local-only mode.
- Protected branch local-only failure: either upload metadata or provide
  `--local-override-note` with a real audit reason for the break-glass run.
- Boundary audit failure: inspect the reported JSON paths and remove raw prompts, documents, rows,
  tool payloads, credentials, private schemas, emails, possible card values, or secret-bearing refs.
- Missing artifact hash: ensure the artifact path is relative to the run directory and is not a
  symlink escaping that directory.
- Runtime event upload lacks details after stripping: keep sensitive payloads local and add
  `payloadHash`, schema refs, policy refs, resource names, data classes, or witness refs instead.

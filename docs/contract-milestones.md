# Contract Milestones

Use these labels when turning stable OSS contract work into issues or release milestones.

## `contract:metadata-boundary`

- Python and gateway metadata-boundary scanners.
- Runtime/gateway upload payload stripping.
- Redacted local artifact modes.
- Security posture tests for secrets and synthetic fixtures.

## `contract:clearance-runner`

- `clearance.runner.v1`
- `clearance.run.v1`
- `clearance.evidence_pack.v1`
- `clearance.upload.v1`
- exit code mapping, idempotency, protected-branch fail-closed behavior

## `contract:runtime`

- `policystrata.runtime_manifest.v1`
- runtime event `0.2.0`
- SQL, retrieval, egress, tool/MCP, RLS drift, kill-switch, and approval controls
- Node runtime event builders and customer-hosted gateway behavior

## `contract:schema-compatibility`

- public schema fixtures
- unknown-field tolerance for forward-compatible consumers
- version/schemaVersion `const` checks
- changelog and migration notes for breaking changes

## `contract:evidence-export`

- `policystrata-json` evidence export
- Inspect and BenchFlow adapters
- JUnit, SARIF, and generic Slack/Jira/Datadog examples
- deterministic Snowflake/text-to-SQL imported-trace fixture

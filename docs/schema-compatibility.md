# Schema Compatibility

PolicyStrata public JSON/YAML contracts are intended to be stable across patch releases.

## Public Contracts

Generate schemas with:

```bash
uv run policystrata schema --kind imported-trace
uv run policystrata schema --kind scan-result
uv run policystrata schema --kind runtime-event
uv run policystrata schema --kind clearance-runner-config
uv run policystrata schema --kind clearance-run
uv run policystrata schema --kind clearance-evidence-pack
uv run policystrata schema --kind clearance-upload
```

Every public schema kind has a valid and invalid fixture under `tests/fixtures/schemas`.

## Compatibility Rules

- Add fields compatibly. Prefer optional fields with defaults.
- Consumers of evidence and scan output should tolerate unknown fields where forward compatibility
  matters.
- Producer input configs may reject unknown fields when accepting them would hide mistakes.
- Breaking changes require a schema-version bump, fixture updates, changelog notes, and migration
  docs.
- Versioned public schemas pin their `version` or `schemaVersion` field with a JSON Schema `const`.
  Compatibility tests fail if a versioned contract loses that pin.
- Metadata-only contracts must remain safe to inspect without raw prompts, rows, documents, tool
  payloads, credentials, private schemas, or full traces.

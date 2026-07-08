# Changelog

## [Unreleased]

## [1.0.5] - 2026-07-08

- Add generic `policystrata-json` evidence export, runtime event builder helpers for common Node
  layers, and source-distribution coverage for schema compatibility fixtures.
- Add Clearance runner/upload contract scaffolding with metadata-only validation, size limits,
  idempotency keys, protected-branch fail-closed behavior, and mock upload tests.
- Include PolicyStrata package version metadata in both Clearance run artifacts and validate nested
  upload payload contracts against the public evidence-pack and run-contract schemas.
- Harden metadata-only boundary scanners and gateway/runtime uploads for raw prompts, documents,
  tool payloads, credentials, JWTs, API keys, emails, cards, and stripped fixture-only fields.
- Improve runtime and gateway coverage for SQL tenant predicates, query-risk classification,
  row-limit checks, RLS drift events, egress classes, and fail-open/fail-closed documentation.
- Add schema compatibility fixtures/tests, audit fixtures, generic integration/export docs, and the
  TODO completion audit that separates PolicyStrata OSS work from agent-assurance hosted work.
- Fix scanner JUnit XML attribute quoting for findings with quoted messages.
- Publish the gateway under the scoped npm name `@policystrata/agent-trust-gateway`.
- Publish the release tuple: PyPI `policystrata==1.0.5`, npm runtime `policystrata@0.1.3`, and
  gateway `@policystrata/agent-trust-gateway@0.1.1`.

## [1.0.4] - 2026-07-07

- Add public JSON Schema rendering for scanner, trace, scan-result, and runtime event contracts.
- Add optional runtime manifest and runtime event fixture readiness checks to `policystrata doctor`.
- Add the customer-hosted `policystrata-agent-trust-gateway` package surface, CI checks, and npm
  trusted-publishing workflow path.
- Publish the registry-proof release tuple: PyPI `policystrata==1.0.4`, npm runtime
  `policystrata@0.1.2`, and gateway `policystrata-agent-trust-gateway@0.1.0`.
- Add runtime fixture `expectedDecision` metadata, CLI assertion mode, doctor expectation checks,
  and clean-install artifact/registry smoke commands.
- Move local development tooling to Bun/mise, add dependency/security workflows, and ignore
  generated site/output artifacts.

## [1.0.3] - 2026-07-02

- Stage the next Node package as `policystrata@0.1.1` and make the npm trusted-publisher workflow
  publish with explicit provenance.
- Add top-level `authorizeTool()`/`authorize_tool()` helpers for Node and Python runtime parity,
  including decision metadata for `toolKind`, `decisionPoint`, `writeState`, `approvalState`,
  `userId`, and `householdId`.
- Validate runtime conformance fixtures against the packaged JSON Schema and compare built
  Node/Python runtime decisions when the Node package has been built locally.
- Clarify that runtime `mode: "shadow"` is rollout metadata and does not change the deterministic
  `allowed` decision.
- Add local integration-test, Infisical, and Socket configuration files intentionally.

## [1.0.2] - 2026-07-02

- Add the stable Node runtime authorization surface with generic
  `authorize({ subject, action, resource, context, mode })`, compatibility `authorizeTool()`, and
  result-release authorization helpers.
- Add a runtime manifest JSON Schema plus shared conformance fixtures for allow/deny, unknown
  action/resource, role aliases, write/export approvals, semantic constraints, release boundaries,
  and deny-by-default behavior.
- Add Python runtime parity for the shared conformance fixtures.
- Document the scanner/doctor versus runtime authorization boundary and record the JavaScript
  distribution decision for publishing the Node runtime through npm.
- Publish the initial npm package and configure npm trusted publishing for future Node runtime
  releases while keeping PyPI publishing on trusted publishing.

## [1.0.1] - 2026-06-29

- Harden the Node trace recorder redaction path against secret leakage and regex denial-of-service
  findings.
- Pin GitHub Actions to immutable commit SHAs and keep PyPI distribution checksum verification in
  the publish workflow.
- Avoid the Socket-flagged `pycparser` 3.0 artifact in the locked release tooling environment.

## [1.0.0] - 2026-06-27

- Promote the polished public paper-backed release line to `1.0.0`.
- Keep the paper PDF, release post, canonical artifact zip, website mirror, exact SHA256 checksums,
  and reproduction command in the public package metadata.
- Pin GitHub Action examples to `v1.0.0`.

## [0.1.6] - 2026-06-26

- Document the public paper PDF, release post, canonical artifact zip, website mirror, SHA256
  checksums, and reproduction command in the README and project metadata.

## [0.1.5] - 2026-06-26

- Render `policystrata doctor --format markdown` as Markdown even when no scanner config is
  supplied.
- Clarify that doctor audits only the selected config, and document
  `policystrata_real_db_clean.yaml` as the Postgres/dbt example config for DB/RLS readiness.
- Recommend both CI gates: `policystrata scan` for policy drift and
  `policystrata doctor --strict` for implementation readiness.
- Keep GitHub Action examples pinned to the current release tag.

## [0.1.4] - 2026-06-26

- Add `policystrata doctor --config` as a first-class stack audit mode for scanner wiring,
  coverage accounting, database schema/RLS/grant/view/index introspection, source-map accounting,
  prompt/tool manifest accounting, and remediation todos.
- Compare JSON/YAML prompt manifests against the canonical policy for stale exposed metrics or
  dimensions.
- Add deterministic privacy policy, terms of service, DPA, internal policy, security policy, and
  retention policy classification for configured policy documents.
- Extract policy-document obligation signals for personal-data minimization, purpose limits,
  notice/consent, data-subject rights, retention/deletion, third-party sharing, subprocessor
  controls, security controls, tenant isolation, and sensitive-data controls.
- Preserve the dependency-only `policystrata doctor` output for reproducibility checks.
- Make `doctor --strict` fail missing, partial, or invalid stack wiring.

## [0.1.3] - 2026-06-26

- Add a first-party TypeScript/Node trace recorder for agent tools, session metadata, Drizzle-style
  query capture, mutation traces, redaction defaults, and SaaS tenant-scope SQL checks.
- Allow imported trace JSONL files to mix Node SDK session/tool/mutation records with SQL traces.
- Accept SDK SQL records that provide SQL under `query.sql` while preserving read-only validation.
- Document the Node SDK workflow and mixed-record trace contract.

## [0.1.2] - 2026-06-26

- Package scanner examples in the wheel and add `policystrata init-scan postgres_dbt --out ...`.
- Expand `policystrata scan --help` with examples and accepted config sections.
- Fix `init-scan --source-domain finance_saas` so the generated config and trace use finance
  principals, metrics, and firm-scope predicates.
- Label scanner reports with configured readiness instead of a pass-like score.
- Keep the intentional scanner failure fixture off the PostgreSQL fixture path.
- Allow Docker/PostgreSQL fixture ports and database URLs to be overridden with environment
  variables for local release testing.
- Add `--strict`/`--fail-on-warning` to `check-integration`.

## [0.1.1] - 2026-06-25

- Add `policystrata init-scan` to scaffold `policystrata.yaml`, `domain/policy.yaml`,
  `domain/surfaces.yaml`, `traces.example.jsonl`, and a runnable scan command.
- Add scanner `tenancy` configuration for custom canonical predicates and tenant columns.
- Add production integration readiness scoring to scanner summaries and reports.
- Add remediation-oriented finding fields for what changed, owning layer, probable fix, minimal
  repro trace, and CI gate command.
- Document the imported-trace contract, framework trace-export recipes, and an AI data assistant
  scanning workflow.

## [0.1.0] - 2026-06-25

- Initial public research artifact.
- Deterministic `support_saas` and `finance_saas` benchmark domains.
- Seeded and generated mutation suites for cross-layer policy drift.
- Traces, summaries, baselines, evidence tables, minimized witnesses, scanner fixtures, and Docker
  PostgreSQL evidence support.
- Public release files, CI, GitHub Action wrapper, and source distribution manifest coverage.
- Eval-card governance, scanner regression-case labels, database state assertions, and
  Inspect/BenchFlow export adapters.
- Suite provenance, evidence-level, and detector-freeze metadata for future blinded or externally
  authored suites.
- `defense_in_depth_stack` baseline and scanner `evidence_exercised` reporting for clean scans.
- Artifact usability report command for reviewer-facing run, witness, latency, and fixture metrics.
- arXiv-ready paper source and same-day submission notes under `paper/arxiv`.

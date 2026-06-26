# Changelog

## [Unreleased]

- No changes yet.

## [0.1.4] - 2026-06-26

- Add `policystrata doctor --config` as a first-class stack audit mode for scanner wiring,
  coverage accounting, database schema/RLS/grant/view/index introspection, source-map accounting,
  prompt/tool manifest accounting, and remediation todos.
- Add deterministic privacy policy, terms of service, DPA, internal policy, security policy, and
  retention policy classification for configured policy documents.
- Extract policy-document obligation signals for personal-data minimization, purpose limits,
  notice/consent, data-subject rights, retention/deletion, third-party sharing, subprocessor
  controls, security controls, tenant isolation, and sensitive-data controls.
- Preserve the dependency-only `policystrata doctor` output for reproducibility checks.

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

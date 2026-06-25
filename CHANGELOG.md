# Changelog

## [Unreleased]

- No changes yet.

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

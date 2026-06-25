# Open Source And Commercial Strategy

PolicyStrata should be open source first. The paper needs reproducibility and trust in the core
mechanism: oracle separation, adapters, compiler checks, traces, witnesses, and benchmark evidence.

The commercial offering should help teams run that mechanism inside their own stacks.

## Strategic Position

PolicyStrata is not an LLM eval dashboard or a closed hosted scanner. The intended category is:

> Deterministic policy-drift regression testing for LLM data-agent stacks.

Open source provides reproducibility and inspectability. Paid enterprise work should focus on
workflow, integration, and support.

## What Stays Open Source

Keep these public:

- CLI and Python package.
- Built-in domains, fixtures, and DataPolicyDriftBench suites.
- Seeded and generated mutation operators.
- Policy oracle, surface contracts, and witness classes.
- JSONL traces, summaries, baselines, and witness minimization.
- Reproducibility scripts and evidence snapshots.
- Dockerized PostgreSQL RLS fixtures.
- Public adapters that support paper claims.
- Methodology docs, including limitations and non-claims.

Researchers should be able to reproduce the paper without a vendor account, LLM API key, hosted
service, or private control plane.

## Commercial Boundary

Commercial work should focus on the parts that become expensive in real organizations:

- Private CI integration.
- Self-hosted runners for private schemas, policies, and sample data.
- Enterprise connectors for warehouses, semantic layers, BI tools, and governance systems.
- Dashboards, history, triage, and audit exports.
- Managed regression campaigns for policy, schema, and semantic-model changes.
- Custom adapters.
- Team workflows, approvals, suppressions, and release gates.
- Support, onboarding, and training.

## Preferred Product Sequence

Initial sequence:

1. Publish the open-source CLI and PyPI package with deterministic demos, benchmark reproduction,
   scanner gates, traces, witnesses, and paper instructions.
2. Ship the first-party GitHub Action as the default CI/release-gate wrapper around
   `policystrata scan`.
3. Run design-partner pilots against real governed data-agent stacks.
4. Package a self-hosted enterprise edition with runners, connectors, dashboards, and audit exports.
5. Add a hosted control plane only for metadata and collaboration state when customers accept it.

A hosted-only SaaS should not be the first product shape. The inputs are sensitive: schemas,
policies, tenant models, warehouse access patterns, traces, and sometimes representative rows.

## Distribution Order

- CLI and PyPI package first: this is the stable public artifact and the easiest path for local,
  CI, and research reproduction.
- GitHub Action second: release gates should wrap `policystrata scan` directly rather than asking
  teams to invent CI glue.
- SDK later: expose a deliberate `policystrata.sdk` module only when there is a stable
  application-facing API contract.
- MCP server later or optional: useful for agent workflows, but it should wrap the CLI or SDK and
  should not become the primary execution path.
- GitHub CLI extension only on demand: local users already have the normal `policystrata` CLI, and
  CI users need the GitHub Action.

## Packaging Rules

- Keep core checks, benchmark reproduction, traces, and witness minimization public.
- Do not require an LLM API key, hosted account, or private service for deterministic artifact runs.
- Do not claim production scanner effectiveness from public benchmark results alone.
- Do not price by killed mutant or generated witness.
- Price around environments, connectors, history, workflows, support, and managed services.
- Keep JSON and YAML trace formats stable. Add fields compatibly.

## License Posture

The current MIT license fits the paper phase: low friction, easy reproduction, and clear permission
to inspect and extend the artifact. If stronger reciprocity matters later, revisit licensing before
broad adoption.

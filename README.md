# PolicyStrata

PolicyStrata is a deterministic regression-testing framework for cross-layer policy drift in LLM
data-agent stacks.

It generates principals, requests, semantic plans, database states, lowered queries, and release
decisions; compares each layer against a canonical reference policy; and minimizes failures into
small reproducible witnesses.

Use it when you are building text-to-SQL agents, BI copilots, internal analytics agents, warehouse
chat systems, or governed enterprise LLM tools and need to know whether prompts, manifests,
semantic plans, validators, SQL compilers, database controls, and output filters still agree about
policy.

PolicyStrata is not an authorization boundary, and it is not another generic text-to-SQL benchmark.
It is a reproducible research artifact and regression gate for finding reachable disagreements
between layers.

## Paper And Artifact

- Paper PDF: <https://raintree.technology/papers/PolicyStrata.pdf>
- Release note: <https://raintree.technology/blog/policystrata-release>
- GitHub release: <https://github.com/raintree-technology/policystrata/releases/tag/policystrata-paper-2026-06-26>
- Artifact zip: <https://github.com/raintree-technology/policystrata/releases/download/policystrata-paper-2026-06-26/policystrata-submission-kit-2026-06-26.zip>
- Website mirror: <https://raintree.technology/artifacts/policystrata/policystrata-submission-kit-2026-06-26.zip>

SHA256:

```text
9a4da81d78c37fd81e9ab6b36f094756e61e6b88cfcd74dcab51cfdd8e5bbcd9  PolicyStrata.pdf
961778c1e8affc04f76e27ce7958572d904e69d7701494e0047e4f7bffbc466d  policystrata-submission-kit-2026-06-26.zip
```

Reproduce the paper-facing artifact run:

```bash
POLICYSTRATA_RUN_ROOT=/tmp/policystrata-final ./scripts/reproduce-final.sh
```

The paper reports deterministic artifact-suite coverage: 1720/1720 non-clean injected cases and
0 false positives on 80 clean controls. This is not a production-recall claim and not an
authorization boundary.

## Quick Start

From PyPI:

```bash
uvx policystrata demo
pipx run policystrata demo
```

From a source checkout:

```bash
uv sync --extra dev
uv run policystrata demo
```

The demo runs the built-in `support_saas` fixture, writes traces and minimized witnesses to
`runs/demo`, and prints the drift classes it found. Use `--out` to choose another output directory:

```bash
uv run policystrata demo --out runs/demo
```

No LLM API key is required for deterministic tests, benchmark runs, or the built-in demo.

## Install

PolicyStrata is a CLI-first Python package. The public package provides the `policystrata` console
script and importable Python modules.

```bash
python -m pip install policystrata
policystrata demo
```

For one-off CLI use without managing an environment:

```bash
uvx policystrata demo
pipx run policystrata demo
```

Repository examples under `examples/`, Docker Compose fixtures, and evidence scripts are available
from a GitHub checkout or source distribution. The wheel installs the runtime package, built-in
domain fixtures, and packaged scanner examples reachable through `policystrata init-scan`.

## Use As A Template

Click **Use this template** on GitHub, then start with the deterministic fixtures:

```bash
uv sync --extra dev
uv run policystrata run --domain support_saas --suite seeded --out runs/example
uv run policystrata summarize runs/example
```

To copy a built-in domain fixture into your tree:

```bash
uv run policystrata init-domain support_saas --out examples/my-policystrata-domain
```

Keep custom integrations as adapters. The policy oracle should stay independent from SQL compiler
behavior, external eval frameworks, and model-provider behavior.

## What It Tests

The core failure class is cross-layer policy drift:

```text
Canonical policy:
  Analysts may view tenant-scoped aggregate ticket counts, but not customer-level PII.

Model-visible manifest or grammar:
  Accidentally exposes customer_email as a dimension.

SQL compiler:
  Accidentally drops the tenant predicate while lowering an authorized aggregate.

Output layer:
  Releases the result because the final answer looks like a summary.

PolicyStrata result:
  A minimized witness localizes the violated layer and failed obligation.
```

PolicyStrata does not assume every layer should behave identically. Each surface has a declared
responsibility:

- `manifest`: expose model-visible capabilities without stale or forbidden options.
- `grammar`: parse the declared intent space and preserve untrusted intent for validation.
- `validator`: authorize semantic queries and bind principal, tenant, time, and budget obligations.
- `compiler`: lower authorized semantic IR into SQL while preserving metric, tenant, time, and row
  obligations.
- `database`: contain row access with RLS and other database-side controls.
- `release`: withhold contained or unauthorized results.

See [docs/failure-taxonomy.md](docs/failure-taxonomy.md) for how witness classes map to concrete
policy-drift failures.

## Run Benchmarks

PolicyStrata ships with deterministic `support_saas`, `finance_saas`, and
`analytics_clickhouse` benchmarks, generated mutation suites, held-out suite support, clean
controls, minimized witnesses, JSONL traces, baseline comparisons, and evidence tables.

```bash
uv run policystrata run --domain support_saas --suite seeded --out runs/example
uv run policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out runs/generated
uv run policystrata run --domain finance_saas --suite seeded --out runs/finance
uv run policystrata freeze-benchmark --domain support_saas --suite heldout_v1 --count 500 --seed 260626 --out runs/freeze/support-heldout-v1.json
uv run policystrata run --domain support_saas --suite heldout_v1 --count 500 --seed 260626 --freeze-manifest runs/freeze/support-heldout-v1.json --out runs/support-heldout-v1
uv run policystrata baselines runs/example runs/support-heldout-v1
uv run policystrata ablations runs/example runs/support-heldout-v1
```

The default `run` command writes:

```text
runs/<id>/traces.jsonl
runs/<id>/summary.json
runs/<id>/metadata.json
runs/<id>/benchmark_manifest.json  # for frozen runs
runs/<id>/witnesses/*.json
```

`metadata.json` records the mutation operator set, suite provenance, evidence level, and
detector-freeze status. Frozen runs verify the manifest before writing traces. Static suite YAML can
declare `suite_metadata` so externally authored, detector-frozen, or incident-reconstruction cases
stay separate from public/generated benchmark scores.

Regenerate paper-style evidence tables with:

```bash
scripts/reproduce-evidence.sh
scripts/reproduce-final.sh
```

Generate reviewer-facing artifact metrics for a run:

```bash
uv run policystrata artifact-report runs/repro/seeded
```

Current benchmark details are in [docs/evidence.md](docs/evidence.md), with methodology and claim
boundaries in [docs/methodology.md](docs/methodology.md) and [EVAL_CARD.md](EVAL_CARD.md).

## Run The Scanner

`policystrata scan` is the production-oriented path. It treats PolicyStrata as a scanner and
release gate, not as the authorization boundary.

Create a scanner scaffold for an application:

```bash
uv run policystrata init-scan --out policystrata
uv run policystrata scan --config policystrata/policystrata.yaml --out runs/policystrata-smoke
```

The scaffold writes `policystrata.yaml`, `domain/policy.yaml`, `domain/surfaces.yaml`, and
`traces.example.jsonl`. Replace the example trace with exported SQL/tool-call traces from your app.
Use `--source-domain finance_saas` to scaffold the finance policy and a matching finance trace
instead of the default support SaaS example.

Copy a packaged Postgres/dbt scanner example from an installed wheel:

```bash
uvx policystrata init-scan postgres_dbt --out policystrata-example
uvx policystrata scan --config policystrata-example/policystrata_clean.yaml --out runs/scan-clean
```

`policystrata doctor` audits only the config you pass. In the copied `postgres_dbt` example,
`policystrata_clean.yaml` is a minimal clean smoke config, so doctor reports database and dbt
wiring as missing. Use `policystrata_real_db_clean.yaml` for the DB/RLS readiness audit, and
combine the dbt and database sections in your own app config when one strict readiness gate should
cover both.

Clean smoke test:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata_clean.yaml --out runs/scan-clean
```

Intentional gate-failure fixture:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata.yaml --out runs/scan
```

That fixture should exit `1` because it contains imported traces with known authorization,
unsafe-release, and tenant-scope findings.

Scanner outputs include:

```text
runs/scan-clean/scan.json
runs/scan-clean/findings.jsonl
runs/scan-clean/summary.json
runs/scan-clean/report.md
runs/scan-clean/witnesses/*.json
runs/scan-clean/scan.sarif  # when sarif: true
```

For a scanner run that also executes imported SQL beside canonical compiler SQL against the
Docker/PostgreSQL fixture:

```bash
docker compose up -d postgres
uv run policystrata scan --config examples/postgres_dbt/policystrata_real_db_clean.yaml --out runs/scan-real-db-clean
```

Postgres access goes through Python/`psycopg`; host `psql` is not required. See
[docs/scanner.md](docs/scanner.md) for scanner configuration, gate behavior, tenancy config,
remediation fields, state assertions, and real-database fixture details. See
[docs/trace-contract.md](docs/trace-contract.md), [docs/trace-adapters.md](docs/trace-adapters.md),
and [docs/testing-ai-data-assistant.md](docs/testing-ai-data-assistant.md) for imported-trace
contracts and framework recipes.

## Audit Stack Wiring

`policystrata doctor` without a config still checks local reproducibility dependencies. With a
scanner config, it audits what a deployment has wired and what is missing:

```bash
uv run policystrata doctor --format markdown
uv run policystrata doctor --config examples/postgres_dbt/policystrata_real_db_clean.yaml \
  --format markdown --out runs/doctor.md
```

The audit inventories policy/domain YAML, surface contracts, SQL traces, dbt semantic models,
PostgreSQL schema/RLS/grant/view/index metadata, privacy policies, terms of service, DPA/security/
retention/internal-policy documents, prompt/tool manifests, source maps, release coverage, and CI
gates. It classifies policy-document obligation signals, compares JSON/YAML prompt manifests
against the canonical policy for stale exposed metrics or dimensions, and emits remediation todos
with owners, files, expected tests, and gate commands. Use `--strict` when missing, partial, or
invalid wiring should fail CI.

## GitHub Action

Use the first-party action to run `policystrata scan` as a pull-request or release policy-drift
gate. The example pins the current release tag:

```yaml
name: PolicyStrata

on:
  pull_request:
  push:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: raintree-technology/policystrata@v1.0.0
        with:
          config: policystrata.yaml
          out: runs/policystrata

      - name: Implementation readiness gate
        if: always()
        run: policystrata doctor --config policystrata.yaml --strict
```

In CI, keep both gates: `policystrata scan` catches high-confidence policy drift, while
`policystrata doctor --strict` catches missing, partial, or invalid stack wiring before release.

See [docs/github-action.md](docs/github-action.md) for inputs, artifact upload, and database
fixture guidance.

## Integrations And Exports

PolicyStrata keeps core execution independent from external eval frameworks. Adapter exports are
available for downstream systems:

```bash
uv run policystrata export runs/example --format inspect --out runs/example/inspect.jsonl
uv run policystrata export runs/example --format benchflow --out runs/example/benchflow.json
```

The repo also includes a small dbt Semantic Layer adapter and fixture:

```bash
uv run policystrata check-integration dbt-semantic \
  --domain finance_saas \
  --path examples/integrations/dbt_semantic/finance_saas/semantic_models.yml
```

See [docs/trace-interop.md](docs/trace-interop.md) for adapter field mappings.

## TypeScript / Node SDK

The repository includes a first-party TypeScript recorder under `packages/node` for Next.js,
Drizzle, and other Node agent stacks:

```ts
import { createPolicyStrataRecorder } from "policystrata/node";

const recorder = createPolicyStrataRecorder({
  service: "demo-data-agent",
  out: ".policystrata/traces.jsonl",
  tenancy: {
    tenantColumns: ["transactions.household_id", "accounts.household_id"],
  },
});
```

`wrapTool()` records sanitized tool executions, `captureQuery()` captures Drizzle `.toSQL()` output
when available, and read-tool SQL records can be scanned with `policystrata scan`.
By default, the recorder HMACs ID fields with a per-recorder key, omits prompt text and raw error
messages, redacts SQL literal values, and records sanitized argument shape rather than argument values.
Default-redacted Node traces omit scanner `tenant_ids`; trusted fixture traces can set
`redaction.hashIds: false` when real database comparison needs raw tenant IDs.
Structured trace payloads such as semantic filters and expected-policy notes are redacted
recursively by default; `semantic_ir.filters.tenant_id` is HMACed unless trusted fixtures set
`redaction.hashIds: false`.

## Reference Docs

- [docs/benchmark-reference.md](docs/benchmark-reference.md): domains, generated mutants,
  baselines, and witness shape.
- [docs/scanner.md](docs/scanner.md): scanner inputs, gates, state assertions, and PostgreSQL
  fixture use.
- [docs/github-action.md](docs/github-action.md): CI wrapper for `policystrata scan`.
- [docs/distribution-roadmap.md](docs/distribution-roadmap.md): CLI, GitHub Action, SDK, MCP, and
  GitHub CLI extension sequence.
- [docs/evidence.md](docs/evidence.md): current evidence snapshot and reproduction commands.
- [docs/methodology.md](docs/methodology.md): claims, limitations, mutant definitions, and witness
  minimization.
- [EVAL_CARD.md](EVAL_CARD.md): benchmark provenance, evidence levels, and eval boundaries.
- [docs/open-source-commercial-strategy.md](docs/open-source-commercial-strategy.md): packaging and
  product boundary.

## Development

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

The built-in `support_saas` domain is deterministic and seed-driven. Preserve JSON/YAML trace
stability when extending artifacts; add fields compatibly.

## Status

PolicyStrata is an early research artifact. It is useful for reproducing the paper's core failure
model and for building regression gates around real stacks. It does not prove recall on unknown
production incidents, and it should not be represented as a production security scanner by itself.

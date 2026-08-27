# PolicyStrata Artifact Reviewer Guide

This kit supports review of the PolicyStrata paper and deterministic artifact.

PolicyStrata tests cross-layer policy drift in governed LLM data-agent stacks. It is not an
authorization boundary, a generic LLM benchmark, or a claim of recall on unknown production faults.
The headline result is deterministic artifact-suite coverage over frozen manifests, held-out
generated suites, clean controls, and two built-in application domains plus a ClickHouse-style
analytics domain. It is not production recall and not an authorization boundary.

## What To Review First

1. Read `paper-public.pdf` or, for double-blind review, `paper-anon.pdf`, which removes author
   identity and generalizes brownfield integration details.
2. Read `INSTALL.md`, `REQUIREMENTS.md`, and `STATUS.md`.
3. Run the 30-minute smoke test in `INSTALL.md`.
4. Run `./reproduce-final.sh` from this directory.
5. Compare generated outputs with `expected-results.md`.
6. Run the `policystrata doctor --config` smoke test below to inspect stack wiring.
7. Optional for the single-blind tool demo: run the BetterOff brownfield integration smoke test.
8. Inspect the generated evidence table at `../policystrata/runs/final/evidence.md`.
9. Optional: run the Docker/PostgreSQL and Docker/ClickHouse fixtures described below.

## Artifact Layout

```text
conference-kit/
  README.md
  paper-anon.pdf
  paper-public.pdf
  artifact-reviewer-guide.md
  INSTALL.md
  REQUIREMENTS.md
  STATUS.md
  LICENSE
  reproduce.sh
  reproduce-final.sh
  expected-results.md
  independent-runs.md
  docker-compose.yml
  issta-splash-tool-demo-paper.tex
  venue-submission-playbook.md
  today-submission-checklist.md
  venue-proposal-variants.md
  talk-proposal-150w.md
  talk-outline.md
  figures/
../policystrata/
  canonical Python artifact
../betteroff/
  optional brownfield application integration for the single-blind tool demo
```

The script assumes this repository sits beside the canonical artifact checkout:

```text
workspace/
  papers/
  policystrata/
```

Override the artifact path with `POLICYSTRATA_ARTIFACT_ROOT=/path/to/policystrata`.

## Requirements

- Python environment managed by `uv`.
- No LLM API key.
- No host `psql`.
- Docker only for optional PostgreSQL/RLS and ClickHouse smoke tests.

## PDF Checksums

```text
9a4da81d78c37fd81e9ab6b36f094756e61e6b88cfcd74dcab51cfdd8e5bbcd9  paper-public.pdf
7f7c1d3a09b2e7dcdc6a4613918255a2409fef43d9fdf1a1e016bedc7a1d332b  paper-anon.pdf
be10314241712fedcaecb7c4a867ba2b5882f9e29c088abfd1504172ea855b15  issta-splash-tool-demo-paper.pdf
33fa96dc7640c738cceb63615418c8d2a21145d7b46aaeda7906655bb0792c5a  policystrata-demo-video.mp4
```

## 30-Minute Smoke Test

This path verifies the CLI and seeded deterministic suite without running the full generated suite:

```bash
cd ../policystrata
rm -rf runs/conference-kit-smoke
uv run policystrata run --domain support_saas --suite seeded --out runs/conference-kit-smoke/seeded
uv run policystrata evidence seeded=runs/conference-kit-smoke/seeded --out runs/conference-kit-smoke/evidence.md
grep -q "| seeded | 50 | 50 | 0 |" runs/conference-kit-smoke/evidence.md
```

The full deterministic suite is intended to complete in minutes on a developer laptop. On the local
checked machine with an already prepared `uv` environment, it completed well under one minute.

## Stack Audit Smoke Test

The scanner/doctor path is separate from the benchmark score. It checks whether a deployment has
the expected policy, trace, database, document, prompt-manifest, source-map, release, and CI-gate
inputs wired.

```bash
cd ../policystrata
uv run policystrata doctor --config examples/postgres_dbt/policystrata_real_db_clean.yaml \
  --format markdown --out runs/conference-kit-doctor.md
sed -n '1,120p' runs/conference-kit-doctor.md
```

The report should include stack rows for policy/domain YAML, surface contracts, SQL traces,
PostgreSQL fixture, RLS checks, release-layer tests, policy and terms document ingestion, prompt/tool
manifest checks, source mapping, export coverage, and CI gating. Policy documents are classified
deterministically; prompt manifests are compared against the canonical policy for stale exposed
metrics or dimensions. This is coverage accounting and remediation guidance, not legal review or a
production authorization guarantee.

## Optional BetterOff Brownfield Integration Smoke Test

This path is for the single-blind SPLASH/ISSTA tool demonstration and practitioner materials. Omit
or sanitize it for double-blind archival packages because it contains product and organization
identity. It exercises real application surfaces with synthetic fixture data, not production
customer rows.

```bash
cd ../betteroff
bun run policystrata:check-generated
bun run policystrata:doctor
bun run policystrata:scan
```

Expected current result:

```text
doctor: all stack items wired, including policy and terms documents, prompt manifest, source map,
        semantic model, SQL/tool traces, database/RLS checks, release coverage, and CI gate
scan: gate pass, 0 findings, ci-gate-ready, 7 imported-trace checks, 4 real database checks
```

This is downstream application-wiring smoke evidence. It is not production customer-data evidence
and is not part of the 1720/1720 deterministic benchmark score.

## Core Reproduction

From `conference-kit/`:

```bash
./reproduce-final.sh
```

The script runs:

```bash
uv run policystrata freeze-benchmark --domain support_saas --suite heldout_v1 ...
uv run policystrata run --domain support_saas --suite heldout_v1 --freeze-manifest ...
uv run policystrata run --domain finance_saas --suite heldout_v1 --freeze-manifest ...
uv run policystrata run --domain analytics_clickhouse --suite generated --freeze-manifest ...
uv run policystrata run --domain support_saas --suite clean_controls --freeze-manifest ...
uv run policystrata baselines runs/final/support-seeded runs/final/support-generated ... --out runs/final/baselines.json
uv run policystrata ablations runs/final/support-seeded runs/final/support-generated ... --out runs/final/ablations.json
uv run policystrata evidence ... --out runs/final/evidence.md
uv run policystrata artifact-report runs/final/support-heldout-v1 --out runs/final/artifact-report.md
```

Expected runtime depends on local hardware, but the deterministic path is intended to complete in
minutes on a developer laptop.

`./reproduce.sh` remains as a short compatibility path for the older 620-case deterministic suite.

## Optional PostgreSQL/RLS Smoke Test

The Docker fixture is outside the deterministic benchmark score. It checks database
containment through a non-superuser application path.

```bash
cd ../policystrata
docker compose -f ../papers/conference-kit/docker-compose.yml up -d postgres
POLICYSTRATA_RUN_DB_TESTS=1 uv run --extra dev pytest tests/test_postgres_integration.py
docker compose -f ../papers/conference-kit/docker-compose.yml down
```

This optional test should not be reported as part of the 1720/1720 deterministic score.

## Optional ClickHouse Smoke Test

The ClickHouse benchmark domain is deterministic and does not require a live ClickHouse server.
This optional smoke test checks service reachability for reviewers who want to exercise the Docker
path.

```bash
cd ../policystrata
docker compose -f ../papers/conference-kit/docker-compose.yml up -d clickhouse
POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 uv run --extra dev pytest tests/test_clickhouse_integration.py
docker compose -f ../papers/conference-kit/docker-compose.yml down
```

## Success Criteria

The artifact review is successful if:

- all final deterministic suites run;
- `evidence.md` reports frozen generated/held-out suites separately from seeded and clean-control suites;
- clean controls report 0 false positives;
- baseline comparators reproduce the expected catch rates in `expected-results.md`;
- each run writes `traces.jsonl`, `summary.json`, `metadata.json`, and witness records;
- frozen runs write `benchmark_manifest.json`;
- the clean scanner fixture exits successfully;
- the doctor report explains missing or partial wiring with remediation todos;
- no LLM API key or host `psql` is required.

## Common Failure Modes

- `uv` missing: install `uv` or use the environment manager required by the venue.
- Docker unavailable: skip the optional PostgreSQL/RLS smoke test; the deterministic artifact does
  not require Docker.
- Existing run directory: set `POLICYSTRATA_RUN_ROOT` to a fresh path or remove `runs/final`.
- Different artifact path: set `POLICYSTRATA_ARTIFACT_ROOT`.

## Claim Boundary

Do report:

- deterministic coverage over implemented non-equivalent mutation operators and fixtures;
- detector-frozen generated and held-out suite results;
- clean-control false-positive accounting;
- responsibility-scoped witnesses and first-transition labels;
- baseline comparison over the same traces;
- stack-audit coverage for privacy and terms documents, prompt manifests, source maps, release tests, and
  CI gates;
- downstream BetterOff integration smoke evidence over real application surfaces with synthetic
  fixture data for single-blind or public demos, clearly separated from deterministic benchmark
  results;
- no LLM API key required for deterministic evidence.

Do not report:

- recall on unknown production incidents;
- a production authorization guarantee;
- an externally authored held-out suite unless one has been added after this kit was prepared;
- model-mediated exploitability as part of the deterministic score.

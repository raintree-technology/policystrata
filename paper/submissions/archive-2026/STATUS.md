# Artifact Status

## Claimed Badges

Target badges depend on venue:

- Artifacts Available: intended after a persistent public archive is created.
- Artifacts Functional or Reusable: intended after reviewer confirmation.
- Results Reproduced or Replicated: not claimed by this kit alone. Those badges generally require
  independent reproduction or replication evidence according to venue rules.

## Supported Claims

- Deterministic artifact-suite coverage for implemented non-equivalent mutation operators and
  fixtures.
- Detector-frozen generated and held-out suite evidence.
- Stable trace generation for the included seeded, generated, held-out, and clean-control suites.
- Domain-transfer evidence over support, finance, and ClickHouse-style analytics fixtures.
- Baseline comparator outputs over the same traces.
- Optional PostgreSQL/RLS and ClickHouse smoke tests.
- Optional BetterOff brownfield application-wiring evidence for single-blind or public demos.

## Unsupported Claims

- Production recall on unknown incidents.
- Production authorization guarantee.
- Security exploitability across arbitrary deployed systems.
- Externally authored benchmark coverage.

## Current Evidence

Last checked local evidence:

```text
support_seeded: 50 mutants, 50 killed, 0 survived
support_generated: 500 mutants, 500 killed, 0 survived, frozen
support_heldout_v1: 500 mutants, 500 killed, 0 survived, frozen
finance_seeded: 20 mutants, 20 killed, 0 survived
finance_heldout_v1: 250 mutants, 250 killed, 0 survived, frozen
analytics_clickhouse_seeded: 100 mutants, 100 killed, 0 survived
analytics_clickhouse_generated: 300 mutants, 300 killed, 0 survived, frozen
clean_controls: 80 controls, 0 false positives, frozen
total non-clean: 1720 mutants, 1720 killed, 0 survived
```

Runtime and output size from the latest local run with a prepared `uv` environment:

```text
scripts/reproduce-final.sh: 3.99s wall-clock
traces: 1800 total, including 1720 non-clean cases and 80 clean controls
witnesses: 1720 JSON witnesses, median 3302 bytes, range 3080-3602 bytes
run directory: 1760 files, 17 MB
```

Scanner smoke test:

```text
findings: 0
```

BetterOff brownfield integration smoke test:

```text
doctor: all stack items wired, including policy and terms documents, prompt manifest, source map,
        semantic model, SQL/tool traces, database/RLS checks, release coverage, and CI gate
scan: gate pass, 0 findings, ci-gate-ready, 7 imported-trace checks, 4 real database checks
```

This integration uses real application surfaces with synthetic fixture data. It is not production
customer-data evidence and is not part of the 1720-case benchmark score.

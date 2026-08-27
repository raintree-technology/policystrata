# PolicyStrata Conference Kit

This directory contains submission assets for PolicyStrata.

Use this kit for two separate products:

- Archival paper and artifact review.
- Practitioner talk, poster, or tool demo.

## Contents

- `paper-anon.pdf`: anonymous paper for double-blind venues, with author identity removed and
  the brownfield integration details generalized.
- `paper-public.pdf`: public paper.
- `artifact-reviewer-guide.md`: reviewer-facing reproduction guide.
- `reproduce-final.sh`: final deterministic reproduction script with freeze manifests.
- `reproduce.sh`: short compatibility reproduction script for the earlier 620-case suite.
- `expected-results.md`: expected suite and baseline outputs.
- `docker-compose.yml`: optional PostgreSQL/RLS smoke-test fixture.
- `issta-splash-tool-demo-paper.tex`: ACM tool-demo paper source including the scanner/doctor path.
- `venue-submission-playbook.md`: venue-specific rules, fit, and adaptation notes.
- `today-submission-checklist.md`: action list for 2026-06-26.
- `venue-proposal-variants.md`: archival and practitioner abstract variants.
- `talk-proposal-150w.md`: short practitioner proposal.
- `talk-outline.md`: practitioner talk outline.
- `figures/`: figure notes and draft diagrams.

## Quick Reproduction

```bash
./reproduce-final.sh
```

The deterministic run is expected to report:

```text
support_seeded: 50/50
support_generated: 500/500 frozen
support_heldout_v1: 500/500 frozen
finance_seeded: 20/20
finance_heldout_v1: 250/250 frozen
analytics_clickhouse_seeded: 100/100
analytics_clickhouse_generated: 300/300 frozen
clean_controls: 80 controls, 0 false positives
non_clean_total: 1720/1720
```

No LLM API key is required. Host `psql` is not required.

## Stack Audit Smoke Test

From the PolicyStrata repository:

```bash
uv run policystrata doctor --config examples/postgres_dbt/policystrata_real_db_clean.yaml \
  --format markdown --out runs/doctor.md
```

The doctor report inventories scanner wiring, database schema/RLS metadata, policy-document inputs
such as privacy policies and terms of service, prompt/tool manifest exposure, source maps, release
coverage, and remediation todos.

## Optional BetterOff Integration Smoke Test

For the single-blind tool demo and practitioner story, the sibling BetterOff repository contains a
downstream finance-assistant integration over real application surfaces with synthetic fixture data:

```bash
cd ../betteroff
bun run policystrata:check-generated
bun run policystrata:doctor
bun run policystrata:scan
```

Current expected result: CI gate pass, 0 findings, `ci-gate-ready`, 7 imported-trace checks, and 4
real database checks. This is downstream application-wiring evidence, not production customer-data
evidence and not part of the 1720-case benchmark score.

## PDF Checksums

```text
9a4da81d78c37fd81e9ab6b36f094756e61e6b88cfcd74dcab51cfdd8e5bbcd9  paper-public.pdf
7f7c1d3a09b2e7dcdc6a4613918255a2409fef43d9fdf1a1e016bedc7a1d332b  paper-anon.pdf
be10314241712fedcaecb7c4a867ba2b5882f9e29c088abfd1504172ea855b15  issta-splash-tool-demo-paper.pdf
33fa96dc7640c738cceb63615418c8d2a21145d7b46aaeda7906655bb0792c5a  policystrata-demo-video.mp4
```

## Submission Rule

Prepare multiple venue-specific versions if useful, but submit the archival paper to only one
peer-reviewed archival venue at a time unless the target venue explicitly permits concurrent
submission.

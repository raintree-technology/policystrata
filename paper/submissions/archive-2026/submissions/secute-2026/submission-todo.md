# SECUTE 2026 Submission Todo

Deadline: 2026-07-17 AoE

## Paper

1. [x] Rewrite as an anonymous ACM tool/data paper.
   - Source: `conference-kit/submissions/secute-2026/secute-tool-data-paper.tex`
   - PDF: `conference-kit/submissions/secute-2026/secute-tool-data-paper.pdf`
   - PDF SHA256: `0bed53ac4c697fccd79612e0e03d9a966f0368a605ff4a20df2a69c13ac0d805`
   - Page count: 3 pages, including references and Data Availability Statement.
2. [x] Use `\documentclass[sigconf,review,anonymous]{acmart}`.
3. [x] Keep references inside the 5-page limit.
4. [x] Add a threat model:
   - stale model-visible capability exposure;
   - stale tenant or purpose constraints during lowering;
   - unauthorized SQL reachability;
   - database containment failures;
   - release of disallowed result-lineage pairs.
5. [x] Include the security-testing workflow in prose:
   policy specs -> surfaces -> generated/imported traces -> oracle -> minimized witness -> remediation.
6. [x] Include Data Availability Statement after the conclusion and inside the page limit.
7. [x] Include limitations and ethics.
8. [ ] Replace the artifact URL placeholder after choosing the final artifact-link strategy.

## Evidence

1. [x] Keep deterministic suite claims:
   - 1720/1720 non-clean injected cases killed;
   - 80 clean controls;
   - 0 false positives;
   - 1800 traces;
2. [x] Phrase all results as artifact-suite coverage over implemented operators and fixtures.
3. [x] Do not claim production recall, general authorization, or legal compliance.
4. [x] Add three concrete security examples:
   - model-visible unauthorized metric exposure;
   - stale tenant-key lowering;
   - release leakage despite database containment.
5. [x] Show source-mapped remediation output through the SECUTE doctor fixture.

## Artifact

1. [x] Create an anonymous artifact package outside the private `papers` repo.
   - Path: `/Users/mb1/Code/raintree/products/policystrata/dist/policystrata-secute-2026-anonymous-artifact.zip`
   - SHA256: `d8182fb6d9b6d6a4a8ffec119e53ec6b3d34896bc4c7c24d38fb3ba376e76225`
2. [x] Remove author-identifying metadata from the review archive.
3. [x] Include:
   - README;
   - reproduce script;
   - expected outputs;
   - fixture data;
   - generated trace samples;
   - license;
   - Data Availability statement.
4. [x] Run package checks:
   - `uv run ruff check .` -> pass
   - `uv run mypy src` -> pass
   - `uv run pytest` -> 124 passed, 5 optional integration tests skipped
5. [x] Run fresh artifact checks after unzip:
   - `uv run --extra dev ruff check .` -> pass
   - `uv run --extra dev mypy src` -> pass
   - `uv run --extra dev pytest` -> 100 passed, 5 optional integration tests skipped
   - SECUTE scan -> expected gate fail with 5 high-confidence findings
6. [x] Record artifact SHA256 and final PDF SHA256 in the ledger.
7. [x] Push SECUTE package branch and create PR for anonymous hosting.
   - Branch: `codex/secute-2026-artifact`
   - PR: `https://github.com/raintree-technology/policystrata/pull/8`
8. [ ] Choose final artifact-link strategy. Anonymous GitHub is paused for now because the OAuth
   grant requests broad repository scope.

## Submission Gate

- Do not submit AgenticDev, MAS-GAIN, TRUST, RASE, AISec, DAI, or archival REALM while SECUTE is
  active unless the text and claims are materially distinct and the venue policy permits it.

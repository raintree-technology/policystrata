# SECUTE 2026 Submission Plan

Official page: https://conf.researchr.org/home/ase-2026/secute-2026

Submission site: https://secute2026.hotcrp.com/

Deadline: 2026-07-17 AoE.

## Product

Anonymous 5-page ACM tool/data paper, including references.

## Working Title

Finding Cross-Layer Authorization Drift in LLM Data-Agent Systems

## Core Angle

Frame PolicyStrata as software-security testing infrastructure, not generic AI safety. The key
security claim is that LLM data-agent stacks create policy-bearing surfaces whose cross-layer drift
can expose unauthorized operations, preserve stale tenant/purpose constraints, or release disallowed
result-lineage pairs even when individual components appear locally valid.

## Required Sections

1. Problem and threat model.
2. Policy-bearing surfaces and obligations.
3. Tool workflow: mutation, scan, witness minimization, doctor/audit mode.
4. Security test cases: unauthorized SQL reachability, tenant predicate loss, release leakage, stale policy version, source-mapped remediation.
5. Evaluation snapshot and baselines.
6. Data Availability Statement inside the page limit.
7. Limitations and ethics.

## Double-Blind Requirements

- Remove name, affiliation, email, Raintree URLs, public GitHub owner, public paper URL, BetterOff brand, and author-identifying release tags.
- Use an anonymized artifact link or explain artifact availability according to the SECUTE data availability requirement.
- Do not cite the public PolicyStrata preprint in a way that identifies authors.
- Use the ACM Primary Article Template with `\documentclass[sigconf,review,anonymous]{acmart}`.

## Package Changes To Show

The current artifact already has doctor mode, policy/TOS document classification, prompt-manifest
checks, source maps, trace adapters, and remediation output. For a stronger SECUTE paper, add or
highlight:

- At least three exploit-style traces:
  - stale tenant-key lowering;
  - model-visible unauthorized metric exposure;
  - release of disallowed lineage after DB containment succeeds.
- A source-mapping example from failed trace to route/tool/query-builder file.
- A remediation todo example with owner, file, expected test, and CI command.

## Conflict Rule

SECUTE is the primary archival/workshop target. If submitted, do not simultaneously submit a
substantially similar AgenticDev, MAS-GAIN, TRUST, RASE, AISec, DAI, or REALM archival paper.

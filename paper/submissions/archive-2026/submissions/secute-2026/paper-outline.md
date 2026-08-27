# SECUTE 2026 Paper Outline

## Title

Finding Cross-Layer Authorization Drift in LLM Data-Agent Systems

## Abstract Shape

LLM data agents introduce policy-bearing surfaces that conventional application security tests do
not cover: model-visible tools, semantic validators, SQL compilers, database policy, lineage, and
release filters. PolicyStrata tests whether authorization, semantic, version, lineage, containment,
and release obligations survive transitions across those surfaces. The artifact generates
deterministic mutants and clean controls, imports real SQL/tool traces, executes optional database
fixtures, and emits minimized witnesses that identify the first violated transition. We evaluate it
over deterministic suites and compare against grammar-only, validator-only, SQL-policy, DB-only,
release-only, final-answer, and defense-in-depth baselines. The result is security-test coverage for
implemented drift operators, not a production authorization guarantee.

## Must-Have Claims

- Cross-layer authorization drift is a software-security testing problem.
- Grammar membership and constrained generation are reliability layers, not authorization boundaries.
- RLS is necessary but insufficient because release and semantic obligations can fail after DB containment.
- Witnesses make security failures actionable by identifying the first violated transition.

## Evaluation Claims To Use Carefully

- `1720/1720` covered non-equivalent injected faults killed.
- `80` clean controls and `0` false positives.
- Defense-in-depth baseline: `1561/1720`.
- Brownfield fixture integration is wiring feasibility only, not fault discovery and not production customer-data evidence.

## Required Final Checks

- Double-anonymous PDF.
- Data availability statement inside page limit.
- No author/company/public-release identifiers.
- Fresh reproduce output before final numbers.
- Visual PDF inspection.

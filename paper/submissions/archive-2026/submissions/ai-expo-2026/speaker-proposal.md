# AI Expo 2026 Speaker Proposal

Official page: https://aiexpo.us/call-for-speakers

Deadline: 2026-07-06.

## Title

Testing Policy Drift Before LLM Data Agents Leak or Lie

## Session Type

Technical talk / practitioner session

## Speaker

Zachary Roth

## Title / Organization

Founder, Raintree Technology

## Email

admin@raintree.technology

## Audience

AI engineers, data platform engineers, security engineers, product teams building analytics agents,
and technical leaders shipping governed LLM workflows.

## Short Abstract

LLM data agents can pass local model, SQL, database, and release checks while the composed workflow
still drops tenant scope, changes metric meaning, or releases disallowed data. This talk shows a
practical testing pattern for cross-layer policy drift: decompose policy obligations, wire real
traces into CI, and use deterministic witnesses to debug failures across manifests, validators,
compilers, database policy, lineage, and release filters.

## Abstract

LLM data agents are not one model call. A user request moves through model-visible tools, prompt
manifests, semantic validators, SQL compilers, database policies, row-level security, lineage
tracking, and release filters. Every layer can look locally reasonable while the composed system
leaks the wrong data, drops a tenant constraint, changes metric meaning, or releases an answer whose
lineage should have stayed inside the trust boundary.

This talk presents a practical testing pattern for policy drift in LLM data agents. We will walk
through a concrete governed-analytics failure, show why valid SQL, grammar membership, and database
permissions are not enough on their own, and demonstrate how deterministic regression tests can
catch tenant, purpose, semantic, lineage, and release failures before deployment. The demo uses
PolicyStrata, a reproducible research artifact that emits minimized witnesses identifying the first
violated transition across the agent stack.

The session is designed for engineers and technical leaders who need to ship data agents over
private structured data without pretending that one layer is the whole safety story. Attendees will
leave with a concrete checklist: how to decompose policy obligations, what to test at each boundary,
how to wire traces and release checks into CI, how to account for policy documents and prompt/tool
manifests, and how to avoid overclaiming what constrained generation or RLS can guarantee. The goal
is not to sell a product; it is to give teams a repeatable way to find and debug cross-layer failures
before those failures become production incidents.

## Takeaways

- Why governed agents need cross-layer policy tests, not just model evals or SQL checks.
- How to turn tool manifests, semantic models, SQL traces, RLS checks, and release filters into CI gates.
- How minimized witnesses make policy failures debuggable across product, data, and security teams.

## Speaker Bio

Zachary Roth is the founder of Raintree Technology and the creator of PolicyStrata, a reproducible
research artifact for testing cross-layer policy drift in LLM data-agent stacks. His current work
focuses on deterministic evals, governed data agents, release-policy testing, and CI evidence for AI
systems that query private structured data. He builds practical tooling for teams that need to
connect model-visible interfaces, semantic layers, SQL compilers, database controls, privacy and
terms obligations, and release filters without losing the policy intent between layers. PolicyStrata
has been packaged as a submission artifact with deterministic benchmarks, minimized witnesses,
doctor/audit reports, and brownfield integration evidence.

## Audience Level

Intermediate to advanced technical audience.

## Prior Speaking Experience

PolicyStrata SPLASH/ISSTA 2026 Tool Demonstrations submission video:
https://www.youtube.com/watch?v=skQQajjI7-0

## Video Sample URL

https://www.youtube.com/watch?v=skQQajjI7-0

## Why This Fits AI Expo

The session is practical, technical, and non-commercial. It targets engineers and technical leaders
building or approving AI agents over private data, and it gives attendees a repeatable checklist
rather than a product pitch.

## Demo Outline

1. Start with a tenant-scoped analytics request that looks harmless.
2. Show how the model-visible manifest, semantic validator, SQL compiler, database policy, lineage,
   and release filter can drift independently.
3. Run PolicyStrata on deterministic traces.
4. Inspect a minimized witness that identifies the first violated transition.
5. Show a doctor/audit report that turns missing stack wiring into remediation todos and CI gates.

## Product-Pitch Guardrail

This is not a sales pitch. The session focuses on the open-source testing pattern, concrete failure
modes, and reproducible commands.

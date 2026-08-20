# Product Marketing Context

*Last updated: 2026-08-20 · Auto-drafted from repository evidence*

## Product Overview

**One-liner:** PolicyStrata finds policy drift between the layers of SQL and governed-data agents.

**What it does:** Deterministic scanners and runtimes compare model-visible tools, semantic validation, SQL compilation, database containment, and result release. Findings identify the first broken responsibility, a minimized witness, containment, and the release decision.

**Product category:** Policy regression testing and release gates for AI data systems

**Product type:** MIT-licensed open-source Python and Node packages, self-hosted gateway, and GitHub Action

**Business model:** Free open-source tooling. No paid service or validated commercial offer is documented.

## Target Audience

**Primary users:** Engineers and governance teams building text-to-SQL systems, BI copilots, semantic layers, PostgreSQL RLS, and governed analytics.

**Primary use case:** Detect when policy representations agree locally but disagree across system handoffs.

**Jobs to be done:**

- Regress policy behavior across manifests, validators, compilers, databases, and release filters.
- Produce a small witness that localizes the first failed transition.
- Run repeatable CI without an LLM call.
- Add scanning or runtime enforcement without exporting sensitive payloads.

## Problems and Alternatives

**Core problem:** Point tests can pass at every layer while version skew or translation errors break the policy between layers.

**Alternatives:** Unit tests, model-quality evaluations, authorization controls, database RLS, and penetration tests remain separate controls. PolicyStrata tests cross-layer agreement and does not replace them.

## Differentiation

- Responsibility-scoped contracts test transitions instead of isolated components.
- Findings preserve version vectors, distinguishing results, containment, and release decisions.
- Deterministic generated or imported traces avoid model-call variance in CI.
- Offline scanner, in-process runtime, and self-hosted gateway allow staged adoption.
- Metadata export defaults exclude prompts, rows, documents, and fixture expectations.

## Objections and Fit

| Question | Answer |
| --- | --- |
| Is this an authorization system? | No. The application and database remain the authorization boundaries. |
| Does the benchmark prove production recall? | No. It measures the declared internal fault model. |
| Must traces include prompts or rows? | No. The supported contract uses sanitized policy and decision metadata. |

**Anti-persona:** Teams seeking a generic LLM benchmark, a penetration-testing suite, or a replacement for runtime authorization.

## Customer Language

No verified customer interviews are recorded. Use: policy drift, cross-layer, first failed handoff, minimized witness, containment, release gate, sanitized trace, and version vector. Avoid: proven secure, complete policy coverage, production recall, and replacement for authorization.

## Brand Voice

**Tone:** Technical, forensic, measured, and explicit about responsibility boundaries

**Style:** Lead with a concrete failure path and explain what broke, where it was contained, and what the evidence does not prove.

## Proof Points

- Deterministic demo runs without an LLM key.
- Published Python, Node, gateway, and GitHub Action surfaces.
- The internal operator taxonomy caught 1,720 injected faults; the layered point-control comparison missed 159. This is fault-model evidence only.
- Repository evidence includes traces, minimized witnesses, studies, and an editable paper build.

## Goals

**Primary goal:** Help governed-data teams make cross-layer policy drift a repeatable CI and release decision.

**Conversion action:** Run `uvx policystrata demo --out runs/demo` and inspect the first violated transition.

## Messaging Guardrails

- Always distinguish regression evidence from authorization correctness.
- Keep internal injected-fault results separate from production effectiveness.
- Do not imply that metadata-only export makes every deployment private by default.
- Name the inspected layers and untested surfaces in every result claim.

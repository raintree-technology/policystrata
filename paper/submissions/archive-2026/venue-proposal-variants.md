# Venue Proposal Variants

These are starting points, not final submissions. Keep archival and practitioner products separate.

## Archival Software Engineering Abstract

Title:
PolicyStrata: Cross-Layer Policy Drift Testing for LLM Data Agents

Abstract:
LLM data agents often transform a request through several representations before a result is
released: model-visible capabilities, semantic plans, lowered queries, database enforcement, and
release filters. Existing checks often validate one layer at a time, allowing policy drift to appear
between layers even when each individual component appears reasonable. PolicyStrata is a
regression-testing framework for governed LLM data-agent stacks. It separates authorization,
semantic, and release policies, defines responsibility-scoped conformance contracts across the
pipeline, and reports minimized witnesses that identify the first violated transition. We evaluate
the artifact with DataPolicyDriftBench, deterministic seeded, generated, and detector-frozen
held-out suites, baseline comparators, stable JSONL traces, clean controls, and optional database
smoke fixtures. The current artifact reports witnesses for 1720/1720 injected non-equivalent faults
covered by the implemented operators and fixtures, plus 0 false positives over 80 clean controls.
This result is deterministic suite coverage, not production recall and not an authorization
guarantee.

Best for:
- FSE
- ASE
- ISSTA
- ICSE Research, if registration exists

## ICSE SEIP Practitioner Abstract

Title:
Testing Policy Drift in LLM Data Agents

Abstract:
Teams building LLM data agents often test the model, SQL compiler, database policy, and release
filter separately. The hard failures appear between those layers: a capability visible to the model
may not match the semantic validator, a valid plan may lower into a query with the wrong tenant or
purpose, or a contained database result may still violate release policy. This paper reports a
systematic investigation of cross-layer policy drift in governed data-agent stacks. We present a
responsibility-scoped testing workflow that decomposes policy into authorization, semantic, and
release obligations, injects deterministic policy mutations, and records minimized witnesses that
pinpoint the first violated transition. The artifact includes reproducible suites, JSON/YAML traces,
baseline comparators, and a PostgreSQL/RLS smoke fixture. We focus on practical lessons: what to
test at each boundary, which claims not to make about constrained generation, and how to package
evidence for review and regression.

Best for:
- ICSE SEIP
- practitioner proceedings
- tool demo tracks after adding demo video

## Governance And Accountability Abstract

Title:
Auditable Policy Drift Testing for Governed LLM Data Agents

Abstract:
Governed LLM data agents move requests across layers owned by different teams: model-visible
interfaces, validators, compilers, database policies, and release controls. When these layers drift,
an organization may lose the ability to explain who was authorized to access which data, under what
purpose, and why a result was released. PolicyStrata studies this problem as cross-layer policy
drift. The framework separates authorization, semantic, and release policies, then tests whether
runtime transitions preserve the obligations that matter for governed data use. Rather than treating
grammar membership or valid SQL as security guarantees, it records responsibility-scoped witnesses:
the principal, request, policy version, semantic plan, lowered query, database rows, lineage,
observed result, and first violated transition. We evaluate the approach with deterministic mutation
suites and explicit claim boundaries. The goal is not production authorization, but auditable
evidence for policy regression testing in institutional data-agent deployments.

Best for:
- FAccT next cycle
- AIES next cycle
- governance workshops

Needed before submission:
- stronger institutional context;
- adverse-impact statement;
- ethics statement;
- discussion of accountability users and failure consequences.

## Security Abstract

Title:
Finding Cross-Layer Authorization Drift in LLM Data-Agent Systems

Abstract:
LLM data agents introduce policy surfaces that do not exist in conventional applications. A request
can be shaped by model-visible capabilities, accepted by a semantic validator, compiled into SQL,
filtered by database policy, and transformed again by a release layer. An attacker or confused
principal may exploit drift between these layers even when each layer appears locally valid. This
paper studies cross-layer authorization drift in LLM data-agent systems. We define a threat model for
principals who can issue natural-language data requests but should be constrained by tenant, purpose,
policy version, lineage, and release obligations. PolicyStrata injects non-equivalent policy
mutations across agent, compiler, database, and release boundaries, then reports minimized witnesses
that identify the first transition where an obligation fails. The artifact produces deterministic
traces and supports database-backed checks through PostgreSQL/RLS fixtures.

Best for:
- NDSS fall only after security hardening;
- USENIX Security 2027 only after security hardening;
- CCS next cycle only after security hardening.

Needed before submission:
- concrete adversary and asset model;
- real exploit scenarios, not only injected regressions;
- security baselines;
- ethics and open-science appendices;
- stronger discussion of responsible deployment.

## NeurIPS E&D / ML Evaluation Abstract

Title:
DataPolicyDriftBench: Evaluating Cross-Layer Policy Drift in LLM Data Agents

Abstract:
Evaluation of LLM data agents often focuses on task success, SQL validity, or model behavior, while
policy obligations may be distributed across model-visible capabilities, validators, compilers,
database controls, and release filters. DataPolicyDriftBench evaluates whether agent stacks preserve
authorization, semantic, and release obligations across these transitions. The benchmark defines
deterministic policy mutation families, stable trace formats, baseline comparators, and minimized
witnesses that identify the first violated transition. It is designed to study evaluation
assumptions: what a grammar-constrained agent can and cannot guarantee, which drift classes are
observable at each layer, and how claims change when lineage and release policy are included. The
current artifact reports 1720/1720 deterministic suite coverage over implemented non-equivalent
operators and fixtures, with 0 false positives over 80 clean controls. We present the benchmark
scope, assumptions, limitations, and reproducibility path, emphasizing that the result is
artifact-suite coverage rather than production recall.

Best for:
- NeurIPS Evaluations and Datasets next cycle;
- ICLR workshops;
- evals/benchmarks workshops.

Needed before submission:
- benchmark card;
- evaluation card;
- final-form hosted code/data at submission;
- broader baselines;
- clearer ML evaluation positioning.

## Practitioner Talk: AI Engineer / PyCon / Open Source GenAI

Title:
Testing Policy Drift in LLM Data Agents

Short abstract:
LLM data agents can pass every local check and still release the wrong data. A model manifest,
semantic validator, SQL compiler, database policy, and release filter each see a different version of
the request. This talk shows how policy drift appears between those layers, why valid SQL and grammar
membership are not enough, and how to build deterministic regression tests that catch tenant,
purpose, lineage, and release failures. We will walk through a concrete data-agent failure, run a
small reproducible suite, inspect a minimized witness, and show how the first violated transition
points to the responsible layer. The takeaway is practical: governed agents need tests for policy
obligations as requests move across representations, not only model evals or database permissions.

Audience:
Engineers building data agents, eval frameworks, internal AI tools, Python services, or security and
governance checks for AI-assisted applications.

Takeaways:
- How cross-layer policy drift differs from SQL validity or prompt safety.
- How to design deterministic policy regression tests without an LLM API key.
- How witnesses make failures debuggable across model, compiler, database, and release layers.

## Practitioner Talk: QCon

Title:
Policy Tests for Data Agents With Real Blast Radius

Short abstract:
Production data agents are not one model call. They are a chain of manifests, validators, compilers,
database controls, and release filters, often owned by different teams. The difficult failures happen
between those layers: the model sees one capability, the planner accepts another, SQL lowers away a
tenant or purpose constraint, and the release path exposes a result that no single component meant to
allow. This talk presents a practical testing pattern for policy drift in LLM data agents. We will
use concrete failures to show where conventional model evals and database permissions stop, then
walk through a regression suite that records the first violated transition. The session ends with
patterns teams can adopt: policy decomposition, versioned obligations, lineage-aware release checks,
deterministic mutation suites, and witnesses that make cross-team responsibility explicit.

Audience:
Senior engineers, architects, AI platform teams, data platform teams, and security/governance
engineers running AI systems in production.

## Practitioner Talk: Monktoberfest

Title:
When Policy Crosses Layers: Testing Trust in LLM Data Agents

Short abstract:
A data agent answers a simple question. The model sees a tool it is allowed to call. The planner
accepts a valid-looking request. The compiler emits SQL. The database returns rows. The release layer
formats an answer. Every step can look defensible, and the final result can still violate the policy
the organization thought it had. This talk is about what happens when trust is spread across people,
software layers, and operational assumptions. Using LLM data agents as the concrete case, we will
look at policy drift: failures that appear not inside one component, but between components with
different responsibilities. The technical lesson is how to test these transitions. The social lesson
is that audits, incidents, and reviews need witnesses that say where responsibility first broke, not
just whether something failed.

Audience:
Engineers and technical leaders interested in the relationship between systems, policy, and the
organizations that rely on them.

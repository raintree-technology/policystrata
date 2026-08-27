# Practitioner / Tool Demo Abstract

## Recommended immediate lane

Submit a tool demonstration, poster, or practitioner talk under the title:

**Testing Policy Drift in LLM Data Agents**

This is stronger for practitioner audiences than leading with the package name.

## Abstract

LLM data agents often fail between the layers that look correct in isolation. A model-visible manifest may expose a stale metric alias, a validator may accept the request under a newer policy, a compiler may lower the semantic plan through an older tenant key, database RLS may or may not contain the mistake, and a release filter may still send raw rows or derived results into an LLM context. Testing only generated SQL or final answers misses these cross-layer policy drift failures.

This demo presents PolicyStrata, a deterministic regression-testing and stack-audit tool for governed data-agent stacks. PolicyStrata separates authorization, business semantics, and release policy; generates principals, requests, semantic plans, database states, version vectors, and lowerings; checks responsibility-scoped contracts across manifests, validators, compilers, database policy, lineage, and release; and emits minimized witnesses that identify the first violated transition. Its doctor mode audits whether SQL traces, dbt semantic files, PostgreSQL schema/RLS metadata, privacy policies, terms of service, data-processing and internal-policy documents, prompt manifests, source maps, release coverage, and CI gates are actually wired. The demo walks through a multi-tenant analytics failure, shows the JSONL trace and minimized witness, runs the deterministic reproduction path, inspects a doctor report with remediation todos, and compares PolicyStrata against point baselines such as grammar-only checks, validator-only checks, SQL policy checks, database-only checks, final-answer checks, and a defense-in-depth stack.

The practical takeaway is a CI pattern for teams shipping BI copilots, customer-support analytics agents, product analytics agents, or internal data assistants: treat constrained generation as reliability infrastructure, not an authorization boundary, and test whether policy obligations survive every translation step before release.

For public demos, I can also show a BetterOff finance-assistant integration over real application surfaces with synthetic fixture data: policy and terms documents, prompt manifest, source map, semantic model, SQL/tool traces, Docker PostgreSQL RLS checks, release decisions, and CI workflow wired end to end.

## Demo outline

1. Show a stale manifest/compiler drift case in a governed analytics agent.
2. Run `scripts/reproduce-final.sh`.
3. Inspect a minimized witness with principal, request, version vector, semantic plan, SQL, lineage, and violated obligation.
4. Run `policystrata doctor --config` and inspect privacy and terms document coverage, prompt-manifest drift, source-map coverage, release coverage, and remediation todos.
5. Switch to the BetterOff integration and show a passing brownfield scan over synthetic fixture data.
6. Compare point baselines against the responsibility-scoped detector.
7. Show how clean controls avoid false positives for intentional underexposure and stricter release suppression.

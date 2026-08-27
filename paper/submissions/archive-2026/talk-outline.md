# Talk Outline: Testing Policy Drift in LLM Data Agents

## Title Options

- Testing Policy Drift in LLM Data Agents
- When Valid SQL Is Not Enough
- Cross-Layer Regression Testing for Governed Data Agents

## Audience

Practitioners building BI copilots, text-to-SQL systems, internal analytics agents, or governed LLM
tools that touch enterprise data.

## 25-Minute Version

1. The failure pattern: data-agent policies are copied across manifests, validators, compilers,
   database controls, and release filters.
2. Concrete example: a tenant-scoped support analyst request reaches stale compiler behavior.
3. Why naive equality is wrong: surfaces have different responsibilities.
4. PolicyStrata model: pipeline objects, policy surfaces, and responsibility-scoped contracts.
5. Witness walkthrough: principal, request, version vector, plan, SQL, rows, lineage, result, first
   violated transition.
6. Artifact demo: run seeded suite, inspect `traces.jsonl`, open a minimized witness.
7. Results: 1720/1720 deterministic non-clean coverage, 80 clean controls with 0 false positives,
   baseline misses, claim boundary.
8. Stack audit: privacy and terms documents, prompt manifests, source maps, release coverage, and CI
   gates.
9. Real app smoke evidence: BetterOff finance-assistant integration over real application surfaces
   with synthetic fixture data: policy and terms documents, prompt manifest, source map, semantic
   model, SQL/tool traces, Docker PostgreSQL RLS checks, and CI gate.
10. How teams can adapt this: CI regression gates, scanner traces, DB/RLS containment checks.
11. Limitations and next evidence: blind suites, real incident reconstructions, model-in-the-loop
   reachability.

## Live Demo Path

```bash
cd policystrata
uv run policystrata run --domain support_saas --suite seeded --out runs/talk/seeded
uv run policystrata summarize runs/talk/seeded
open runs/talk/seeded/witnesses
```

Optional scanner demo:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata_clean.yaml --out runs/talk/scan-clean
uv run policystrata scan --config examples/postgres_dbt/policystrata.yaml --out runs/talk/scan
uv run policystrata doctor --config examples/postgres_dbt/policystrata_real_db_clean.yaml \
  --format markdown --out runs/talk/doctor.md
```

The second scanner command is intentionally failing evidence and should be framed as a gate that
correctly blocks known drift.

Optional downstream app demo:

```bash
cd ../betteroff
bun run policystrata:check-generated
bun run policystrata:doctor
bun run policystrata:scan
```

Frame this as public practitioner evidence over real application wiring with synthetic fixture data,
not as production customer-data evidence and not as part of the deterministic benchmark score.

## Visuals To Prepare

- Pipeline diagram: request -> manifest -> validator -> compiler -> database policy -> release.
- One minimized witness screenshot.
- One doctor report screenshot showing policy and terms document coverage and remediation todos.
- One BetterOff CI/scan screenshot showing brownfield application wiring.
- Baseline comparison table.
- Claim-boundary slide: deterministic coverage, not production recall; testing artifact, not
  authorization boundary.

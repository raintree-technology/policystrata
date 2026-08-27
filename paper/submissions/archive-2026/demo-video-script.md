# Demo Video Script

Target length: 6-8 minutes.

Generated quick-demo asset:

- `policystrata-demo-video.mp4`

Use the generated MP4 for the same-day YouTube upload. Use the longer script below if recording a live walkthrough instead.

## Title card

PolicyStrata: Testing Policy Drift in LLM Data Agents

## 0:00-0:45: Problem

"LLM data agents fail across layers. A manifest, validator, compiler, database policy, and release filter can each look reasonable in isolation while the composed system violates tenant scope, metric semantics, lineage, or release policy. PolicyStrata tests those cross-layer obligations directly."

Show:

- `paper-public.pdf` title or website page.
- One sentence from the abstract or claims table.

## 0:45-1:45: Artifact layout

Show terminal:

```bash
cd /Users/mb1/Code/raintree/products/policystrata
ls
find src/policystrata/domains -maxdepth 2 -type f | sort | head -40
```

Say:

"The artifact includes three deterministic analytics domains: support SaaS, finance SaaS, and analytics ClickHouse. The core path requires no LLM API key and no host psql."

## 1:45-3:30: Run deterministic reproduction

Show:

```bash
POLICYSTRATA_RUN_ROOT=/tmp/policystrata-demo ./scripts/reproduce-final.sh
```

While it runs:

"The script freezes benchmark manifests, runs seeded, generated, detector-frozen held-out, and clean-control suites, then emits traces, summaries, minimized witnesses, baselines, ablations, and export-adapter outputs."

Show:

```bash
sed -n '1,80p' /tmp/policystrata-demo/evidence.md
```

Call out:

- `1720/1720`
- `80` clean controls
- `0` false positives

## 3:30-5:00: Inspect one witness

Find a witness:

```bash
find /tmp/policystrata-demo -name '*witness*.json' | head
```

Open one minimized witness and point to:

- principal
- request
- version vector
- semantic plan
- lowered SQL
- lineage
- first violated transition
- violated obligation

Say:

"The goal is not only to know that an answer is wrong. The useful debugging output is the smallest database-backed witness that preserves the violated obligation and identifies where the obligation first failed."

## 5:00-6:15: Audit a stack

Show:

```bash
uv run policystrata doctor --config examples/postgres_dbt/policystrata_real_db_clean.yaml \
  --format markdown --out runs/demo-doctor.md
sed -n '1,120p' runs/demo-doctor.md
```

Say:

"The scanner path answers a different question: what is actually wired in this stack? The doctor report accounts for SQL traces, dbt semantic models, PostgreSQL schema and RLS metadata, privacy policies, terms of service, data-processing and internal-policy documents, prompt manifests, source maps, release coverage, and CI gates. It also gives concrete remediation todos with owners, files, expected tests, and gate commands."

## 6:15-7:15: Baselines

Optional if recording a longer tool-demo walkthrough:

```bash
cd /Users/mb1/Code/raintree/betteroff
bun run policystrata:check-generated
bun run policystrata:doctor
bun run policystrata:scan
```

Say:

"This is a BetterOff finance-assistant integration over real application surfaces with synthetic fixture data. It is not part of the benchmark score and it is not production customer-data evidence. It shows the same PolicyStrata wiring in an application repository: policy and terms documents, prompt manifest, source map, semantic model, SQL and tool traces, Docker PostgreSQL RLS checks, release decisions, and a CI gate. The current scan reports gate pass, zero findings, seven imported-trace checks, and four real database checks."

Show:

```bash
jq . /tmp/policystrata-demo/baselines.json
jq . /tmp/policystrata-demo/ablations.json
```

Say:

"Point baselines catch only the faults visible from their layer. The strongest defense-in-depth baseline catches 1561 out of 1720; the misses are exactly why responsibility-scoped transition obligations matter."

## 7:15-8:00: Close

"PolicyStrata is not an authorization boundary. It is a regression-testing tool for governed data-agent stacks. The practical CI pattern is: keep constrained generation as reliability infrastructure, keep database controls as containment, and test whether authorization, semantic, lineage, and release obligations survive every translation step before release."

End on:

- `https://raintree.technology/papers`
- `https://github.com/raintree-technology/policystrata`

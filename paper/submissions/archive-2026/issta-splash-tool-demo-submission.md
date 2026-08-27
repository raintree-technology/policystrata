# SPLASH/ISSTA 2026 Tool Demo Submission Sheet

Official submission portal: https://splashissta2026-demo.hotcrp.com

Deadline: Friday, June 26, 2026 AoE. This is Saturday, June 27, 2026 at 4:59:59 AM PDT.

## Title

PolicyStrata: Testing Policy Drift in LLM Data Agents

## Authors

Zachary Roth, Raintree Technology

## Short abstract

PolicyStrata is a deterministic regression-testing and stack-audit tool for governed LLM data-agent stacks. It detects cross-layer policy drift among model-visible manifests, grammars, semantic-plan validators, SQL compilers, database policy/RLS, lineage, and release filters. Given canonical authorization, semantic, and release specifications, PolicyStrata generates principals, requests, semantic plans, database states, version vectors, and lowerings; checks responsibility-scoped contracts; and emits minimized witnesses that identify the first violated transition. Its doctor mode audits whether a real stack has SQL traces, dbt semantic files, PostgreSQL schema/RLS metadata, privacy policies, terms of service, data-processing and internal-policy documents, prompt/tool manifests, source maps, release coverage, and CI gates wired. The demo runs the reproducible artifact path, inspects JSONL traces and minimized witnesses, shows a doctor report with remediation todos, and compares PolicyStrata with grammar-only, validator-only, SQL-policy, DB-only, release-only, final-answer, and defense-in-depth baselines.

## Keywords

LLM data agents; policy testing; software testing; authorization; semantic drift; text-to-SQL; row-level security; reproducibility; regression testing

## Tool users

PolicyStrata is intended for engineers and researchers building governed data agents, BI copilots, embedded analytics assistants, product analytics agents, and internal data assistants. The primary users are teams that maintain manifests, semantic layers, validators, SQL compilers, database policies, policy and terms documents, and release filters independently and need CI evidence that policy obligations survive translation across those layers.

For the single-blind tool demo, the kit can also show a BetterOff finance-assistant integration over real application surfaces with synthetic fixture data: policy and terms inputs, prompt manifest, source map, semantic model, SQL/tool traces, Docker PostgreSQL RLS fixture, and CI workflow wired end to end. That integration is useful practitioner evidence, but it is kept separate from the deterministic benchmark headline and is not production customer-data evidence.

## Testing and analysis challenge

Component tests can pass while the composed agent violates policy. A model-visible surface can expose a stale metric alias, a validator can accept a plan under a newer policy, a compiler can lower through an older tenant key, database RLS can contain or miss the problem, and a release filter can still expose unauthorized rows or derived results. PolicyStrata targets these cross-layer-only failures by assigning different obligations to each surface rather than treating all policy representations as equivalent.

The tool demo also covers a deployment-readiness problem: teams often do not know whether their trace exports, privacy and terms inputs, prompt manifests, source maps, database RLS metadata, release tests, and CI gates are wired at all. `policystrata doctor --config` turns that into an auditable checklist with owners, expected files, expected tests, and gate commands.

## How to use the tool

The reviewer-facing path is:

```bash
uv run pytest
uv run ruff check .
uv run mypy src
POLICYSTRATA_RUN_ROOT=/tmp/policystrata-final-submit ./scripts/reproduce-final.sh
uv run policystrata doctor --config examples/postgres_dbt/policystrata_real_db_clean.yaml \
  --format markdown --out runs/doctor.md
```

The final reproduction script writes traces, summaries, minimized witnesses, freeze manifests, baseline reports, ablations, export-adapter outputs, and an artifact report. The doctor command writes stack wiring, policy-document coverage, prompt-manifest comparison, database introspection, and remediation output.

Optional brownfield integration path if the BetterOff repository is checked out beside the artifact:

```bash
cd ../betteroff
bun run policystrata:check-generated
bun run policystrata:doctor
bun run policystrata:scan
```

## Validation results

On controlled deterministic non-equivalent mutant suites, PolicyStrata reports witnesses for 1720/1720 injected faults covered by the implemented operators and fixtures, with 0 false positives on 80 clean controls. Baseline comparators are evaluated over the same traces; the strongest defense-in-depth baseline catches 1561/1720 failures. These are deterministic artifact-suite results, not a claim of recall on unknown production faults and not an authorization-boundary claim.

Separate brownfield smoke evidence from BetterOff currently reports CI gate pass, 0 findings, `ci-gate-ready`, 7 imported-trace checks, and 4 real database checks. This validates real application wiring and CI shape with synthetic fixture data; it is not production customer-data evidence and is not included in the 1720/1720 score.

## Tool Availability

Latest tool version:

- Repository: https://github.com/raintree-technology/policystrata
- Latest tool snapshot: https://github.com/raintree-technology/policystrata/releases/tag/v1.0.0
- PyPI package: https://pypi.org/project/policystrata/1.0.0/
- Paper artifact kit: https://github.com/raintree-technology/policystrata/releases/tag/policystrata-paper-2026-06-26
- Documentation: README, evaluator guide, expected-results document, methodology notes, CLI help, deterministic reproduction script, and test suite.

Current paper and public PDF:

- Website: https://raintree.technology/papers
- PDF: https://raintree.technology/papers/PolicyStrata.pdf

Demonstration video:

- Local MP4 generated for upload: `policystrata-demo-video.mp4`
- Unlisted YouTube URL: https://www.youtube.com/watch?v=skQQajjI7-0
- Finalizer: `./fill-demo-video-url.sh 'https://www.youtube.com/watch?v=skQQajjI7-0'`
- The finalizer inserts the URL, rebuilds the PDF, checks that no TODO remains, verifies 3 pages, and prints the SHA256.
- PDF SHA256: `de90c8d2d44cb79cf7751902c105d64d6303f2fa67ed9779a234b626d4b95642`
- Video SHA256: `ae9a7a9b4e9ff2e886c34ec2ea1dfad76d928f6fbbbc366ee8079b58cf4c86f5`

Archived version:

- Frozen source release: https://github.com/raintree-technology/policystrata/releases/tag/v1.0.0
- Frozen paper artifact release: https://github.com/raintree-technology/policystrata/releases/tag/policystrata-paper-2026-06-26

## Live demo plan

1. Show a support-analytics principal scoped to tenant A.
2. Show a request that should not reach tenant B data.
3. Trigger a stale compiler/tenant-key mutation.
4. Inspect the minimized witness: principal, request, database rows, version vector, semantic plan, SQL, lineage, result, first violated transition, and obligation.
5. Show whether database containment blocked the unauthorized behavior.
6. Run `policystrata doctor --config` and inspect privacy and terms obligation coverage, prompt-manifest drift, source-map coverage, release coverage, and remediation todos.
7. Switch to the BetterOff integration and run `bun run policystrata:doctor` plus `bun run policystrata:scan`.
8. Compare baselines and ablations.
9. Show clean controls to demonstrate intentional asymmetry handling.

## Final HotCRP submission steps

1. Upload `policystrata-demo-video.mp4` to YouTube as unlisted.
2. Run `./fill-demo-video-url.sh 'https://www.youtube.com/watch?v=skQQajjI7-0'`.
3. Upload `issta-splash-tool-demo-paper.pdf` to HotCRP.
4. Preview the uploaded PDF and confirm the final YouTube URL appears.
5. Submit through HotCRP with your account.

Use the short tool-demo PDF for this single-blind track. Do not submit `paper-anon.pdf`, `paper-public.pdf`, or the full archival paper.

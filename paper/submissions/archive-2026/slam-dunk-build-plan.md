# PolicyStrata Slam-Dunk Build Plan

Goal: make the FSE/ASE/ISSTA-style submission hard to reject by improving benchmark rigor,
artifact reproducibility, domain generality, baseline strength, and paper framing.

Primary archival target: FSE 2027 Research.

Secondary targets:

- ASE/ISSTA next cycle with the same package.
- ICSE SEIP with a practitioner rewrite.
- Security venues only after the security hardening track is complete.

## Success Standard

The submission should answer these reviewer questions cleanly:

- Was the detector frozen before the held-out evaluation?
- Is there a real held-out suite, not only public/generated development cases?
- Does the approach generalize beyond one synthetic SaaS domain?
- Are baselines credible alternatives rather than strawmen?
- Does the artifact run from exact commands with expected outputs?
- Are false positives and equivalent/invalid mutations accounted for?
- Does the paper make a narrow claim and avoid security overclaiming?

## Final Evidence Shape

Target final evaluation table:

```text
Suite                         Mutants  Killed  Survived  Equivalent  Invalid  False positives  Frozen
support_dev_seeded            50       ?       ?         ?           ?        -                yes
support_dev_generated         500      ?       ?         ?           ?        -                yes
finance_dev_seeded            20       ?       ?         ?           ?        -                yes
support_heldout_v1            300-500  ?       ?         ?           ?        -                yes
finance_heldout_v1            100-250  ?       ?         ?           ?        -                yes
analytics_clickhouse_seeded   100-200  ?       ?         ?           ?        -                yes
clean_controls                50-100   -       -         -           -        0 target         yes
```

Do not optimize for 100% kill rate at the expense of credibility. A few survived or equivalent cases
are acceptable if they are explained honestly.

## Phase 1: Benchmark Freeze Infrastructure

Purpose: remove the biggest current reviewer objection: `Detector frozen: no`.

Build:

- `benchmark_manifest.json` per run.
- `policystrata freeze-benchmark` CLI.
- `policystrata verify-freeze` CLI.
- Hashes for:
  - mutation registry;
  - detector/detection logic;
  - generator version;
  - policy YAML;
  - surfaces YAML;
  - suite YAML or generation parameters;
  - package version or git commit.
- Run metadata fields:
  - `benchmark_manifest_id`;
  - `detector_frozen`;
  - `detector_freeze_id`;
  - `authored_after_detector_freeze`;
  - `generator_seed`;
  - `mutation_operator_hash`;
  - `detector_hash`.

Acceptance criteria:

- `uv run policystrata freeze-benchmark --domain support_saas --suite generated --count 500 --seed 1729 --out runs/freeze/support-generated.json`
- `uv run policystrata run ... --freeze-manifest runs/freeze/support-generated.json ...`
- Evidence table reports `Detector frozen: yes`.
- Freeze verification fails if mutation code, detector code, policy, surfaces, seed, count, or suite file changes.
- Tests cover stable hashes and tamper detection.

Tests:

```bash
uv run pytest tests/test_benchmark_freeze.py
uv run pytest
uv run ruff check .
uv run mypy src
```

## Phase 2: Held-Out Suites

Purpose: separate development evidence from post-freeze evaluation.

Build:

- `heldout_v1` suite type with explicit metadata:
  - `provenance: secondary_generated` or `externally_authored`;
  - `evidence_level: blinded_suite`;
  - `detector_frozen: true`;
  - `authored_after_detector_freeze: true`.
- Generator mode for held-out cases:
  - different seeds;
  - different principal-role combinations;
  - multi-dimension variants;
  - edge limits around `max_rows`;
  - time-range variants;
  - alias and metric-expression variants.
- Clean control suite:
  - valid authorized requests;
  - valid denied requests that should be cleanly rejected;
  - valid contained database cases;
  - no expected witness.
- Equivalent/invalid mutation accounting:
  - model fields in summary/evidence;
  - reason strings;
  - no silent dropping.

Acceptance criteria:

- At least one held-out suite is generated after freeze and marked separately from development suites.
- Evidence reports held-out results separately.
- Clean controls report false-positive count.
- Invalid/equivalent cases are visible in summary and not counted as kills.

Commands:

```bash
uv run policystrata freeze-benchmark --domain support_saas --suite heldout_v1 --count 500 --seed 260626 --out runs/freeze/support-heldout-v1.json
uv run policystrata run --domain support_saas --suite heldout_v1 --count 500 --seed 260626 --freeze-manifest runs/freeze/support-heldout-v1.json --out runs/final/support-heldout-v1
uv run policystrata run --domain support_saas --suite clean_controls --out runs/final/clean-controls
```

## Phase 3: ClickHouse / Analytics Domain

Purpose: show generality beyond transactional SaaS and PostgreSQL/RLS-style thinking.

Domain name:

```text
analytics_clickhouse
```

Use case:

- embedded product analytics over event/session data;
- tenant/project membership;
- purpose-bound analytics access;
- cohort suppression;
- derived-table/materialized-view lineage;
- ClickHouse row policies for read-only users.

Policy obligations:

- tenant/project filter must be preserved;
- purpose must be preserved;
- aggregate-only roles cannot expose raw event rows;
- release only aggregates with `k >= threshold`;
- row lineage must include source table, project, policy version, and release class;
- semantic lowering must preserve distinct/session/user grain;
- time bucketing must preserve timezone/window semantics.

Mutation families to add:

- `clickhouse_row_policy_missing_project_filter`;
- `clickhouse_row_policy_readonly_assumption_violation`;
- `aggregate_small_cohort_release`;
- `materialized_view_lineage_drop`;
- `timezone_bucket_drift`;
- `uniq_to_count_drift`;
- `sample_clause_release_drift`;
- `distributed_table_policy_gap` if feasible in local fixture.

Implementation choices:

- Start with deterministic simulation so the benchmark remains no-network/no-LLM.
- Add optional Docker ClickHouse integration test after simulator is stable.
- Use official ClickHouse public/example dataset shape, but keep the packaged fixture small and
  deterministic.

Acceptance criteria:

- `analytics_clickhouse` is a built-in domain.
- Seeded suite has at least 100 cases.
- Generated suite supports at least 300 cases.
- Optional ClickHouse Docker smoke test proves row-policy containment for representative cases.
- Docs state ClickHouse row-policy caveat: row policies are meaningful for read-only users.

Tests:

```bash
uv run pytest tests/test_clickhouse_domain.py
POLICYSTRATA_RUN_CLICKHOUSE_TESTS=1 uv run --extra dev pytest tests/test_clickhouse_integration.py
```

## Phase 4: Serious Baselines And Ablations

Purpose: make the comparison look like real alternatives an engineer/reviewer would consider.

Add baselines:

- `grammar_only`;
- `semantic_validator_only`;
- `sql_ast_policy_checker`;
- `db_policy_only`;
- `release_filter_only`;
- `lineage_only`;
- `policy_as_code_precheck`;
- `defense_in_depth_stack_v2`.

Add ablations:

- PolicyStrata without lineage;
- without policy version;
- without release policy;
- without independent oracle;
- without database containment;
- without minimization;
- without transition obligations.

Acceptance criteria:

- Baselines and ablations are documented in code and paper.
- Evidence table separates baselines from ablations.
- Each baseline has a short rationale and a concrete detection rule.
- No baseline relies on hidden knowledge unavailable to that strategy.

Commands:

```bash
uv run policystrata baselines runs/final/support-heldout-v1 --format json --out runs/final/baselines.json
uv run policystrata ablations runs/final/support-heldout-v1 --format json --out runs/final/ablations.json
```

## Phase 5: Artifact Reproduction Hardening

Purpose: make artifact reviewers successful quickly.

Build:

- `scripts/reproduce-final.sh`.
- `conference-kit/reproduce-final.sh`.
- Docker Compose path for optional Postgres and ClickHouse smoke tests.
- `policystrata artifact-report` over all final suites.
- `policystrata doctor` command to check local dependencies.
- Zip/tarball packaging script for anonymous artifact upload.

Acceptance criteria:

- Fresh clone path works with only `uv`.
- Optional database tests never require host `psql`.
- No LLM API key required.
- Outputs include exact expected files:
  - `traces.jsonl`;
  - `summary.json`;
  - `metadata.json`;
  - `benchmark_manifest.json`;
  - `witnesses/*.json`;
  - `evidence.md`;
  - `baselines.json`;
  - `ablations.json`;
  - `artifact-report.md`.

Independent-run protocol:

- Run on three clean environments.
- Record OS, CPU class, runtime, first failure, final status.
- Add `independent-runs.md` to conference kit.

## Phase 6: Paper Rewrite

Purpose: make the paper read like a mature research paper, not a package announcement.

Rewrite around RQs:

- RQ1: Can PolicyStrata detect injected cross-layer policy drift after benchmark freeze?
- RQ2: How does it compare to credible layer-local baselines?
- RQ3: Which obligations matter most? Ablation study.
- RQ4: Do witnesses localize the first violated transition and remain compact?
- RQ5: Does the method transfer across domains/backends, including ClickHouse analytics?

Required paper changes:

- Put formulas in Appendix A only.
- Add one main pipeline diagram.
- Replace product/package language with method/benchmark/artifact language.
- Add benchmark freeze protocol.
- Add held-out protocol.
- Add baseline rationale.
- Add ablation table.
- Add clean-control false-positive table.
- Add ClickHouse/analytics domain subsection.
- Add independent reproduction table.
- Add Data Availability section.
- Add artifact availability statement.
- Add limitations that explicitly avoid production recall and authorization-boundary claims.

Paper acceptance criteria:

- Main paper can be understood without appendix formalism.
- Every headline number maps to a reproducible command.
- No claim depends on PyPI popularity, website, or brand.
- Reviewers can identify the contribution in one sentence:
  "PolicyStrata is a responsibility-scoped conformance testing method and benchmark for cross-layer
  policy drift in LLM data-agent stacks."

## Phase 7: Practitioner Track

Purpose: submit talks while the paper work continues.

Build:

- 5-minute demo script.
- 20-minute talk outline.
- 30-minute talk outline.
- One diagram.
- One terminal recording or GIF.
- One concrete failure story.

Submit:

- Monktoberfest: story/social+technical framing.
- QCon: production-pattern framing.
- PyCon/AI Engineer/Open Source GenAI: next-cycle demo/tool framing.

## Phase 8: Security Hardening Track

Purpose: make USENIX/NDSS/CCS plausible later, not now.

Build:

- attacker model;
- assets and security properties;
- exploit path examples;
- adversarial request generation;
- security baselines;
- responsible disclosure/ethics text;
- abuse-risk analysis.

Security go/no-go:

- Do not submit to security venues until the paper has real exploitability evidence, not only
  injected regression evidence.

## Proposed Work Order

1. Freeze infrastructure.
2. Held-out and clean-control suites.
3. Baselines and ablations.
4. ClickHouse analytics domain.
5. Final reproduction scripts and artifact reports.
6. Final benchmark runs.
7. Paper rewrite.
8. Practitioner talk assets.
9. Optional security hardening.

## Final Verification Commands

```bash
uv run pytest
uv run ruff check .
uv run mypy src
./scripts/reproduce-final.sh
python3 /Users/mb1/Code/raintree/papers/scripts/build_paper.py policystrata
```

## Non-Negotiables

- No LLM API key for deterministic tests.
- No host `psql`.
- Preserve JSON/YAML trace stability; add fields compatibly.
- Keep policy oracle independent from SQL compiler.
- Treat constrained generation as reliability, not authorization.
- Do not hide survived, equivalent, invalid, or false-positive cases.
- Do not submit duplicate archival versions concurrently.


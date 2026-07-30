# Evidence Snapshot

The headline result is the defense-in-depth gap, not the kill count. A layered stack of
conventional point controls (validator, SQL snapshot, database/RLS, final-answer checks) still
misses 159 of 1720 injected cross-layer faults (`defense_in_depth_stack`, 0.91 catch rate).
PolicyStrata's responsibility-scoped contracts catch all 1720 and attribute each to the first
violating surface. Read the 1720/1720 figure as a consistency check over PolicyStrata's own
operator taxonomy — 100% by construction — not as a discovery or recall result.

These numbers measure coverage over PolicyStrata's current deterministic mutation operators and
fixtures. They do not imply recall on unknown production incidents. See
[`docs/methodology.md`](methodology.md) for definitions and limitations.

The tables below were generated with:

```bash
scripts/reproduce-evidence.sh
scripts/reproduce-final.sh
```

Equivalent command sequence:

```bash
scripts/reproduce-final.sh
```

`generated_alt_seed` is currently a secondary deterministic generated suite with a different
default seed. It is not a blinded held-out set. The legacy suite name `held_out` remains accepted as
a compatibility alias.

What this proves:

- PolicyStrata kills every mutant in the current deterministic `seeded`, `generated`,
  detector-frozen generated, detector-frozen `heldout_v1`, finance, and analytics suites.
- Clean controls produce no false positives in the final reproduction path.
- The result is reproducible without an LLM API key.
- Each non-clean trace has a minimized witness and a localized surface responsibility.
- Run metadata records suite provenance and detector-freeze status, so future blinded or
  externally authored suites can be reported separately from public/generated suites.

What this does not prove:

- It does not establish recall on unknown production incidents.
- It does not validate production security-scanner effectiveness.
- It does not remove circularity between the deterministic simulator, expected-label fixtures, and
  detector taxonomy.

## Suite Results

| Suite | Mutants | Killed | Survived | Equivalent | Invalid | Clean controls | False positives | Median witness bytes | Evidence level | Provenance | Detector frozen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| support_seeded | 50 | 50 | 0 | 0 | 0 | 0 | 0 | 3138 | deterministic_fixture | hand_authored | no |
| support_generated | 500 | 500 | 0 | 0 | 0 | 0 | 0 | 3227 | property_generated | generated | yes |
| support_heldout_v1 | 500 | 500 | 0 | 0 | 0 | 0 | 0 | 3227 | detector_frozen_generated | secondary_generated | yes |
| finance_seeded | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 3253 | deterministic_fixture | hand_authored | no |
| finance_heldout_v1 | 250 | 250 | 0 | 0 | 0 | 0 | 0 | 3336 | detector_frozen_generated | secondary_generated | yes |
| analytics_clickhouse_seeded | 100 | 100 | 0 | 0 | 0 | 0 | 0 | 3427 | deterministic_fixture | hand_authored | no |
| analytics_clickhouse_generated | 300 | 300 | 0 | 0 | 0 | 0 | 0 | 3423 | property_generated | generated | yes |
| clean_controls | 80 | 0 | 0 | 0 | 0 | 80 | 0 | 0 | detector_frozen_generated | secondary_generated | yes |

## Evidence Provenance

| Evidence level | Suites | Mutants |
| --- | --- | --- |
| detector_frozen_generated | 3 | 830 |
| deterministic_fixture | 3 | 170 |
| property_generated | 2 | 800 |

## Baselines

| Baseline | Failures caught | Catch rate |
| --- | --- | --- |
| grammar_only | 121/1720 | 0.07 |
| semantic_validator_only | 573/1720 | 0.33 |
| sql_ast_policy_checker | 1043/1720 | 0.61 |
| db_policy_only | 326/1720 | 0.19 |
| release_filter_only | 364/1720 | 0.21 |
| lineage_only | 239/1720 | 0.14 |
| policy_as_code_precheck | 363/1720 | 0.21 |
| defense_in_depth_stack_v2 | 1550/1720 | 0.90 |
| final_answer_only | 920/1720 | 0.53 |
| sql_snapshot | 939/1720 | 0.55 |
| validator_only | 452/1720 | 0.26 |
| db_rls_only | 326/1720 | 0.19 |
| random_data_generation | 1246/1720 | 0.72 |
| naive_surface_equality | 573/1720 | 0.33 |
| defense_in_depth_stack | 1561/1720 | 0.91 |
| conventional_test_suite | 1579/1720 | 0.92 |
| property_differential | 899/1720 | 0.52 |

`defense_in_depth_stack` approximates a layered production control stack by taking the union of
validator-only, SQL-snapshot, database/RLS, and final-answer checks. The remaining 159 misses are
the clearest paper examples for why cross-layer responsibility contracts and witness localization
matter beyond stacked point controls.

`conventional_test_suite` is the stronger, deployable comparator the earlier baselines lacked: six
fixed checks a competent engineer would derive from the contract documents alone (tenant predicate
present, denied metric/dimension rejected, row limit enforced, release blocked on canonical denial,
golden metric values), each traced to a spec clause and not tuned against the operator list. It
catches 1579/1720; its 141 misses are semantic drift on non-golden metrics (70), unsafe releases of
canonically allowed queries (38), and database-containment failures invisible in released values
(33) — the faults that need cross-layer responsibility contracts rather than more point assertions.
`property_differential` is a Cedar-style pairwise differential over surface decisions; it catches
899/1720 and by construction misses drift where every layer agrees on the allow/deny outcome but the
pipeline drifts semantically (613 of its misses are compiler-localized semantic drift). Both flag
0/80 clean controls.

## Extended Studies

These address external-validity and depth gaps beyond the deterministic kill count. Each has its own
doc and a reproduction script; all are deterministic and need no LLM API key unless noted.

| Study | Headline | Doc |
| --- | --- | --- |
| Reconstructed real-fault suite | 19 real public faults (CVEs, RLS incidents) reconstructed and killed; 6 honestly dropped | [incident-reconstruction-results.md](incident-reconstruction-results.md) |
| Spec-blind mutant suite | 42 spec-authored mutants; detector agrees on 39/42, 3 misses expose a real contract ambiguity | [spec-blind-results.md](spec-blind-results.md) |
| Brownfield scans (real OSS) | 0 new real bugs across 4 stacks; ~1.4% real-input FP; true-positive demo on cube's own broken fixtures; 5 scanner gaps found, all 5 now fixed (metricflow adapter warnings 27 → 4) | [brownfield-results.md](brownfield-results.md) |
| Executed real RLS (midday) | all 20 `CREATE POLICY` statements in the frozen migrations loaded verbatim across 6 tables; 13/13 live checks pass intact, weakening one real predicate fails exactly the 4 checks covering it | [brownfield-results.md](brownfield-results.md#live-database-pass-midday) |
| External fault-taxonomy coverage | v1 registry vs an independently authored 8-class data-agent vulnerability taxonomy: 2 covered, 1 partial, 5 outside; 401/1720 cases have no counterpart there | [external-taxonomy-coverage.md](external-taxonomy-coverage.md) |
| Second taxonomy cross-check | LASM's 116-paper vocabulary: v1 occupies 3/7 architectural layers and 1/4 temporal classes | [second-taxonomy-coverage.md](second-taxonomy-coverage.md) |
| Source-frozen MetricFlow | 68 upstream-authored expected-SQL cases reproduced byte-for-byte at an exact Git object; Raintree-authored bridge leaves 68 fuzz mutations surviving | [brownfield-results.md](brownfield-results.md) |
| Maintainer-operated deployment study | deployed and inspected source revisions matched; 33/36 read-only boundary probes passed, with 3 authenticated skips; no customer reads or production mutations | [deployment-study.md](deployment-study.md) |
| Private-source historical replay | 3/3 source-contract changes reproduced; 2 map to v1 and 1 is outside the taxonomy; private identifiers and source excerpts are omitted | [`studies/historical-replay-summary.json`](../studies/historical-replay-summary.json) |
| Counterfactual-repair attribution | attribution is causally validated (sufficiency + necessity), not label-matched; teeth-checked | [counterfactual-repair.md](counterfactual-repair.md) |
| Higher-order / compound mutants | first-transition attribution is stable under distinct-surface composition | [compound-mutants.md](compound-mutants.md) |
| Minimization metrics | per-witness reduction ratios, 1-minimality (100% on standard suites, not guaranteed) | [minimization-metrics.md](minimization-metrics.md) |
| Adversarial clean controls | 0/1000 detector false positives; naive denial-flagging is 285/1000 | [adversarial-clean-controls.md](adversarial-clean-controls.md) |
| Soundness + completeness | witness ⇒ contract violation (property-tested + exhaustive); per-class completeness | [soundness-completeness.md](soundness-completeness.md) |
| Scalability + covering arrays | pairwise covering array cuts cases ~90%; flat per-case cost | [scalability.md](scalability.md) |
| TCB adapter mutation testing | 16 of 18 adapter mutations silently corrupt scan output today | [tcb-analysis.md](tcb-analysis.md) |
| LLM reachability harness | build-only; manifest-skew changes emitted plans (stub); no model runs yet | [reachability.md](reachability.md) |
| Real ClickHouse row-policy check | real row-policy containment evidence (verified against ClickHouse 25.6) | [clickhouse.md](clickhouse.md) |
| Write-action model (v2) | write containment with its own first-transition detector; 48/48 killed, 0 FP | [write-actions.md](write-actions.md) |
| Benchmark versioning + difficulty tiers | difficulty tiers from the baseline matrix; freeze/verify + adapters | [benchmark-versioning.md](benchmark-versioning.md) |

## Known Limitations

- The 1720/1720 result establishes coverage over implemented operators and fixtures, not unknown
  production-fault recall.
- Generated mutants are policy-driven, but they are generated from the same operator taxonomy used
  by the deterministic simulator and expected-label fixtures.
- Equivalent and stillborn mutant accounting is supported in the evidence table; the current
  generators emit none.
- The current witness minimizer is a bounded semantic-IR replay reducer, not a search-based
  delta-debugging reducer.
- Database effects are simulated in deterministic benchmark runs.
- The production pilot verifies deployment identity and live denial boundaries, not authenticated
  cross-tenant behavior; three probes need an isolated smoke principal.
- MetricFlow cases are upstream-authored, but the adapter and study operation are not external or
  PolicyStrata-blind.
- Historical replay verifies source-contract changes without executing the vulnerable services.
- The executed-RLS pass covers all 20 policies across the 6 policy-bearing tables in the frozen
  migrations, but runs them under a Raintree-authored Supabase bridge rather than Midday's
  deployed runtime.
- Both external taxonomy mappings are our reading of another group's classes; their authors did
  not review them, and neither taxonomy is a field distribution.

## Optional Real PostgreSQL RLS Check

This fixture is outside the deterministic benchmark score, but it exercises one containment
table against Dockerized PostgreSQL through the Python adapter:

```bash
docker compose up -d postgres
uv run python scripts/postgres-rls-evidence.py
```

Against a PostgreSQL you already run, set both URLs instead of starting the compose service:

```bash
POLICYSTRATA_DATABASE_URL=postgresql://user:pw@host:5432/support_saas \
POLICYSTRATA_APP_DATABASE_URL=postgresql://app:pw@host:5432/support_saas \
  uv run python scripts/postgres-rls-evidence.py
```

The app role must be a non-owner, non-superuser login role, or row-level security is bypassed and
every check passes without testing anything.

Expected table shape:

| PostgreSQL check | app.tenant_id | Rows | Tenant ids | Result |
| --- | --- | --- | --- | --- |
| accounts RLS | acme | 2 | acme | pass |
| accounts RLS | beta | 2 | beta | pass |
| accounts RLS | &lt;unset&gt; | 0 | - | pass |

## Production Scanner Output

`policystrata scan` is also outside the deterministic benchmark table. It reports gateable findings
over configured dbt files, imported SQL/semantic traces, generated SQL/IR fuzz mutants, and optional
real PostgreSQL fixture checks.

Clean smoke test:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata_clean.yaml --out runs/scan-clean
```

Clean real-DB smoke test:

```bash
docker compose up -d postgres
uv run policystrata scan --config examples/postgres_dbt/policystrata_real_db_clean.yaml --out runs/scan-real-db-clean
```

The real-DB clean fixture now includes a `pass_to_pass` state assertion that executes a read-only
PostgreSQL query and checks that the acme tenant result does not expose beta tenant state.

Intentional gate-failure example:

```bash
uv run policystrata scan --config examples/postgres_dbt/policystrata.yaml --out runs/scan
```

The second config includes imported traces with known authorization, release, and tenant-scope
findings and should exit `1`. The scanner writes `scan.json`, `findings.jsonl`, `summary.json`,
`report.md`, and minimized finding witnesses. These findings carry evidence levels such as
`imported_trace`, `property_generated`, and `real_db`, plus regression case labels such as
`fail_to_pass` or `pass_to_pass`; they are release-gating evidence, not proof that all real-world
policy drift can be detected.

## External Eval Exports

Runs can be exported through adapter files without coupling core execution to external frameworks:

```bash
uv run policystrata export runs/repro/seeded --format inspect --out runs/repro/seeded/inspect.jsonl
uv run policystrata export runs/repro/seeded --format benchflow --out runs/repro/seeded/benchflow.json
uv run policystrata export runs/repro/seeded --format policystrata-json --out runs/repro/seeded/evidence.json
```

The `inspect` and `benchflow` formats are explicit framework adapters. The
`policystrata-json` format is a generic local evidence export with run metadata, aggregate counts,
trace IDs, semantic IR, expected/observed witness classes, decision summaries, artifact refs, and
cost/latency metrics. It intentionally omits raw request text, raw SQL text, and raw database
result values.

These exports package evidence for downstream eval harnesses, CI artifacts, or local audit
handoffs. They are not part of the deterministic benchmark score.

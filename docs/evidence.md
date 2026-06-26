# Evidence Snapshot

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
| support_heldout_v1 | 500 | 500 | 0 | 0 | 0 | 0 | 0 | 3227 | blinded_suite | secondary_generated | yes |
| finance_seeded | 20 | 20 | 0 | 0 | 0 | 0 | 0 | 3253 | deterministic_fixture | hand_authored | no |
| finance_heldout_v1 | 250 | 250 | 0 | 0 | 0 | 0 | 0 | 3336 | blinded_suite | secondary_generated | yes |
| analytics_clickhouse_seeded | 100 | 100 | 0 | 0 | 0 | 0 | 0 | 3427 | deterministic_fixture | hand_authored | no |
| analytics_clickhouse_generated | 300 | 300 | 0 | 0 | 0 | 0 | 0 | 3423 | property_generated | generated | yes |
| clean_controls | 80 | 0 | 0 | 0 | 0 | 80 | 0 | 0 | blinded_suite | secondary_generated | yes |

## Evidence Provenance

| Evidence level | Suites | Mutants |
| --- | --- | --- |
| blinded_suite | 3 | 830 |
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

`defense_in_depth_stack` approximates a layered production control stack by taking the union of
validator-only, SQL-snapshot, database/RLS, and final-answer checks. The remaining 159 misses are
the clearest paper examples for why cross-layer responsibility contracts and witness localization
matter beyond stacked point controls.

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

## Optional Real PostgreSQL RLS Check

This fixture is outside the deterministic benchmark score, but it exercises one containment
table against Dockerized PostgreSQL through the Python adapter:

```bash
docker compose up -d postgres
uv run python scripts/postgres-rls-evidence.py
```

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
```

These exports package tasks, traces, and deterministic verifier expectations for downstream eval
harnesses. They are not part of the deterministic benchmark score.

# Evidence Snapshot

These numbers measure coverage over PolicyStrata's current deterministic mutation operators and
fixtures. They do not imply recall on unknown production incidents. See
[`docs/methodology.md`](methodology.md) for definitions and limitations.

The tables below were generated with:

```bash
scripts/reproduce-evidence.sh
```

Equivalent command sequence:

```bash
uv run policystrata run --domain support_saas --suite seeded --out runs/repro/seeded
uv run policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out runs/repro/generated
uv run policystrata run \
  --domain support_saas \
  --suite generated_alt_seed \
  --out runs/repro/generated_alt_seed
uv run policystrata run --domain finance_saas --suite seeded --out runs/repro/finance
uv run policystrata evidence \
  seeded=runs/repro/seeded \
  generated=runs/repro/generated \
  generated_alt_seed=runs/repro/generated_alt_seed \
  finance_saas=runs/repro/finance \
  --out runs/repro/evidence.md
```

`generated_alt_seed` is currently a secondary deterministic generated suite with a different
default seed. It is not a blinded held-out set. The legacy suite name `held_out` remains accepted as
a compatibility alias.

What this proves:

- PolicyStrata kills every mutant in the current deterministic `seeded`, `generated`,
  `generated_alt_seed`, and `finance_saas` seeded suites.
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

| Suite | Mutants | Killed | Survived | Equivalent declared | Median witness bytes | Evidence level | Provenance | Detector frozen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| seeded | 50 | 50 | 0 | 0 | 3138 | deterministic_fixture | hand_authored | no |
| generated | 500 | 500 | 0 | 0 | 3227 | property_generated | generated | no |
| generated_alt_seed | 50 | 50 | 0 | 0 | 3227 | property_generated | secondary_generated | no |
| finance_saas | 20 | 20 | 0 | 0 | 3253 | deterministic_fixture | hand_authored | no |

## Evidence Provenance

| Evidence level | Suites | Mutants |
| --- | --- | --- |
| deterministic_fixture | 2 | 70 |
| property_generated | 2 | 550 |

## Baselines

| Baseline | Failures caught | Catch rate |
| --- | --- | --- |
| final_answer_only | 304/620 | 0.49 |
| sql_snapshot | 350/620 | 0.56 |
| validator_only | 178/620 | 0.29 |
| db_rls_only | 134/620 | 0.22 |
| random_data_generation | 438/620 | 0.71 |
| naive_surface_equality | 225/620 | 0.36 |
| defense_in_depth_stack | 573/620 | 0.92 |

`defense_in_depth_stack` approximates a layered production control stack by taking the union of
validator-only, SQL-snapshot, database/RLS, and final-answer checks. The remaining 47 misses are
the clearest paper examples for why cross-layer responsibility contracts and witness localization
matter beyond stacked point controls.

## Known Limitations

- The 620/620 result establishes coverage over implemented operators and fixtures, not unknown
  production-fault recall.
- Generated mutants are policy-driven, but they are generated from the same operator taxonomy used
  by the deterministic simulator and expected-label fixtures.
- Equivalent and stillborn mutant accounting is supported in the evidence table; the current
  generators emit none.
- The current witness minimizer is a bounded semantic-IR replay reducer, not a search-based
  delta-debugging reducer.
- Database effects are simulated in deterministic benchmark runs.

## Optional Real PostgreSQL RLS Check

This fixture is outside the 620-mutant deterministic benchmark, but it exercises one containment
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
harnesses. They are not part of the 620-mutant score.

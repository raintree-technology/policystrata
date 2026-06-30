# PolicyStrata Eval Card

PolicyStrata is a deterministic policy-regression environment for governed LLM data-agent stacks.
It is not an authorization boundary, a generic LLM leaderboard, or a claim of production incident
recall.

## Scope

PolicyStrata evaluates whether authorization, semantic, database-containment, and release
obligations survive translation across policy-bearing surfaces:

- model-visible manifests;
- grammars and semantic IR;
- validators;
- SQL compilers;
- database controls;
- output-release checks.

The core artifact uses deterministic semantic plans and traces. It does not require an LLM API key.
The oracle and surface contracts form an executable specification boundary; scan results are
counterexamples or regression evidence, not universal correctness proofs.

## Current Suites

| Suite | Provenance | Boundary |
| --- | --- | --- |
| `support_saas` seeded | public hand-authored fixture | regression coverage, not recall |
| `support_saas` generated | deterministic operator-generated cases | generated from the same public taxonomy |
| `support_saas` generated_alt_seed | secondary deterministic generated suite | reproducibility evidence, not blinded held-out evidence |
| `support_saas` heldout_v1 | detector-frozen generated cases | held out from development after freeze, not externally authored |
| `finance_saas` seeded | second synthetic built-in domain | reduces single-domain risk, still synthetic |
| `finance_saas` heldout_v1 | detector-frozen generated cases | second-domain held-out coverage |
| `analytics_clickhouse` seeded/generated | ClickHouse-style analytics fixture | domain-transfer evidence, deterministic simulation |
| `clean_controls` | generated no-drift controls | false-positive accounting |

The current final reproduction path reports 1720/1720 killed non-clean injected cases and 0 false
positives on 80 clean controls. That means coverage over the implemented deterministic operators
and fixtures. It does not mean PolicyStrata detects all real-world policy drift.

Run metadata records each suite's evidence level, provenance, and detector-freeze status. Future
externally authored or incident-reconstruction suites should be reported separately from this
deterministic artifact-suite score.
`benchmark_manifest.json` records detector, generator, mutation registry, policy, surfaces, suite,
and task hashes for frozen runs.

## Scanner Evidence Levels

Scanner findings carry evidence levels:

- `deterministic_fixture`: built-in or explicitly configured fixtures.
- `property_generated`: generated SQL/IR mutants over configured inputs.
- `imported_trace`: imported production or representative traces.
- `real_db`: PostgreSQL fixture or RLS observations through Python adapters.
- `blinded_suite`: externally authored or detector-frozen suites when provided.

These levels describe what was exercised. They are not confidence intervals for unknown production
faults.

## Regression Gate Semantics

PolicyStrata scanner traces and state assertions may be labeled:

- `fail_to_pass`: known drift evidence should now be caught or contained.
- `pass_to_pass`: legitimate behavior should stay clean.
- `contain_to_contain`: a risky request should remain contained by a later layer.
- `deny_to_deny`: a forbidden request should remain denied.
- `allow_to_allow`: an authorized request should remain usable.
- `unclassified`: legacy or unlabeled imported evidence.

Release gates should not rely only on failing examples. A useful gate includes both
`fail_to_pass` evidence and `pass_to_pass`/`allow_to_allow` maintenance evidence so fixes do not
create over-restriction regressions.

## Real Database Boundary

Deterministic benchmark runs simulate database effects. The scanner can optionally prepare a
Docker/PostgreSQL fixture, execute read-only imported SQL beside canonical compiler SQL, run RLS
checks, and evaluate state assertions over result rows. Host `psql` is not required.

The current real-DB fixture is a smoke test for containment and SQL behavior. It is not an
end-to-end dbt/warehouse execution harness and should not be represented as one.

## Benchmark Integrity

Current limitations:

- no blinded externally authored held-out suite is shipped;
- no verified real incident reconstructions are shipped;
- synthetic domains may miss organization-specific policy nuance;
- generated mutants share the public operator taxonomy;
- baseline comparators are simple observability controls, not independent production test suites;
- bounded witness reduction is not full delta debugging or source-code root-cause localization.

External validation should follow `docs/external-suite-protocol.md` and, for real incidents,
`docs/incident-reconstruction-template.md`.

## Model-In-The-Loop Use

Model-mediated experiments are a reachability layer on top of deterministic conformance. They
should report reliability separately from capability:

- `reachability@k`: at least one of `k` attempts reached a witness.
- `policy_pass^k`: all `k` independent attempts respected the policy.
- `release_safe^k`: all `k` independent attempts avoided unsafe release.

Do not mix these with deterministic mutant kill rate.

# Methodology

This document defines what the current PolicyStrata evidence measures and, just as important, what
it does not measure.

## Current Claim

The current benchmark reports 620/620 killed mutants across the `seeded`, `generated`,
`generated_alt_seed`, and `finance_saas` seeded suites. These results measure coverage over the
current deterministic mutation operators and fixtures. They do not imply recall on unknown
production incidents.

PolicyStrata should be described as:

> On the current deterministic public and generated mutant suites, PolicyStrata kills 620/620
> non-equivalent mutants. This establishes artifact coverage over the implemented mutation
> operators, not recall on unknown production faults.

Do not describe the result as detecting all policy drift.

## What Counts As A Mutant

A mutant is a deterministic injected cross-layer drift case. Each mutant is described by a
`MutationSpec` with:

- an affected surface;
- a witness class;
- a human-readable drift description;
- optional containment expectations.

The current generated suite is policy-driven but not blind. It takes the domain policy, surface
versions, seed, and mutation operators, then constructs task variants by selecting principals,
metrics, dimensions, time ranges, and limits from the policy. It does not yet mutate arbitrary
external application code or SQL text and then infer labels from scratch.

The runner simulates the affected layer behavior from the mutation fixture, then classifies the
resulting trace from canonical decisions, surface decisions, contract decisions, SQL-lowering flags,
database-result flags, and release decisions. Expected labels remain in the fixtures for regression
tests and accuracy summaries. That means generated mutants are stronger than hand-expanded fixtures,
but weaker than independent unknown production bugs.

## Suite Definitions

`seeded` is a static public suite. It is useful for regression tests and artifact reproducibility.

`generated` is a deterministic programmatic suite. It uses the implemented mutation operators and a
configurable seed/count to synthesize many task variants from domain policy metadata.

`generated_alt_seed` is a secondary deterministic generated suite with a different default seed and
count. It is not a blinded research held-out set. The legacy suite name `held_out` remains accepted
for compatibility, but paper language should call these cases `generated_alt_seed` or `secondary
generated`, unless the detector has been frozen before the cases are generated or authored
independently.

`finance_saas` is a second domain with different entities and scope semantics. It reduces the
single-domain artifact risk, but it is still a built-in synthetic fixture.

## Killed, Survived, Equivalent, Stillborn

A mutant is counted as killed when PolicyStrata emits a non-clean witness for the trace.

A mutant is counted as survived when the run emits a clean trace for a mutant task.

An equivalent mutant is a mutation that does not change the policy-observable behavior for the
generated principal, query, and database state.

A stillborn mutant is malformed before evaluation, for example because it creates an invalid
semantic query or cannot be compiled into the expected trace shape.

The evidence table computes `Equivalent declared` from clean expected witness labels. It is zero for
the current suites because the current generators do not emit equivalent or stillborn mutants.
Equivalent-mutant discovery is not implemented yet. If future generators can produce equivalent or
stillborn cases, they should be counted separately rather than silently removed.

## What PolicyStrata Can Observe

PolicyStrata observes:

- the canonical policy oracle decision over semantic IR;
- per-surface decisions;
- declared surface responsibility contracts;
- compiled SQL;
- simulated database effects for deterministic fixtures;
- containment and release decisions;
- minimized witness records.

The policy oracle is intentionally independent from the SQL compiler path.

`policystrata scan` adds production-oriented observations over configured inputs:

- dbt semantic-model metadata and expression references;
- imported SQL and semantic trace JSONL records;
- deterministic SQL/IR fuzz mutants over imported traces;
- optional real PostgreSQL fixture/RLS results through Python/`psycopg`;
- optional imported-SQL execution against canonical compiler SQL on the same PostgreSQL fixture;
- gateable findings with evidence levels.

The scanner is a regression-testing and release-gating tool. It is not the authorization boundary;
the host application and database policies remain responsible for enforcement.

## Evidence Levels

Production scan findings report evidence levels instead of universal detection claims:

- `deterministic_fixture`: built-in or explicitly configured fixtures.
- `property_generated`: generated SQL/IR mutants over configured inputs.
- `imported_trace`: imported production or representative traces.
- `real_db`: real PostgreSQL fixture/RLS observations.
- `blinded_suite`: externally authored or detector-frozen suites when provided.

These levels describe what was exercised. They do not prove recall over unknown production faults.

## Detector Freeze Boundary

Each run metadata file records the mutation operator IDs used by that run. This helps reviewers
compare evidence snapshots against a specific operator set, but it is not a substitute for a
blinded evaluation.

A blinded suite should be produced only after the detector and operator taxonomy are frozen, or by
an external author who does not tune cases against PolicyStrata behavior. Until then,
`generated_alt_seed` should be treated as reproducibility evidence, not external recall evidence.

## What Baselines Can Observe

The current baselines are deliberately simple:

- `final_answer_only`: catches only released semantic differences.
- `sql_snapshot`: catches compiler-local SQL shape changes, except cost-only drift.
- `validator_only`: catches unauthorized queries that the canonical validator rejects outside a
  validator-local mutation.
- `db_rls_only`: catches database containment cases.
- `random_data_generation`: catches semantic differences exposed by the deterministic generated
  database result.
- `naive_surface_equality`: catches any surface decision that differs from the canonical decision,
  which is intentionally too strict for layers that should be asymmetric.

All baselines receive the same traces. They are not full reimplementations of production testing
systems, and their purpose is to make the observability gap explicit. PolicyStrata's own killed
count is reported in the suite table rather than as a self-referential baseline.

## Witnesses

The current witness minimizer performs bounded semantic-IR replay reduction and then emits a compact
projection of the reduced trace. It tries to remove dimensions, remove filters, and reset non-default
limits. A candidate reduction is accepted only if replay preserves the witness class, first violated
surface, containment layer, release decision, localized contract failure, and semantic-drift or
database-containment evidence when present.

It preserves:

- task ID;
- witness class;
- localized surface;
- containment layer;
- principal and request;
- replay-reduced semantic IR;
- surface versions;
- surface responsibilities;
- contract decisions;
- transition obligations;
- compiled SQL;
- database result;
- release decision;
- explanatory reasons.

This is not a delta-debugging reducer or proof of globally minimal input. It is a bounded replay
reducer over the current semantic IR shape. Future minimization that changes metrics, time windows,
joins, rows, or source code must test that the same witness class, first violated surface, principal
meaning, database distinction, and containment status remain unchanged.

## Current Limitations

- Generated mutants are derived from the same taxonomy used by the deterministic simulator and
  expected-label fixtures.
- `generated_alt_seed` is not a blinded held-out set; legacy `held_out` is only a compatibility
  alias for that secondary generated suite.
- Equivalent and stillborn mutant accounting is defined, but the current generators do not emit
  those cases.
- Database effects are simulated for deterministic benchmark runs.
- The dbt integration is a semantic-name comparison adapter, not an end-to-end dbt execution
  harness.
- Finance and support domains are still synthetic built-in fixtures.
- Baselines are simple observability models, not full production test suites.

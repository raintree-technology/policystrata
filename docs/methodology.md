# Methodology

This document defines what the current PolicyStrata evidence measures and, just as important, what
it does not measure.

## Current Claim

The current final reproduction path reports 1720/1720 killed non-clean injected cases and 0 false
positives across 80 clean controls. The result spans support SaaS, finance SaaS, and
ClickHouse-style analytics domains, including detector-frozen generated and `heldout_v1` suites.
These results measure coverage over the current deterministic mutation operators and fixtures. They
do not imply recall on unknown production incidents.

PolicyStrata should be described as:

> On the current deterministic public, generated, and detector-frozen generated suites,
> PolicyStrata kills 1720/1720 non-clean injected cases and reports 0 false positives on 80 clean
> controls. This establishes artifact coverage over the implemented mutation operators, not recall
> on unknown production faults.

Do not describe the result as detecting all policy drift.

## Formal-Verification Boundary

PolicyStrata uses a formal-verification-style separation between specification and implementation.
The canonical policy oracle is the executable specification, each stack surface is a
policy-preserving translation boundary, and transition obligations are the invariants that should
survive across those boundaries.

PolicyStrata does not discharge proof obligations with a proof assistant, SMT solver, or verified
compiler. Its evidence is falsification-oriented: deterministic fixtures, generated mutants,
imported traces, optional database checks, and minimized witnesses. A witness is a reproducible
counterexample for the exercised trace and configured policy, not a universal proof about every
possible program, query, database state, or release path.

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

`analytics_clickhouse` is a ClickHouse-style product analytics domain. It exercises project-scope
row policies for read-only users, aggregate-only roles, cohort release thresholds, timezone
bucketing, unique-user/session grain, and materialized-view lineage. The deterministic benchmark
simulates effects; the optional ClickHouse Docker test is a service smoke test, not part of the
kill-rate claim.

## Killed, Survived, Equivalent, Stillborn

A mutant is counted as killed when PolicyStrata emits a non-clean witness for the trace.

A mutant is counted as survived when the run emits a clean trace for a mutant task.

An equivalent mutant is a mutation that does not change the policy-observable behavior for the
generated principal, query, and database state.

A stillborn mutant is malformed before evaluation, for example because it creates an invalid
semantic query or cannot be compiled into the expected trace shape.

The evidence table reports killed, survived, equivalent, invalid, clean-control, and false-positive
counts separately. Equivalent and invalid counts are zero for the current suites because the current
generators do not emit those cases. If future generators can produce equivalent or stillborn cases,
they should be counted separately rather than silently removed.

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
- optional database state assertions over row counts, result columns, and allowed or forbidden
  values;
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

## Regression Gate Cases

Scanner inputs can label examples with regression case semantics:

- `fail_to_pass`: known policy drift should now be caught or contained.
- `pass_to_pass`: legitimate behavior should remain clean.
- `contain_to_contain`: later containment should continue blocking an attempted violation.
- `deny_to_deny`: forbidden behavior should stay denied.
- `allow_to_allow`: authorized behavior should stay usable.
- `unclassified`: legacy imported evidence without a case label.

These labels follow the same spirit as regression-test maintenance sets: a useful release gate
needs both bug-catching cases and behavior-preserving cases. The labels appear in scan summaries,
finding witnesses, and reports; they do not change the core policy oracle.

## Detector Freeze Boundary

Each run metadata file records the mutation operator IDs used by that run. This helps reviewers
compare evidence snapshots against a specific operator set, but it is not a substitute for a
blinded evaluation.

Run metadata also records suite provenance:

- `evidence_level`;
- `suite_provenance`;
- `detector_frozen`;
- `detector_freeze_id`;
- `authored_after_detector_freeze`;
- structured `suite_metadata` copied from static suite files when provided.

Static task suites can declare this metadata in `suite_metadata` at the top of the suite YAML. The
runner copies it into `metadata.json`, and `policystrata evidence` reports it beside the suite
score. This makes detector-frozen and externally authored suites separable from public generated
suites without changing trace JSON.

A blinded suite should be produced only after the detector and operator taxonomy are frozen, or by
an external author who does not tune cases against PolicyStrata behavior. Until then,
`generated_alt_seed` should be treated as reproducibility evidence, not external recall evidence.
The working protocol for these suites is in
[`external-suite-protocol.md`](external-suite-protocol.md).

`policystrata freeze-benchmark` creates a benchmark manifest with hashes for detector source,
mutation operators, generator source, policy YAML, surfaces YAML, suite materialization, task
materialization, package version, and git commit when available. `policystrata run
--freeze-manifest` verifies those hashes before producing traces and copies the manifest into the
run directory.

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
- `defense_in_depth_stack`: catches a failure if any of `validator_only`, `sql_snapshot`,
  `db_rls_only`, or `final_answer_only` would catch it. This approximates a plausible layered
  production control stack, but it still lacks PolicyStrata's cross-layer responsibility contracts
  and witness localization.
- `grammar_only`, `semantic_validator_only`, `sql_ast_policy_checker`, `db_policy_only`,
  `release_filter_only`, `lineage_only`, `policy_as_code_precheck`, and
  `defense_in_depth_stack_v2`: reviewer-facing variants that separate layer-local controls from
  cross-layer responsibility checks.

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
- `heldout_v1` is detector-frozen generated evidence when run with a freeze manifest, but it is not
  externally authored by default.
- Equivalent and stillborn mutant accounting is defined, but the current generators do not emit
  those cases.
- Database effects are simulated for deterministic benchmark runs.
- Scanner state assertions are real database checks, but they are still fixture-level evidence
  unless run against a representative warehouse clone.
- The dbt integration is a semantic-name comparison adapter, not an end-to-end dbt execution
  harness.
- Finance, support, and analytics domains are still synthetic built-in fixtures.
- Baselines are simple observability models, not full production test suites.

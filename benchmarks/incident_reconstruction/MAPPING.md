# Incident reconstruction: fault -> operator mapping

Source ledger: `real-faults.json` (25 verified, citation-backed cross-layer policy faults; see the
external review). This directory reconstructs 19 of those 25 as deterministic PolicyStrata tasks
in `tasks/reconstructed.yaml`, mapped onto PolicyStrata's existing 22 mutation operators in
`src/policystrata/mutations.py`. No new operator was added. 6 faults were not reconstructed; see
"Dropped faults" below.

Run: `uv run policystrata run --domain incident_reconstruction --domain-path benchmarks/incident_reconstruction --suite reconstructed --out runs/incident-reconstruction`.
Result: 19/19 killed, localization_accuracy 1.0, expected_class_accuracy 1.0 (see
`docs/incident-reconstruction-results.md`).

## Included faults (19)

| Fault ID | Source | Operator | Surface / witness class | Justification |
|---|---|---|---|---|
| pg-cve-2019-10130-selectivity-rls | [postgresql.org CVE-2019-10130](https://www.postgresql.org/support/security/CVE-2019-10130) | `db_rls_old_ownership_field` | database / over_permissive | The planner reads row values through statistics before RLS is applied, so the enforced policy stops actually restricting the rows it claims to; that is exactly what a database-surface over-permissive operator represents. |
| pg-cve-2023-2455-rls-inlining | [postgresql.org CVE-2023-2455](https://www.postgresql.org/support/security/CVE-2023-2455) | `compiler_uses_old_tenant_key` | compiler / lowering_violation (containment: database) | A plan built under one role's identity is executed under another after inlining -- the compiler emits a lowering keyed to a stale identity instead of the current principal, the same shape as using a legacy tenant key. |
| pg-cve-2024-10976-rls-subquery | [postgresql.org CVE-2024-10976](https://www.postgresql.org/support/security/CVE-2024-10976) | `compiler_swaps_tenant_account_id` | compiler / lowering_violation (containment: database) | Incomplete tracking of RLS tables reached via subquery/CTE/view/function means the compiled predicate ends up anchored to the wrong identity column for that reference path, matching an operator that swaps which identity column scopes the predicate. |
| pg-cve-2021-3393-partition-error-leak | [postgresql.org CVE-2021-3393](https://www.postgresql.org/support/security/CVE-2021-3393) | `aggregate_small_cohort_release` | release / unsafe_release | A column-privilege boundary is bypassed by an output channel (the error message) the boundary doesn't cover -- a release-layer disclosure, regardless of the specific channel. |
| pg-cve-2016-2193-plancache-rls-role | [postgresql.org CVE-2016-2193](https://www.postgresql.org/support/security/CVE-2016-2193) | `compiler_drops_tenant_predicate` | compiler / lowering_violation (containment: database) | A cached plan reused across a role change never recomputes the row-security predicate for the new role -- equivalent to the compiler's lowering never carrying the tenant-scope predicate forward. |
| pg-cve-2017-7484-selectivity-column-priv | [postgresql.org CVE-2017-7484](https://www.postgresql.org/support/security/CVE-2017-7484) | `db_rls_old_ownership_field` | database / over_permissive | Column-privilege analogue of CVE-2019-10130 (selectivity functions bypass column SELECT privilege instead of row security); same resulting drift shape, so the same operator. |
| pg-cve-2014-8161-constraint-error-column-leak | [postgresql.org CVE-2014-8161](https://www.postgresql.org/support/security/CVE-2014-8161) | `sample_clause_release_drift` | release / unsafe_release | Predecessor pattern to CVE-2021-3393 (constraint-violation errors leak forbidden column values); a different release operator is used to keep the two fixtures distinguishable while both represent the same output-channel disclosure class. |
| pg-cve-2024-10978-setrole-wrong-userid | [postgresql.org CVE-2024-10978](https://www.postgresql.org/support/security/CVE-2024-10978) | `db_rls_old_ownership_field` | database / over_permissive | SET ROLE applying the wrong user ID mid-query means RLS ends up evaluated against the wrong identity value -- represented the same way as a policy referencing a stale/wrong ownership field. |
| supabase-cve-2025-48757-missing-rls-anon-read | [mattpalmer.io writeup](https://mattpalmer.io/posts/2025/05/CVE-2025-48757/) | `app_deny_missing_db_policy` | database / over_permissive | The application/manifest assumed tenant-scoped access that was never enforced in the database (RLS never enabled) -- a direct, near-literal match for "a declared deny rule was not propagated into the database policy." |
| supabase-security-definer-view-bypass | [Supabase database-advisors lint 0010](https://supabase.com/docs/guides/database/database-advisors?lint=0010_security_definer_view) | `clickhouse_row_policy_readonly_assumption_violation` | database / over_permissive | A SECURITY DEFINER view runs as its creator rather than the caller, invalidating an assumption about which identity/context the row policy is evaluated under -- the closest existing operator modeling "a row-policy assumption is invalidated by the execution context," even though the specific context here is view ownership, not read-only mode. |
| clickhouse-issue-21084-mv-vs-base-rowpolicy | [ClickHouse#21084](https://github.com/ClickHouse/ClickHouse/issues/21084) | `distributed_table_policy_gap` | database / over_permissive | A materialized view is a second read path over the same underlying data that does not re-apply the base table's row policy -- structurally identical to "a distributed-table read bypasses a local-table row policy." |
| clickhouse-issue-12544-malformed-policy-failopen | [ClickHouse#12544](https://github.com/ClickHouse/ClickHouse/issues/12544) | `app_deny_missing_db_policy` | database / over_permissive | A parse failure means a declared row policy is never loaded, leaving its table unenforced -- the declared-vs-enforced-policy gap this operator represents, here caused by a config-loader bug rather than a missing propagation step. |
| cube-cve-2022-23510-sqlrunner-rls-bypass | [GHSA-6jqm-3c9g-pch7](https://github.com/cube-js/cube/security/advisories/GHSA-6jqm-3c9g-pch7) | `validator_omits_sensitive_column` | validator / over_permissive | The `/v1/sql-runner` endpoint bypasses Cube's modeling-layer authorization (`queryRewrite`) entirely for that request path -- reconstructed as the validator surface omitting its scoping/authorization obligation, the closest existing validator-level over-permissive operator (the specific "sensitive column" framing is a stand-in for "an obligation the validator should apply to this request path"). |
| looker-access-filter-pitfalls | [Looker access_filter reference](https://cloud.google.com/looker/docs/reference/param-explore-access-filter) | `stale_metric_alias_manifest` | manifest / over_permissive | Looker's own docs describe an Explore missing `access_filter` as not row-restricted at all -- a capability that should have been gated remains exposed at the model-config (manifest) layer, matching a manifest-surface over-permissive operator. This fixture reconstructs only the "missing filter" sub-case of the three pitfalls the source documents (missing filter, wildcard-value workaround, SQL Runner bypass); the other two are noted but not separately reconstructed. |
| metricflow-issue-1489-timefilter-dropped | [dbt-labs/metricflow#1489](https://github.com/dbt-labs/metricflow/issues/1489) | `fiscal_calendar_mismatch` | compiler / semantic_drift | A declared `metric_time` filter is not re-applied to the time-spine table after aggregation, so compiled SQL returns rows outside the requested window -- matches an operator representing the compiler using the wrong compiled time bounds for a declared time-scoped query. |
| metabase-cve-2024-55951-sandbox-filter-cache | [GHSA-rhjf-q2qw-rvx3](https://github.com/metabase/metabase/security/advisories/GHSA-rhjf-q2qw-rvx3) | `aggregate_small_cohort_release` | release / unsafe_release | Cached field-filter values from one sandboxed user were served to another sandboxed user -- reconstructed as the release-layer outcome (a value disclosed across a boundary at the output stage), without reproducing the caching layer itself. |
| superset-cve-2025-48912-rls-sqli | [GHSA-8w7f-8pr9-xgwj](https://github.com/advisories/GHSA-8w7f-8pr9-xgwj) | `compiler_drops_tenant_predicate` | compiler / lowering_violation (containment: database) | An injected sub-query neutralizes the intended RLS `sqlExpression` predicate during compilation; the effect -- the restricting predicate is absent from the executed query -- is exactly what "compiler drops the tenant predicate" represents, independent of the injection mechanism. |
| hasura-cve-2022-46792-updatemany-rowauth | [CVE-2022-46792 (MITRE)](https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2022-46792) | `app_deny_missing_db_policy` | database / over_permissive | The row-permission predicate enforced on ordinary mutations was not applied on the `update_many` path -- a permission rule that exists in policy but was never propagated/enforced on this specific operation path. |
| langchain-cve-2024-8309-graphcypherqachain | [GHSA-45pg-36p6-83v9](https://github.com/advisories/GHSA-45pg-36p6-83v9) | `compiler_drops_tenant_predicate` | compiler / lowering_violation (containment: database) | The advisory explicitly lists cross-tenant data access as a confirmed outcome of the injection; reconstructed as the tenant-scope predicate being dropped from the executed query, the same visibility consequence as the Superset RLS-SQLi fixture above, without reproducing prompt-injection or LLM-chain internals. |

Three operators are reused across multiple fault IDs above (`db_rls_old_ownership_field` x3,
`app_deny_missing_db_policy` x3, `compiler_drops_tenant_predicate` x3). This is intentional:
PolicyStrata's 21-operator taxonomy is coarser than the space of real incidents, so several
distinct real faults legitimately reduce to the same generic drift shape (a database policy that
no longer restricts what it claims to; a compiled predicate that is absent). Reuse is not evidence
that the detector distinguishes between the underlying mechanisms -- see "What this suite does not
claim" below.

## Dropped faults (6) -- not reconstructed

| Fault ID | Reason not reconstructed |
|---|---|
| clickhouse-issue-12373-first-policy-hides-all | The fault's direction is over-restrictive: creating a permissive policy for one user causes every *other* unpolicied user to see zero rows, not more rows. PolicyStrata's 22 operators are all `over_permissive`, `lowering_violation`, `semantic_drift`, or `unsafe_release` -- none produce an `over_restrictive` witness. Forcing this onto a permissive-direction operator would invert what the incident actually did, which the task instructions explicitly rule out. |
| dbt-core-issue-6238-incremental-revokes-grants | Same reason as above: the documented direction is under-grant (an incremental run leaves narrower privileges than the manifest/DEFAULT PRIVILEGES config intends), which is over-restrictive from the querying principal's perspective, not a leak. No under-grant/over-restrictive operator exists in the taxonomy. (The source itself notes the inverse, over-granting, pattern is also possible, but that is not the documented incident.) |
| vanna-cve-2024-5565-text2sql-rce | The fault is arbitrary Python code execution via `exec()` on LLM-generated Plotly code, triggered by prompt injection. It has no row/column-visibility shape at all -- there is no query whose result set is over- or under-exposed. PolicyStrata's simulator models metric/dimension/tenant authorization and compiled-SQL predicate correctness, not arbitrary code execution; nothing in the operator taxonomy represents RCE. |
| langchain-cve-2023-36189-sqldatabasechain | The fault is unchecked execution of LLM-generated SQL, demonstrated with a destructive statement ("Drop Employee table"). This is an integrity/availability fault (data/schema destruction), not a row-visibility fault; no operator represents a compiled statement's type changing from a scoped SELECT to an arbitrary/destructive statement. |
| pandasai-cve-2024-12366-prompt-injection | Same class as vanna-cve-2024-5565: prompt injection driving `exec()` of attacker-controlled Python/SQL, an RCE fault outside the row/column-visibility model this suite reconstructs. |
| cube-issue-9024-preagg-crosstenant-params | Marked `reconstructable: partial` in the source ledger, and its own verification note is explicit that the confirmed outcome is a query type-mismatch error ("invalid input syntax for type timestamp"), not a confirmed unauthorized read -- "unauthorized-read outcome not confirmed" per the source. Rather than reconstruct an unconfirmed outcome as a definite detector kill, this fault was excluded from the task suite. (Contrast with langchain-cve-2024-8309 above, whose advisory explicitly lists cross-tenant data access as a confirmed outcome, which is why that one was kept.) |

## What this suite does not claim

- **No new operator was authored.** Every task uses one of the 21 existing mutation operators in
  `src/policystrata/mutations.py`, unmodified. Where a real fault's precise mechanism (planner
  statistics, plan-cache role reuse, view SECURITY DEFINER semantics, a caching layer, prompt
  injection into an LLM chain, SQL injection into an RLS expression) isn't representable by any
  existing operator, this suite reconstructs the operator's *own* generic drift shape that best
  matches the fault's *documented resulting visibility drift* -- not the trigger mechanism itself.
  The `db_result` numeric deltas in `src/policystrata/runner.py::simulate_db_result` are synthetic
  per-operator constants; they are not derived from replaying the actual vulnerable code path of
  Postgres, ClickHouse, Cube, Supabase, Looker, dbt, Metabase, Superset, Hasura, or LangChain.
- **"Recall" here is narrow.** It means: given a task whose mutation was chosen to honestly reflect
  a real fault's documented `layer_mapping`/`drift_shape`, does PolicyStrata's detector classify and
  localize it correctly? It does **not** mean PolicyStrata would have caught the original incident
  in production, and it does not estimate recall over unknown/future faults. See
  `docs/incident-reconstruction-results.md` for how this is kept separate from the synthetic-mutant
  suites' kill numbers.
- **Reused operators are not independent evidence.** The 19 tasks exercise 12 distinct operators
  (of 21 available); 3 operators are each responsible for 3 of the 19 tasks. A single operator
  passing on three differently-cited faults is one behavior being checked three ways, not three
  independently-verified detection capabilities.
- **The Looker fixture narrows a broader source.** `looker-access-filter-pitfalls` cites a
  reference doc describing three distinct pitfalls; only the "missing `access_filter`" sub-case is
  reconstructed as a task. The wildcard-value workaround and the SQL Runner bypass are mentioned in
  the citation but not independently modeled.

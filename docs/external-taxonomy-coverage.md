# External Fault-Taxonomy Coverage

PolicyStrata's 22 mutation operators were authored alongside its detector, so their
coverage of the 1720-case benchmark measures internal consistency only. This study
measures the registry against a fault vocabulary nobody on this project wrote: the
eight data-agent vulnerabilities (V1-V8) of Wang et al., *Data Agents Under Attack*
(arXiv:2606.08661), derived from a systematic audit and evaluated on six data agents
including two production cloud analytics services.

The operator-to-vulnerability mapping is a human judgement, recorded in
`scripts/external-taxonomy-study.py` so it can be argued with. Case counts are derived
from the materialized traces of `scripts/reproduce-final.sh`.

## Result

- 2 of 8 external vulnerability classes are covered by the v1 model, 1 partially, and 5 fall outside it.
- 1319 of 1720 benchmark cases instantiate a drift shape the external taxonomy also names.
- 401 cases have no counterpart there, for a reason given below.

Every class that falls outside does so because of a v1 scope boundary the paper already
declares -- single-request, read-only, starting after intent formation, stateless release.
That is the useful reading of this table: the exclusions are the declared scope, not gaps
discovered after the fact.

## Coverage by external vulnerability

| Ext. | Layer | Vulnerability | v1 coverage | Operators | Cases |
| --- | --- | --- | --- | ---: | ---: |
| V1 | interpretation | Implicit Trust Bias | outside | 0 | 0 |
| V2 | interpretation | Lack of Data Source Verification | outside | 0 | 0 |
| V3 | execution | Uncontrolled Query Cost | covered | 1 | 104 |
| V4 | execution | Cross-Engine Semantic Inconsistency | partial | 8 | 613 |
| V5 | execution | Unbounded Multi-Step Query Chains | outside | 0 | 0 |
| V6 | policy | Security Policy Forgetting under Context Pressure | outside | 0 | 0 |
| V7 | policy | Over-Privileged Database Connection | covered | 8 | 602 |
| V8 | policy | Lack of Compositional Leakage Control | outside | 0 | 0 |

## Why each class lands where it does

**V1 Implicit Trust Bias — outside.** v1 begins at a typed semantic plan. It models no conflict between data assets and no precedence rule for resolving one.

**V2 Lack of Data Source Verification — outside.** v1 treats database rows as trusted state, not as a channel that can carry instructions, so database-resident prompt injection is unmodelled.

**V3 Uncontrolled Query Cost — covered.** The canonical policy declares per-role row and cost bounds and the compiler contract checks the lowered query against them. v1 checks a declared static estimate, not measured runtime resource consumption.

Operators: `cost_estimate_ignores_expansion`.

**V4 Cross-Engine Semantic Inconsistency — partial.** The semantic oracle compares a reference interpreter against the lowered query under declared NULL, timezone, and tolerance rules, and two operators are date-semantics divergence exactly. v1 models one execution engine, so it finds reference-versus-SQL divergence and not SQL-versus-Python divergence.

Operators: `compiler_inner_join_drops_rows`, `compiler_removes_distinct`, `fanout_join_drift`, `fiscal_calendar_mismatch`, `gross_net_metric_drift`, `materialized_view_lineage_drop`, `timezone_bucket_drift`, `uniq_to_count_drift`.

**V5 Unbounded Multi-Step Query Chains — outside.** v1 scores single-request, read-only analytics and has no multi-step budget.

**V6 Security Policy Forgetting under Context Pressure — outside.** This is a property of the model context. v1's manifest operators model stale exposure, which is a deployed artifact being out of date, not policy being evicted from a context window at runtime.

**V7 Over-Privileged Database Connection — covered.** The largest overlap. Every operator here is principal or tenant identity failing to survive a transition, or a runtime role carrying more privilege than the policy assumed.

Operators: `app_deny_missing_db_policy`, `clickhouse_row_policy_missing_project_filter`, `clickhouse_row_policy_readonly_assumption_violation`, `compiler_drops_tenant_predicate`, `compiler_swaps_tenant_account_id`, `compiler_uses_old_tenant_key`, `db_rls_old_ownership_field`, `distributed_table_policy_gap`.

**V8 Lack of Compositional Leakage Control — outside.** v1 release is stateless and single-query by declaration. It checks a per-query cohort threshold and sampling disclosure, but tracks no cumulative disclosure across a session, which is what V8 names.

## Cases with no external counterpart

401 cases across 5 operators: `aggregate_small_cohort_release`, `grammar_permits_forbidden_dimension`, `sample_clause_release_drift`, `stale_metric_alias_manifest`, `validator_omits_sensitive_column`.

The external study fixes an adversary who controls only the user prompt and uploaded data, and treats the policy set as given. These operators model an update desynchronizing a surface with no adversary present: a retired alias still advertised to the model, a grammar still admitting a dimension policy has retired, a validator not yet updated for a newly sensitive column, and two release rules that can themselves drift. They are outside an attack taxonomy by construction, not by oversight.

This is the direction of the comparison that is easy to miss. The two taxonomies differ
in threat model, not just in scope: the external study asks what an adversary can induce,
and PolicyStrata asks what an update can break. Neither subsumes the other, and a stack
that only defends against one of them is unprotected against the other.

## Limits

- The mapping is our reading of another group's taxonomy. They did not review it.
- Agreement on a fault *shape* is not evidence that PolicyStrata would detect that fault
  in the systems where they observed it; those runs used live agents and adversarial
  prompts, and PolicyStrata scores a deterministic simulator.
- One external taxonomy is not the field distribution. It bounds our registry against a
  second opinion; it does not turn 1720/1720 into recall.

## Reproduce

```bash
scripts/reproduce-final.sh
uv run python scripts/external-taxonomy-study.py
```

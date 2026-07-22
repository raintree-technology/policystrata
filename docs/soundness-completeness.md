# Soundness and Completeness

This characterizes what the checking procedure guarantees relative to the surface
contracts, and what it does not.

## Soundness: a witness implies a contract violation

For every trace the detector produces:

    witness != CLEAN  =>  (some surface's contract was violated)
                          or (the release layer allowed an unauthorized result)

`policystrata.soundness.witness_implies_contract_violation` is that predicate.
It is checked two ways in `tests/test_soundness.py`:

- **Property-based** (Hypothesis, 400 examples): random operator x domain x
  query draws across the taxonomy, asserting the invariant on each.
- **Exhaustive**: every operator in every built-in domain over 25 seeds.

Both pass with zero counterexamples. So the detector never emits a witness
without a corresponding contract violation - no witness is spurious relative to
the contracts. The converse (every contract violation produces a witness) is
*not* claimed globally; it is characterized per fault class below.

## Completeness, characterized per fault class

Completeness is stated per witness class rather than as a global claim, because
the guarantee is "faults expressible as one of these operators are localized to
their declared surface," not "all conceivable drift is caught."

| Witness class | Surfaces it localizes to | Operators |
| --- | --- | --- |
| lowering_violation | compiler | 3 |
| over_permissive | compiler, database, grammar, manifest, validator | 9 |
| semantic_drift | compiler | 8 |
| unsafe_release | release | 2 |

Full operator -> contract mapping:

| Operator | Surface | Witness class | Containment |
| --- | --- | --- | --- |
| aggregate_small_cohort_release | release | unsafe_release | — |
| app_deny_missing_db_policy | database | over_permissive | — |
| clickhouse_row_policy_missing_project_filter | database | over_permissive | — |
| clickhouse_row_policy_readonly_assumption_violation | database | over_permissive | — |
| compiler_drops_tenant_predicate | compiler | lowering_violation | database |
| compiler_inner_join_drops_rows | compiler | semantic_drift | — |
| compiler_removes_distinct | compiler | semantic_drift | — |
| compiler_swaps_tenant_account_id | compiler | lowering_violation | database |
| compiler_uses_old_tenant_key | compiler | lowering_violation | database |
| cost_estimate_ignores_expansion | compiler | over_permissive | — |
| db_rls_old_ownership_field | database | over_permissive | — |
| distributed_table_policy_gap | database | over_permissive | — |
| fanout_join_drift | compiler | semantic_drift | — |
| fiscal_calendar_mismatch | compiler | semantic_drift | — |
| grammar_permits_forbidden_dimension | grammar | over_permissive | — |
| gross_net_metric_drift | compiler | semantic_drift | — |
| materialized_view_lineage_drop | compiler | semantic_drift | — |
| sample_clause_release_drift | release | unsafe_release | — |
| stale_metric_alias_manifest | manifest | over_permissive | — |
| timezone_bucket_drift | compiler | semantic_drift | — |
| uniq_to_count_drift | compiler | semantic_drift | — |
| validator_omits_sensitive_column | validator | over_permissive | — |

Regenerate these tables from the taxonomy with
`policystrata.soundness.completeness_by_class` and `operator_contract_map`.

## Scope and limits

- Soundness is relative to the surface contracts *as modeled here*, checked over
  the deterministic simulator - not a mechanized proof over an independent
  formalization. Mechanizing the contracts (Lean/Coq) would strengthen this from
  an exhaustively-checked property to a proof; that is future work.
- Completeness is per-operator: a fault that no operator expresses (e.g. a novel
  same-surface interaction, or drift outside the six modeled surfaces) is outside
  the characterized guarantee. This is the same taxonomy-boundary caveat the
  evidence snapshot states for the kill-rate numbers.

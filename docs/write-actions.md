# Write Actions (v2 dimension)

The read pipeline covers SELECT-shaped requests. This extends the same
responsibility-scoped, first-transition machinery to write actions
(INSERT / UPDATE / DELETE), where the failure modes and containment differ.

```bash
uv run python scripts/write-study.py
```

## Write surfaces and containment

The write pipeline is `manifest -> grammar -> validator -> compiler -> database
-> commit` (a `commit` layer replaces the read pipeline's `release`). Containment
mirrors the read model: a compiler-level tenant-scope drop is *contained* when
the database write policy's `WITH CHECK` rejects the offending rows - the fault
is localized to the compiler, but the write never commits.

## Operators and results

Eight write operators, each localizing to its surface with its own witness class:

| Operator | Surface | Witness class | Contained by DB | Commits |
| --- | --- | --- | --- | --- |
| manifest_exposes_retired_writable_alias | manifest | over_permissive_write | no | yes |
| grammar_permits_write_to_readonly_table | grammar | over_permissive_write | no | yes |
| validator_permits_forbidden_write_column | validator | column_policy_violation | no | yes |
| update_drops_tenant_predicate | compiler | unscoped_write | yes | no |
| delete_missing_tenant_scope | compiler | unscoped_write | yes | no |
| insert_forges_tenant_id | compiler | forged_tenant_write | yes | no |
| db_write_policy_missing_with_check | database | over_permissive_write | no | yes |
| commit_releases_uncontained_write | commit | unsafe_commit | no | yes |

Study over 48 mutants + 40 clean write controls:

- killed 48 / 48, false positives 0 / 40
- localization accuracy 1.00
- containment rate 0.375 (the three compiler tenant-scope drops are caught by
  the database write policy; the other five are not, because the skew is at or
  after the containment layer)
- uncontained commits: the writes that actually escape are exactly the ones
  whose skew is at the database or commit layer, or upstream of tenant scope
  (manifest/grammar/validator over-permissive writes)

The same defense-in-depth-gap logic carries over: a database `WITH CHECK` policy
contains the compiler's tenant-scope drops but does nothing for a manifest that
exposes a retired writable alias or a validator that permits a forbidden column -
those commit, and only a responsibility-scoped check localizes them.

## Scope

This is the single v2 dimension implemented with real semantics, not a stub, and
it is deliberately self-contained: its own witness classes, surfaces, operators,
simulator, and first-transition detector, with the read pipeline untouched. It is
a compact model of write containment - no multi-statement transactions, triggers,
or cross-row aggregation effects - which are the natural next steps. The other v2
dimensions the review listed (multi-query aggregation privacy, history-aware
release) are intentionally left for later rather than added shallowly.

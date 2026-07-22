# Brownfield target: cube-js/cube -- intentionally-broken ACL fixtures

Source: shallow clone (`--depth 1`) of `cube-js/cube` at
`/private/tmp/claude-501/-Users-mb1-Code-raintree-oss-policystrata/3e286431-07a6-4558-8ba2-1af21b7c3c90/scratchpad/brownfield/cube`.
Static inspection only; no cube code was executed. All content below was produced by
`scripts/brownfield-transform-cube.py` (stdlib + PyYAML only) reading that clone.

Run:

```bash
uv run python examples/brownfield/cube/scripts/brownfield-transform-cube.py \
  --source <path-to-cube-clone> \
  --out examples/brownfield/cube
uv run policystrata scan --config examples/brownfield/cube/policystrata.yaml \
  --out runs/brownfield-cube
uv run policystrata scan --config examples/brownfield/cube/policystrata_clean.yaml \
  --out runs/brownfield-cube-clean
```

Results: `policystrata.yaml` -> **exit 1**, 2 findings, both true positives (see below).
`policystrata_clean.yaml` -> **exit 1**, 1 finding, a known scanner limitation, not a cube issue
(see below). Neither is a config error.

## The three fixtures

`packages/cubejs-schema-compiler/test/unit/fixtures/` ships three fixtures that define the
*identical* `orders` cube (same `dimensions`, `measures`, `joins`) and differ only in the
`admin` group's `accessPolicy[].rowLevel.filters[0].member`:

| Fixture | `filters[0].member` | cube's own compiler verdict (from `schema.test.ts`, quoted not executed) |
| --- | --- | --- |
| `orders_big.yml` | `status` | Valid -- `status` is a real dimension declared on `orders` itself. |
| `orders_incorrect_acl.yml` | `{CUBE}.order_users.name` | **Rejected at build time.** `order_users` is a joined cube (real fixture, `order_users.yml`, and it genuinely has a `name` dimension) -- but cube's compiler explicitly disallows cross-cube *paths* in `accessPolicy` filter members. Test: *"throw errors for incorrect policy members with paths"* asserts the thrown message contains `"Paths aren't allowed in the accessPolicy policy but 'order_users.name' provided as a filter member reference for orders"`. |
| `orders_nonexist_acl.yml` | `{CUBE}.other.path.created_at` | **Rejected at build time.** `other` is not a cube or member at all. Test: *"throw errors for nonexistent policy members with paths"* asserts `"orders.other cannot be resolved. There's no such member or cube"`. |

Both broken fixtures are cube's own negative-path test fixtures -- cube already knows about and
tests that its compiler rejects them. This target is **not** a new discovery about cube; it is a
demonstration that PolicyStrata's independent SQL-trace layer would *also* catch the same defect
class (an unresolvable row-level predicate reference), which matters as a defense-in-depth
argument, not as a cube bug report.

## What is native, transformed, and synthesized

| Artifact | Status | Detail |
| --- | --- | --- |
| `semantic_models.yml` | **Native, mapped** | Built only from `orders_big.yml` (the one fixture cube actually accepts). `dimensions[].name`/`type`, `measures[].name`, and the `sql_table` field are copied verbatim from the cube YAML; cube's `type: count` measure vocabulary is mapped to dbt's `agg: count` vocabulary (`CUBE_MEASURE_TYPE_TO_AGG`), cube's `type: time` dimension is mapped to dbt's `type: time` (everything else defaults to dbt's `categorical`), and `model: ref('orders')` is synthesized from the real `sql_table: orders` field. |
| `domain/policy.yaml` `dimensions{}` | **Native names, synthesized permissions** | Keys (`id`, `user_id`, `status`, `created_at`, `completed_at`) are cube's own dimension names. `allowed_roles`/`sensitive`/`cost` are invented -- cube's `memberLevel.includes: [status]` concept (which dimensions a group may see in *output*) has no PolicyStrata field to map to cleanly, so we did not attempt to encode it; both synthetic roles are simply granted the one dimension (`status`) our synthesized traces actually request. |
| `domain/policy.yaml` `metrics.count` | **Native name, derived expression** | `expression: count(id)` is templated from the real `measures[0].sql: id` / `type: count` fields, the same `f"{agg}({expr})"` convention used for the metricflow target. |
| `tenancy.canonical_predicates` (`policystrata.yaml`) | **Mechanically derived from real filter metadata** | `"orders.status = 'completed'"` is composed from `orders_big.yml`'s actual, resolved `filters[0]` (`member: status`, `operator: equals`, `values: [completed]`) via a literal `column = 'value'` rendering for the `equals` operator. Nothing invented beyond that rendering; see `resolve_filter_member`/`primary_filter_predicate` in the transform script, and `transform_report.json`'s `canonical_row_level_predicate` field. The nested `or:`/`and:` date-range sub-filters that follow `filters[0]` in all three fixtures are identical noise and were deliberately not translated (documented in the script's docstring). |
| `traces.jsonl` `cube_admin_query__correct` | **SQL composed from real, resolved filter metadata** | `select count(id) as count, status from orders where orders.status = 'completed' group by status` -- the `WHERE` clause is the derived predicate above; this is what a correctly-scoped admin query against `orders_big.yml`'s policy should look like. |
| `traces.jsonl` `cube_admin_query__incorrect_acl` / `__nonexist_acl` | **Fully synthesized, explicitly labeled as such** | Identical query with the `WHERE` clause omitted, representing what PolicyStrata's tenant-scope check must catch *if* the config's unresolvable row-level predicate were ever silently unenforced rather than raising cube's real, confirmed compile-time error. Each trace's `expected_policy.note` field states in full that this is a synthesized regression case, not observed cube output, and cites the exact confirmed compiler error it stands in for. **This is the one part of this target's SQL that is invented rather than transformed** -- everything else in this table is native data reshaped, not new data. |
| `traces_clean.jsonl` `cube_common_query__correct` | **Synthesized, no predicate expected** | `orders_big.yml`'s `common` group is `rowLevel: {allowAll: true}` -- a real, native fact -- so no filter predicate is composed for it; the query is a generic unfiltered `orders` read. |
| `domain/surfaces.yaml` | **Boilerplate, reused verbatim** | Copied unmodified from `src/policystrata/domains/support_saas/surfaces.yaml` (generic scanner plumbing, not target-specific). |

## Findings, classified

### (a)-adjacent true positive, demonstration not discovery -- 2x `tenant_scope_missing` (HIGH/HIGH, `policystrata.yaml`)

`cube_admin_query__incorrect_acl` and `cube_admin_query__nonexist_acl` both fail the tenant/
row-level-scope check, exactly as intended: **2 of 2 broken-ACL fixtures caught, 0 of 1 correct
fixture flagged, in the same scan.** This validates that PolicyStrata's SQL-trace layer, given an
honestly-derived canonical predicate, distinguishes the one cube configuration that actually
enforces its intended row restriction from the two cube's own compiler already rejects. We
classify this as "(a)-adjacent" rather than a clean (a): it is not a *new* real issue in cube
(cube already fails closed on both fixtures today, confirmed by its own passing test suite), so
there is nothing to file upstream. Its value is as a validated true-positive detection capability
demo using known-bad fixtures, which is exactly what this brownfield pass asked for.

### (c) Scanner limitation -- 1x `tenant_scope_missing` (HIGH/HIGH, `policystrata_clean.yaml`)

`cube_common_query__correct` fails the same check for an unrelated reason: `policystrata_clean.yaml`
declares no `tenancy` block (correctly -- the `common` group's `allowAll: true` genuinely has no
row-level predicate to declare), so `tenant_columns_for_scope_check` falls back to
`compiler.py::tenant_column("brownfield_cube")` = the hardcoded built-in-domain default
`"accounts.tenant_id"`, a column name that has nothing to do with cube's `orders` schema. This is
the **same scanner gap already documented in `examples/brownfield/metricflow/README.md`**
(custom `domain_path` domains silently inherit an irrelevant built-in tenant-column fallback
instead of erroring or skipping when tenancy is unconfigured), now independently reproduced on a
second, unrelated target. That recurrence is itself useful signal for prioritizing a scanner fix.
Not a cube issue.

### Clean signal worth naming

Within the *same* `policystrata.yaml` scan, the one real/correct fixture's trace produced **zero
findings** -- no dbt-adapter warnings (full 1:1 metric/dimension coverage since the policy was
derived from the same fixture), no static tenant-scope violation, no fuzz-survived mutants (4
mutants generated across the 3 traces were killed, 17 equivalent, 0 survived). That is the
brownfield FP-measurement result for this target: **0 false positives on the one real, correctly-
configured input, alongside 2 of 2 true positives on the known-bad inputs, in a single scan.**

## Not attempted

- The nested `or:`/`and:` date-range sub-filters in `filters[1]` (identical across all three
  fixtures) were not translated into additional predicate coverage -- out of scope, documented in
  the transform script.
- `memberLevel.includes`/`excludes` (which dimensions a group may see in output, as opposed to
  which rows) has no natural PolicyStrata field and was not modeled.
- No live PostgreSQL comparison -- cube's demo schema is not backed by committed seed data in this
  clone.

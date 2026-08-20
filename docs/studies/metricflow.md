# Brownfield study: dbt-labs/metricflow

Source: shallow clone (`--depth 1`) of `dbt-labs/metricflow` at commit
`45dce78641bbdd7e182aa57132fc11a23b24dde5`. The freeze manifest is
`benchmarks/external_source/metricflow-freeze.json`.
Static inspection only; no metricflow code was executed. All content below was produced by
`scripts/brownfield-transform-metricflow.py` (stdlib + PyYAML only) reading that clone.

Run:

```bash
uv run python examples/brownfield/metricflow/scripts/brownfield-transform-metricflow.py \
  --source <path-to-metricflow-clone> \
  --out examples/brownfield/metricflow
uv run policystrata scan --config examples/brownfield/metricflow/policystrata.yaml \
  --out runs/brownfield-metricflow
```

Current result: **exit 0**, with 72 warning-level findings and gate `warn`; no high-confidence
finding fails the gate. Earlier results in this document predated the custom-domain tenancy and
dbt-adapter fixes. The frozen rerun is authoritative for the revision and hashes named above.

## What is native, transformed, and synthesized

| Artifact | Status | Detail |
| --- | --- | --- |
| `semantic_models.yml` `semantic_models[]` | **Native**, format-merged | Every `measures`/`dimensions`/`entities`/`defaults` value is copied verbatim from metricflow's 12 `simple_manifest/semantic_models/*.yaml` files. The only addition is `model: ref('<alias>')`, synthesized from each model's real `node_relation.alias` so PolicyStrata's lineage check has something to read (metricflow's own fixtures use `node_relation`, not dbt-project `ref()` syntax). |
| `semantic_models.yml` `metrics[]` | **Native**, format-merged | Every field copied verbatim from metricflow's singular multi-doc `metric:` YAML (`simple_manifest/metrics.yaml` plus `metric:` docs embedded in a couple of semantic-model files, e.g. `user_sm_source.yaml`). Transform: metricflow's `---`-separated singular `semantic_model:`/`metric:` documents are merged into the single-document plural `semantic_models:`/`metrics:` lists PolicyStrata's dbt adapter (`src/policystrata/integrations/dbt_semantic.py`) reads. 110 metrics, 12 models. |
| `traces.jsonl` `sql` | **Native**, lightly rendered | Each trace's `sql` is metricflow's own `check_query` from `tests_metricflow/integration/test_cases/itest_*.yaml` -- real, hand-authored expected SQL from metricflow's own integration-test suite, not written by us. The only edit is substituting the `{{ source_schema }}` Jinja placeholder with the fixed literal `mf_brownfield_src`. |
| `traces.jsonl` `semantic_ir.metric` / `.dimensions` | **Native** | Copied from each selected test case's `metrics[0]` / `group_bys`. |
| `traces.jsonl` `principal`, `tenant_ids`, `time_range`, `grain`, `limit` | **Synthesized** | metricflow is a single-tenant SQL compiler with no principal, tenancy, time-range-label, or row-budget concept. Every trace uses one synthetic principal (`metricflow_query_service`), one synthetic tenant (`mf_default_tenant`), and constant `time_range`/`grain`/`limit` values. This is the "graft a tenancy concept onto a tool that doesn't have one" case called out in the inventory. |
| `domain/policy.yaml` `metrics{}` | **Auto-derived from native data** | One entry per merged dbt metric. `expression` is extracted verbatim from a real trace's `SELECT ... AS <metric>` clause when one of the selected traces uses that metric (most of the 110); otherwise templated as `f"{agg}({expr})"` from the underlying measure's real `agg`/`expr` fields. `table`/`columns` come from the same real measure metadata. |
| `domain/policy.yaml` `dimensions{}` | **Auto-derived, two sources** | (a) One entry per raw dimension name declared in `semantic_models[].dimensions[]` (native names, e.g. `is_instant`). (b) One entry per distinct group-by token observed across the selected traces (metricflow's entity-qualified query-time names, e.g. `booking__is_instant`, `user__company_name`, the bare entity name `guest`, and the pseudo-dimension `metric_time`). These are two different, non-overlapping namespaces in metricflow itself -- declared-dimension names vs. query-reference names -- both are real, but the union is a synthesis decision described below. `sensitive: true` is a heuristic (dimension name contains `email`/`name`/`ip`/`phone`/`address`/`ssn`), not sourced from metricflow. |
| `domain/policy.yaml` `principals{}` / `roles{}` | **Fully synthesized** | One principal, one role (`compiler_output`), granted every metric and every dimension with a very large `max_rows`/`max_cost`. metricflow has no role or ACL model at all, so there is nothing to derive a restrictive role from; a maximally-permissive single role is the least-fabricated choice available (see limitation notes below for what this costs the fuzz layer). |
| `domain/surfaces.yaml` | **Boilerplate, reused verbatim** | Copied unmodified from `src/policystrata/domains/support_saas/surfaces.yaml`. This is generic scanner surface-contract plumbing (five pipeline-stage descriptions), not target-specific data. |
| `tenancy:` block in `policystrata.yaml` | **Deliberately empty** | See finding classification below -- there is no honest tenant column to declare. |

## Selection and skip accounting (from `transform_report.json`)

- 19 `itest_*.yaml` files scanned, 266 `integration_test` documents total.
- 33 skipped: target a manifest other than `SIMPLE_MODEL` (`SCD_MODEL`, `EXTENDED_DATE_MODEL`,
  `PARTITIONED_MULTI_HOP_JOIN_MODEL`, `UNPARTITIONED_MULTI_HOP_JOIN_MODEL`,
  `SIMPLE_MODEL_NON_DS`) that we did not merge into `semantic_models.yml`. Out of scope for
  this pass, not attempted.
- 43 skipped: request more than one metric in a single query. PolicyStrata's `SemanticQuery` IR
  (`src/policystrata/models.py`) models exactly one `metric: str` per query, but metricflow
  natively supports multi-metric-per-query requests. There is no way to represent these traces
  without either dropping `semantic_ir` (silently disabling the authorization/metric checks for
  them) or fabricating a query metricflow never ran. We chose to skip rather than misrepresent.
  **This is a genuine scanner-IR limitation, documented as such in `docs/brownfield-results.md`.**
- 122 skipped: `check_query` uses a Jinja test-harness macro other than `{{ source_schema }}`
  (`render_time_constraint`, `render_dimension_template`, `render_date_trunc`, `render_extract`,
  `render_metric_template`, ...). These macros are defined in metricflow's test-harness code, not
  in metricflow's shipped SQL-generation code; reimplementing their semantics from scratch would
  mean inventing SQL metricflow never produced, which conflicts with the "native SQL" premise of
  this trace corpus. Skipped rather than guessed at.
- **68 traces selected** and included in `traces.jsonl`, 100% real `check_query` SQL.

## Findings, classified

The source-frozen rerun produces 72 warnings, no high-confidence failure, and gate `warn`
(exit 0). None is a MetricFlow defect: MetricFlow is a compiler with no native PolicyStrata
principal, tenancy, authorization, or release surface. The former 68
`tenant_scope_missing` failures disappeared after PolicyStrata stopped applying a built-in tenant
column to custom domains with no configured tenancy basis. The remaining warnings are synthesis
effects or correct adapter findings listed below.

### Closed adapter gap -- 15 → 0 `missing_policy_dimension`

`domain/policy.yaml` registers the entity-qualified query-time dimension tokens (e.g.
`booking__is_instant`, `user__company_name`, `metric_time`) so the 68 traces authorize cleanly.
Those tokens never appear verbatim in any semantic model's `dimensions:` list (metricflow
declares `is_instant`; queries reference it via the entity join as `booking__is_instant`).
The adapter now resolves per-model entity-qualified names, entity names, and `metric_time`, so
these 15 false warnings are gone.

### Correct adapter finding -- 3x `stale_dbt_metric` (WARNING)

The adapter now excludes private measures from the stale-name comparison. Three measures
(`archived_users`, `new_users`, and `total_account_balance_first_day_of_month`) remain because
they declare `create_metric: true`; they are governable metrics that the scoped policy does not
cover, so these warnings are correct.

### Closed adapter gap -- 2 → 0 `dbt_expression_mismatch`

`account_balance` and `booking_value` measures omit `expr:` in their native YAML (metricflow
convention: an omitted `expr` implicitly defaults to the measure's own name). PolicyStrata's
adapter now resolves the omitted expression to the measure name, so both false warnings are gone.

### (b) Synthesis artifact -- 1x `dbt_sensitive_metadata_missing` (WARNING)

`company_name` was heuristically marked `sensitive: true` by our transform script's own
name-keyword rule (`"name" in dimension_name`). The dbt YAML has no
`meta.policystrata.sensitive` annotation because metricflow doesn't know about PolicyStrata. This
finding is entirely a byproduct of our own heuristic, not a discovery about metricflow.

### (b) Synthesis artifact -- 68x `fuzz_survived_..._sensitive_dimension_added` (WARNING, property-generated)

Every fuzz mutant that adds an unrequested sensitive dimension to a trace's `semantic_ir` and
re-checks authorization "survives" (stays authorized), because the single synthetic
`compiler_output` role grants every dimension, sensitive or not. This is the direct, expected
cost of not having a real restrictive role to derive from metricflow (see table above) -- it
demonstrates the fuzz layer works correctly against real compiled SQL, not that metricflow has a
sensitive-data exposure problem.

### Clean signal worth naming

All 110 native dbt metrics now match the auto-derived policy with zero
`missing_policy_metrics` or expression mismatches, and the `sql_mentions_policy_metric` static
check passes for the 68 real traces. That is a genuine "trace-ready" capability demonstration:
PolicyStrata's SQL-trace metric-expression matching works against 100% real, unmodified
metricflow-compiler SQL when the policy's metric vocabulary is derived from the same manifest.

## Not attempted

- `SCD_MODEL`/`EXTENDED_DATE_MODEL`/multi-hop-join manifests and their itest cases (33 skipped
  test docs) -- would need merging the corresponding non-`simple_manifest` semantic YAML too.
- Live PostgreSQL comparison (`database:` block / `db-ready` stage) -- would require rendering
  `tests_metricflow/fixtures/source_table_snapshots/` into seed SQL against
  `local-data-warehouses/postgresql/docker-compose.yaml`; out of scope for this pass.
- Multi-metric traces (43 skipped) and macro-driven traces (122 skipped) -- see skip accounting
  above.

# Second External Taxonomy Cross-Check

The first external comparison uses Wang et al.'s eight data-agent vulnerabilities.
This independent second comparison uses Chu's Layered Attack Surface Model (LASM), a
7-layer by 4-timescale taxonomy derived from a survey of 116 agent-security papers
(arXiv:2604.23338). LASM asks *where and when* a failure occurs, so it tests a different
axis than the first vulnerability-name comparison.

The mapping is a PolicyStrata-author judgement recorded in
`scripts/second-taxonomy-study.py`; Chu did not review it. Counts come from the same
materialized 1720 benchmark traces as the paper.

## Result

- PolicyStrata covers 3 of 7 LASM layers: Cognitive, Tool
  Execution, and Governance.
- All 1720 cases measure an instantaneous, single-request consequence. The benchmark
  has no session-persistent, cross-session-cumulative, or sub-session-stack case.
- The cross-check therefore confirms the paper's declared boundary and exposes it more
  sharply: v1 checks contract and enforcement drift after intent formation, not model
  foundations, memory, agent coordination, or ecosystem compromise.

## Architectural layers

| LASM layer | Coverage | Operators | Cases |
| --- | --- | ---: | ---: |
| Foundation | outside | 0 | 0 |
| Cognitive | covered | 2 | 242 |
| Memory | outside | 0 | 0 |
| Tool Execution | covered | 10 | 838 |
| Multi-Agent Coordination | outside | 0 | 0 |
| Ecosystem | outside | 0 | 0 |
| Governance | covered | 10 | 640 |

## Temporal classes

| LASM temporal class | Coverage | Cases |
| --- | --- | ---: |
| instantaneous | covered | 1720 |
| session-persistent | outside | 0 |
| cross-session cumulative | outside | 0 |
| sub-session-stack | outside | 0 |

A deployed drift can remain present across sessions, but the v1 benchmark does not model
state accumulation or propagation: each case scores one request from a fixed faulty
state. Calling those cases cross-session would overstate what was executed.

## Operator mapping

**Cognitive.** `grammar_permits_forbidden_dimension`, `stale_metric_alias_manifest`.

**Tool Execution.** `compiler_inner_join_drops_rows`, `compiler_removes_distinct`, `cost_estimate_ignores_expansion`, `fanout_join_drift`, `fiscal_calendar_mismatch`, `gross_net_metric_drift`, `materialized_view_lineage_drop`, `timezone_bucket_drift`, `uniq_to_count_drift`, `validator_omits_sensitive_column`.

**Governance.** `aggregate_small_cohort_release`, `app_deny_missing_db_policy`, `clickhouse_row_policy_missing_project_filter`, `clickhouse_row_policy_readonly_assumption_violation`, `compiler_drops_tenant_predicate`, `compiler_swaps_tenant_account_id`, `compiler_uses_old_tenant_key`, `db_rls_old_ownership_field`, `distributed_table_policy_gap`, `sample_clause_release_drift`.

## Limits

- LASM is a broad agent-security survey taxonomy, not a data-agent fault distribution.
- Layer agreement is structural overlap, not evidence of production recall.
- The mapping has not been reviewed by the LASM author.

## Reproduce

```bash
scripts/reproduce-final.sh
uv run python scripts/second-taxonomy-study.py
```

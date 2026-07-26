# Brownfield Scan Results: External Data-Agent Stacks

First real brownfield scan of `policystrata scan` against external, independently-maintained
open-source data-agent / semantic-layer / multi-tenant-SaaS stacks, run from shallow clones
(`--depth 1`, static inspection only, nothing executed) against four targets:
[dbt-labs/metricflow](#metricflow), [midday-ai/midday](#midday), [Canner/WrenAI](#wrenai), and
[cube-js/cube](#cube) (bonus target, intentionally-broken ACL fixtures). All four ran `policystrata
scan` to completion. Full detail, including exact source citations for every transformed or
synthesized value, lives in each target's own `examples/brownfield/<repo>/README.md`; this
document summarizes and cross-references.

## Method

1. Read `src/policystrata/scan_models.py` (`ScanConfig`, `ImportedTrace`), `docs/scanner.md`,
   `src/policystrata/trace_import.py`, `src/policystrata/integrations/dbt_semantic.py`, and
   `examples/postgres_dbt/*.yaml` to establish the scanner's actual input contract and finding
   taxonomy before touching any target repo.
2. For each target, built `examples/brownfield/<repo>/` containing: a `policystrata.yaml` scan
   config; where a mechanical, deterministic transform was possible, a
   `scripts/brownfield-transform-<repo>.py` (stdlib + PyYAML only, never executes code from the
   cloned repo, ruff-clean); the transformed/synthesized inputs it produces (`semantic_models.yml`,
   `domain/policy.yaml`, `traces.jsonl`, `schema.sql`); and a `README.md` with a field-by-field
   table stating exactly what is **native** (copied from the real repo unmodified), **transformed**
   (mechanically reshaped real data, e.g. YAML doc-merging or an MDL→dbt field mapping), or
   **synthesized** (invented because the target has no equivalent concept, e.g. principals for a
   single-tenant SQL compiler) -- every synthesized value is labeled as such at the point it is
   used, not just in a caveats section.
3. Ran `uv run policystrata scan --config examples/brownfield/<repo>/policystrata.yaml --out
   runs/brownfield-<repo>` for each target and iterated on the config/transform until it reached a
   real exit 0 or a legitimate findings-based exit 1 (never a config/parse error). MetricFlow's
   source-frozen rerun exits 0 with warnings after the custom-domain tenancy fix; the other
   recorded scans exit 1 for the target-specific reasons below.
4. Classified every finding as **(a)** a real, newly-discovered potential upstream issue in the
   scanned repo, **(b)** an artifact of the synthesis/transform bridge (not a discovery about the
   target), or **(c)** a PolicyStrata scanner/adapter limitation. See "Scanner gaps" below for the
   (c) findings, several of which recurred across independent targets.

No file under `src/policystrata/**` was modified. No commits were made. No network access beyond
the pre-existing shallow clones. No new Python dependencies.

## Summary table

| Repo | dbt/semantic input | SQL traces | Tenancy signal | `scan` exit | Total findings | Gate-failing (HIGH/HIGH+) | Warnings | Class (a) | Class (b) | Class (c) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [metricflow](#metricflow) | 12 models / 110 metrics, native+merged | 68, 100% native `check_query` SQL | synthesized (compiler has none) | 0 | 95 | 0 | 95 | 0 | 3 finding-families | 2 finding-families |
| [midday](#midday) | none (no semantic layer) | 5, hand-transcribed from cited real TS | native RLS column (`team_id`) | 1 | 2 | 1 | 1 | 0 | 0 | 2 |
| [WrenAI](#wrenai) | 3 models, native+mapped | 2 (1 native-condition, 1 labeled hypothetical) | mechanically rendered from real MDL RLAC condition | 1 | 11 | 1 | 10 | 0 | 0 | 1 (recurs, see below) |
| [cube](#cube) *(bonus)* | 1 model, native+mapped | 3 main + 1 clean-config | mechanically rendered from real accessPolicy filter | 1 (both configs) | 2 main / 1 clean | 2 main / 1 clean | 0 | 0 | 0 | 1 (recurs, see below) |

**Zero class-(a) findings across all four targets.** See "Draft upstream issues" below for why,
and "Scanner gaps" for what the class-(c) findings are (several are the *same* gap recurring on
independent targets, which is itself the most useful signal from this pass).

## Per-repo detail

### metricflow

`examples/brownfield/metricflow/` -- `dbt-labs/metricflow`. Full detail:
`examples/brownfield/metricflow/README.md`.

The merge transform the inventory anticipated (metricflow's multi-doc singular `semantic_model:`
YAML → PolicyStrata's plural `semantic_models:` list) was implemented and works cleanly: 12
semantic models and 110 metrics merged, native field values throughout. 68 of 266 real
`tests_metricflow/integration/test_cases/itest_*.yaml` cases were selected as traces (single-metric,
`SIMPLE_MODEL`-targeted, renderable without reimplementing test-harness-only Jinja macros); every
trace's `sql` is metricflow's own, real, hand-authored `check_query` text. The source-frozen rerun
uses upstream commit `45dce78641bbdd7e182aa57132fc11a23b24dde5`; the transformed input hashes
are recorded in `benchmarks/external_source/metricflow-freeze.json`. All 68 traces authorize
against a policy derived from the same manifest. The scan emits 95 non-gating warnings from the
synthetic bridge role and remaining adapter gaps, including two dbt measures that omit `expr:`
under MetricFlow's implicit-default convention.

### midday

`examples/brownfield/midday/` -- `midday-ai/midday`. Full detail:
`examples/brownfield/midday/README.md`.

The only target with real, committed Postgres RLS SQL (`packages/db/migrations/*.sql`, 20
`CREATE POLICY` statements) and a real tenant-column vocabulary (`team_id`). `schema.sql` is a
mechanical, ordered concatenation of all 39 migrations (script-produced). Traces are hand-
transcribed (not script-generated -- no TypeScript parser in scope) from 5 real, cited
`packages/db/src/queries/*.ts` functions across two tables, each trace citing both its source
function/line range and the exact native `CREATE POLICY` statement that protects the table it
queries. 4 of 5 traces (real, team-scoped, explicit `team_id` filters) produced zero findings. The
5th (`insight_user_status`, genuinely and correctly scoped by a *different* real RLS policy,
`user_id = auth.uid()`) was flagged -- a real, narrowly-scoped scanner limitation, not a midday
defect (see Scanner gaps). The `database.schema` block is wired in (`required: false`) and
produces exactly the expected non-gating "fixture unavailable" warning, since no live Postgres was
started for this pass.

### WrenAI

`examples/brownfield/WrenAI/` -- `Canner/WrenAI`. Full detail:
`examples/brownfield/WrenAI/README.md`.

Smallest-scope target. Built from one real MDL JSON fixture
(`core/wren-core-base/tests/data/mdl.json`), scoped to the one model (`customer`) and one rule
(`rule1`, `requiredProperties: [{session_id, required: true}]`, `condition: "c_custkey =
@session_id"`) with an unambiguous required-session-property semantic. The MDL→dbt mapping and the
`@session_property`→`:principal.tenant_id` predicate rendering are both mechanical, 1:1, and cited.
One real-condition-consistent trace and one explicitly-labeled hypothetical "what if this required
rule were silently bypassed" trace were built; the scan cleanly separates them (0 findings on the
first, 1 gate-failing finding on the second). 10 non-gating WARNINGs are expected fallout of
scoping the policy to just the RLAC-relevant model rather than all three models in the fixture.

### cube (bonus)

`examples/brownfield/cube/` -- `cube-js/cube`. Full detail: `examples/brownfield/cube/README.md`.

The requested bonus target: `orders_incorrect_acl.yml` and `orders_nonexist_acl.yml`, two of
cube's own schema-compiler unit-test fixtures for *intentionally invalid* `accessPolicy` row-level
filter member references. cube's own test suite (`packages/cubejs-schema-compiler/test/unit/
schema.test.ts`, read and quoted, not executed) confirms cube's compiler rejects both at build
time with two different, specific error messages. This script re-derives the same
member-resolution verdict cube's compiler reaches (a small, deterministic path-check against the
cube's own declared members and joins) and renders the one real, valid fixture's
(`orders_big.yml`) row-level filter into a literal SQL predicate. In a single scan: the real/valid
fixture's trace produces zero findings, and both broken fixtures are caught (2 of 2), each clearly
labeled as a synthesized regression case demonstrating detection capability against a known-bad
input, not a claim about observed cube runtime output. A separate `policystrata_clean.yaml`
(cube's unrestricted `common`/`allowAll` group) reproduces the same tenant-column-fallback scanner
gap documented for metricflow and midday.

## Scanner gaps identified (class c)

Each gap is cited with the exact recommended change. Gaps 1 and 2 have since been **fixed** (see the
notes below and `tests/test_scanner_tenancy_fallback.py`); gaps 3–5 remain open.

### 1. Custom-domain tenant-column fallback is misleading (recurs on 3 of 4 targets) — FIXED

**Fixed.** `tenant_columns_for_scope_check()` no longer inherits a built-in domain's tenant column
for a custom (`domain_path`) domain: `builtin_domain_tenant_column()` returns the canonical column
only for a built-in domain with no `domain_path`, and `sql_preserves_tenant_scope()` skips the
tenant-scope check (rather than reporting a violation) when no tenancy basis is configured. After the
fix, metricflow drops from 163 to 95 findings (0 `tenant_scope_missing`, gate fail → warn) and cube's
clean config drops to 0 findings, while cube's broken fixtures are still caught (2) and the built-in
`support_saas` examples are unchanged.

The original result was 68/68 `tenant_scope_missing` findings on MetricFlow and one on Cube's
`allowAll` fixture because the scanner substituted `accounts.tenant_id`. Those historical counts
are retained here only to explain the fix; they are not current evaluation results.

### 2. Tenancy config is one global column list, no per-table/per-trace override — FIXED

**Fixed.** `TenancyScanConfig` gained a `table_tenant_columns` map (table name → columns); a trace
whose primary table (from `primary_table_from_sql()`) matches uses those columns instead of the
global `tenant_columns`. This lets midday declare `team_id` globally and `user_id` for
`insight_user_status`. Original report follows.

### 2. Tenancy config is one global column list, no per-table/per-trace override

`midday`'s real schema genuinely uses two different real RLS dimensions across tables (`team_id`
for most tables, `user_id` for a few, e.g. `insight_user_status`). `tenancy.tenant_columns` has no
way to declare "table X uses column Y," so a config correctly scoped for the dominant pattern
necessarily misjudges the minority one. See `examples/brownfield/midday/README.md`'s finding
detail for the concrete example and recommended fix (per-table/per-trace tenancy declarations).

### 3. dbt adapter does plain name-string matching with no entity-join resolution

metricflow declares dimensions with local names (`is_instant`) but its own query interface
references them via entity-qualified dunder names (`booking__is_instant`) that never appear
verbatim in the manifest YAML. `src/policystrata/integrations/dbt_semantic.py`'s
`inspect_dbt_semantic_model` does a flat name-set diff, so any tool with this (common, in
dbt-Semantic-Layer-style systems) declared-name vs. referenced-name split will produce this class
of warning. See `examples/brownfield/metricflow/README.md`.

### 4. `metrics ∪ measures` comparison pool conflates private measures with public metrics

Also in `dbt_semantic.py`: `dbt_metric_names` is `metrics ∪ measures`. metricflow measures marked
`create_metric: true` with no separate literal `metric:` document (relying on metricflow's own
name-equals-measure-name auto-promotion convention) land in that pool with no policy counterpart
and are flagged "stale," even though they were never meant to be individually governed the same
way as an explicit metric. See `examples/brownfield/metricflow/README.md`.

### 5. `expression_mismatches` doesn't know omitted `expr:` has an implicit default

metricflow measures may omit `expr:` (it implicitly defaults to the measure's own name). dbt
adapter's `expression_matches_policy` treats an empty `expr` string as an automatic mismatch
regardless of whether the underlying policy expression is actually correct. See
`examples/brownfield/metricflow/README.md`.

## False-positive accounting on real inputs

Across the 4 targets, **74 traces carry real (not intentionally-broken, not hypothetical-
regression) SQL content**: 68 metricflow (100% real `check_query` text), 1 cube (real, resolved
`accessPolicy` filter), 4 midday (hand-transcribed but cited line-for-line from real ORM code), 1
WrenAI (real, rendered RLAC condition).

- **1 of those 74** was flagged where the flag is arguably a false positive against that specific
  trace's actual SQL content (midday's `insight_user_status`, gap #2 above) -- ~1.4%, and fully
  attributable to one documented, narrow scanner-config limitation, not scattered noise.
- **68 of those 74** (all of metricflow's) were also flagged, but *not* because of anything wrong
  with the specific SQL -- every one fails identically, for the same structural reason (gap #1
  above), independent of trace content. We report this separately from the 1.4% figure above
  because it is not a per-trace judgment call the scanner got wrong; it is one config-fallback
  behavior applied uniformly.
- **The remaining 5 of 74** (1 cube, 4 midday, and technically metricflow's 108/110 correctly-
  matched dbt metrics) produced the clean result the scanner is supposed to produce on correct
  input.
- **105 non-gating WARNING findings** (95 metricflow + 10 WrenAI) are 100% attributable to a
  documented, deliberate scope decision (policy narrower than the full demo/fixture manifest) --
  none are scanner miscalls against real data.

A genuinely **clean** scan (0 findings) was not achieved on any target's primary config, because
gap #1 makes an all-traces-fail-identically outcome unavoidable for any target without a real
tenancy concept once traces are supplied at all -- but the *content-level* signal (does the scanner
correctly distinguish an enforced query from an unenforced one, on real SQL) is clean and correct
everywhere it was tested: cube (2/2 broken caught, 0/1 correct flagged), WrenAI (1/1 hypothetical
bypass caught, 0/1 real-consistent flagged), and midday (0/4 real team-scoped traces flagged).

## Draft upstream issues

**None.** No class-(a) finding (a real, newly-discovered potential issue in a scanned repo) came
out of this pass:

- metricflow, midday, and WrenAI: every finding traces to a synthesis-bridge artifact or a
  PolicyStrata scanner/adapter limitation (classes b/c above), not a defect in the scanned project.
- cube: the two "true positive" findings are cube's own, already-known, already-tested-for
  intentionally-broken fixtures (`schema.test.ts` already asserts cube's compiler rejects both).
  There is nothing new to report to cube -- the value of this target is demonstrating that
  PolicyStrata's independent SQL-trace layer *would also* catch the same defect class as a
  defense-in-depth layer, not discovering a new bug.

This is reported per this task's own instruction: "A clean scan on real inputs is a valid result
... do not inflate." Inventing a class-(a) finding to have something to draft would be exactly the
inflation this pass was asked to avoid.

## Honest limitations / not attempted

- **vanna** (ranked weakest target in the inventory: no semantic models, no SQL fixtures, no
  schema, no tenancy vocabulary -- "almost everything must be authored from scratch") was not
  attempted in this pass, consistent with the task's priority order and budget guidance.
- No live PostgreSQL comparison (`database.rls_checks`/`state_assertions`/real-DB semantic-drift
  detection) was run for any target. midday's `schema.sql` is produced and wired into its config
  (`required: false`) specifically so this is honestly represented as "not exercised" rather than
  silently absent, but standing up a seeded Postgres fixture for any target was out of this pass's
  scope.
- metricflow: `SCD_MODEL`/`EXTENDED_DATE_MODEL`/multi-hop-join manifests (33 of 266 itest cases),
  multi-metric traces (43 cases -- PolicyStrata's `SemanticQuery` IR models exactly one metric per
  query, which metricflow's real multi-metric-per-query capability can't be represented in without
  either dropping `semantic_ir` or fabricating a query metricflow never ran; documented, not
  attempted), and macro-driven traces (122 cases, would require reimplementing metricflow
  test-harness-only Jinja macros) were all skipped by explicit, logged design, not by omission.
- WrenAI: only 1 of 3 `customer` RLAC rules was modeled (the unambiguous `required: true` one);
  the two `required: false` rules were skipped because their exact absent-property behavior was
  not confidently known without reading wren-core's Rust planner more deeply than this pass's
  budget allowed. wren-core's own richer worked example
  (`row-level-access-control.rs`) was read and cited for context but not transcribed as scan input.
- midday: prompt/tool-manifest export (`apps/api/src/chat/prompt.ts`,
  `apps/api/src/mcp/tools/*.ts`) and policy-document extraction (`SECURITY.md`, privacy/terms TSX)
  were not attempted -- both are doctor-only accounting sections not consumed by `scan`.
- cube: `memberLevel.includes`/`excludes` (which columns a group may see in output, distinct from
  which rows) has no natural PolicyStrata field and was not modeled. The nested `or:`/`and:`
  date-range sub-filters in each fixture's second `rowLevel.filters` entry were not translated.

## Reproduction

```bash
# metricflow
uv run python examples/brownfield/metricflow/scripts/brownfield-transform-metricflow.py \
  --source <metricflow-clone> --out examples/brownfield/metricflow
uv run policystrata scan --config examples/brownfield/metricflow/policystrata.yaml \
  --out runs/brownfield-metricflow   # exit 0, gate warn

# midday
uv run python examples/brownfield/midday/scripts/brownfield-transform-midday.py \
  --source <midday-clone> --out examples/brownfield/midday
uv run policystrata scan --config examples/brownfield/midday/policystrata.yaml \
  --out runs/brownfield-midday   # exit 1

# WrenAI
uv run python examples/brownfield/WrenAI/scripts/brownfield-transform-wrenai.py \
  --source <WrenAI-clone> --out examples/brownfield/WrenAI
uv run policystrata scan --config examples/brownfield/WrenAI/policystrata.yaml \
  --out runs/brownfield-WrenAI   # exit 1

# cube (bonus)
uv run python examples/brownfield/cube/scripts/brownfield-transform-cube.py \
  --source <cube-clone> --out examples/brownfield/cube
uv run policystrata scan --config examples/brownfield/cube/policystrata.yaml \
  --out runs/brownfield-cube          # exit 1, 2/2 known-bad fixtures caught
uv run policystrata scan --config examples/brownfield/cube/policystrata_clean.yaml \
  --out runs/brownfield-cube-clean    # exit 1, scanner gap #1 recurrence
```

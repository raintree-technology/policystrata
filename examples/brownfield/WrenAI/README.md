# Brownfield target: Canner/WrenAI -- MDL row-level access control

Source: shallow clone (`--depth 1`) of `Canner/WrenAI`.
Static inspection only; no WrenAI/wren-core code (Python, Rust, or otherwise) was executed. All
content below was produced by `scripts/brownfield-transform-wrenai.py` (stdlib + PyYAML only)
reading `core/wren-core-base/tests/data/mdl.json`, a real MDL (Modeling Definition Language) test
fixture.

Run:

```bash
uv run python examples/brownfield/WrenAI/scripts/brownfield-transform-wrenai.py \
  --source <path-to-WrenAI-clone> \
  --out examples/brownfield/WrenAI
uv run policystrata scan --config examples/brownfield/WrenAI/policystrata.yaml \
  --out runs/brownfield-WrenAI
```

Result: **exit 1**, 11 findings (10 warnings, 1 gate-failing), gate `fail`. Not a config error.
This is the smallest-scope target in this pass -- see "Not attempted" for what was deliberately
left out.

## The fixture

`core/wren-core-base/tests/data/mdl.json` defines three models (`customer`, `profile`, `orders`).
Only `customer` has a `rowLevelAccessControls` entry, with three rules; this target uses only
`rule1`:

```json
{
  "name": "rule1",
  "requiredProperties": [{"name": "session_id", "required": true}],
  "condition": "c_custkey = @session_id"
}
```

`@session_id` is MDL's session-property placeholder: wren-core's query planner is meant to
substitute it with the actual session-bound value at query time (not a literal from the fixture
itself). For corroborating evidence of how `@session_property` conditions are meant to work in a
genuinely multi-tenant setting, see wren-core's own first-party worked example,
`core/wren-core/wren-example/examples/row-level-access-control.rs` (a *different*, richer MDL
manifest built via Rust `ManifestBuilder` calls, with a `documents` model and a
`tenant_id = @session_tenant_id` rule). That file is cited for context only -- it is not parsed,
executed, or transcribed by the transform script; every artifact in this target comes from the
one JSON fixture named above.

## What is native, transformed, and synthesized

| Artifact | Status | Detail |
| --- | --- | --- |
| `semantic_models.yml` | **Native, mapped** | All 3 MDL models included. `columns[]` entries whose `type` matches another model's name (i.e. relationship columns, like `customer`'s `orders` column) are excluded -- they describe joins, not selectable fields, and dbt's semantic-model schema has no matching concept. Every other column (including `isCalculated` ones, e.g. `custkey_plus`, `totalcost`) becomes a dbt `dimension:` with its real MDL `type` carried through unmodified. There is no MDL "measures"/"cubes" section in this fixture, so the merged `metrics:` list is genuinely empty -- nothing was invented to fill it (contrast with the metricflow and cube targets, which had real measures to derive metrics from). |
| `domain/policy.yaml` `dimensions{}` | **Native names, scoped to one model** | Only `customer`'s 3 non-relationship columns (`c_custkey`, `c_name`, `custkey_plus`) are covered -- `profile`'s and `orders`' dimensions are real MDL data but were not modeled here, because `customer` is the only model with a real RLAC rule and this target's whole point is the RLAC demonstration (see "Findings" below for the resulting, expected WARNING noise). |
| `tenancy.canonical_predicates` | **Mechanically rendered from the real condition** | `"c_custkey = :principal.tenant_id"` is `rule1`'s native `condition` string (`"c_custkey = @session_id"`) with MDL's `@session_id` token replaced by PolicyStrata's own `:principal.tenant_id` placeholder syntax -- a 1:1 token substitution, nothing else changed. See `transform_report.json`'s `native_condition` vs `canonical_predicate` fields. |
| `traces.jsonl` `wren_customer_rule1_consistent` | **SQL composed from the real, rendered predicate** | `select c_custkey, c_name from customer where c_custkey = 4821` -- `4821` is a synthetic session-id-shaped value (not a captured real one) substituted into the rendered predicate above. |
| `traces.jsonl` `wren_customer_rule1_bypassed_regression` | **Fully synthesized, explicitly labeled** | The same query with the `WHERE` clause removed, representing what PolicyStrata's tenant-scope check must catch if a `required: true` RLAC rule were ever silently not applied. Unlike the cube target, this is **not** grounded in a confirmed compiler-rejection test -- WrenAI's own test suite does not (as far as this static pass found) assert that a missing required session property is rejected at any particular layer, so this trace is explicitly a hypothetical defense-in-depth demonstration, not a claim about any specific wren-core behavior. Every trace's `expected_policy.note` field states this. |
| `domain/policy.yaml` `principals{}`/`roles{}` | **Fully synthesized** | One principal, one role. MDL's RLAC model is about session *properties*, not roles/principals in PolicyStrata's sense, so there was no real role structure to derive from -- same situation as the metricflow target. |
| `domain/surfaces.yaml` | **Boilerplate, reused verbatim** | Copied unmodified from `src/policystrata/domains/support_saas/surfaces.yaml`. |

## Findings, classified

### (a)-adjacent true positive, demonstration not discovery -- 1x `tenant_scope_missing` (HIGH/HIGH, gate-failing)

`wren_customer_rule1_bypassed_regression` is flagged; `wren_customer_rule1_consistent` (same
query, same principal, same tenant, only the `WHERE` clause differs) produces zero findings in
the same scan. As with the cube target, this validates that PolicyStrata's SQL-trace layer,
given a predicate mechanically rendered from a real MDL RLAC condition, correctly distinguishes
an enforced query from an unenforced one. Also as with the cube target, this is not a discovery
about WrenAI (we did not observe or execute wren-core's planner, and found no confirmed defect to
point to) -- it is a validated true-positive detection-capability demonstration using a
deliberately-labeled hypothetical regression case.

### (b) Synthesis artifact, non-gating -- 10x `dbt_stale_dimension` (WARNING)

Every one of `profile`'s and `orders`' real dimensions is flagged "stale" (present in the dbt
inventory, absent from the policy), because the policy was deliberately scoped to only the
`customer` model's RLAC-relevant columns. This is an expected consequence of the scope decision
above, not a discovery, and it does not gate (WARNING/MEDIUM).

### Clean signal worth naming

The one real-condition-consistent trace produced zero findings (no tenant-scope violation, no
dbt-adapter warning, no fuzz-survived mutant) in the same scan as the flagged regression trace --
**0 false positives on the one real, RLAC-consistent query; 1 of 1 hypothetical bypass case
caught.**

## Not attempted

- `rule2` (`session_id_optional`, `required: false`, no default) and `rule3`
  (`session_id_default`, `required: false`, `defaultExpr: "1"`) -- modeling what wren-core does
  when an optional session property is absent (skip the rule? apply a default?) would require
  reading wren-core's Rust RLAC-application logic closely enough to state its behavior with
  confidence, which this pass's time budget did not allow. Only `rule1` (required, unambiguous)
  was used.
- `core/wren-core/wren-example/examples/row-level-access-control.rs`'s richer
  `documents`/`tenants`/`users` manifest (real, tenant-scoped, with a second `auth` RLAC rule
  combining role/department/ownership conditions) was read for context and cited above, but not
  transcribed into MDL JSON or used as scan input -- it is Rust builder code, not a JSON/YAML
  fixture, and hand-transcribing an entire manifest carries more transcription risk than this
  pass's scope justified. `core/wren-core/core/tests/data/mdl.json` (a second, similar JSON
  fixture named in the inventory) was also not attempted.
- `columnLevelAccessControl` (a related but distinct MDL concept, gating column visibility rather
  than rows) was not modeled.
- `core/wren/src/wren/policy.py`'s strict-mode SQL AST validator and the MDL->dbt-project
  `metadata.yml` example files (`examples/v5-jaffle/...`) were noted in the inventory but not
  used in this pass.

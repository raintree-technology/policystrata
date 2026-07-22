# Brownfield target: midday-ai/midday

Source: shallow clone (`--depth 1`) of `midday-ai/midday` at
`/private/tmp/claude-501/-Users-mb1-Code-raintree-oss-policystrata/3e286431-07a6-4558-8ba2-1af21b7c3c90/scratchpad/brownfield/midday`.
Static inspection only; no midday code (TypeScript, Drizzle queries, or migrations) was executed.

Run:

```bash
uv run python examples/brownfield/midday/scripts/brownfield-transform-midday.py \
  --source <path-to-midday-clone> \
  --out examples/brownfield/midday
uv run policystrata scan --config examples/brownfield/midday/policystrata.yaml \
  --out runs/brownfield-midday
```

Result: **exit 1**, 2 findings (1 warning, 1 gate-failing), gate `fail`. Not a config error. See
classification below -- one finding is expected/non-gating, the other is a real, narrowly-scoped
structural limitation, not a midday defect.

## What is native, transformed, and synthesized

| Artifact | Status | Detail |
| --- | --- | --- |
| `schema.sql` | **Native, mechanically concatenated** | `scripts/brownfield-transform-midday.py` concatenates all 39 files under `packages/db/migrations/*.sql` in filename-numeric order, byte for byte, with a one-line `-- source: <path>` provenance comment before each. No SQL rewritten or reordered within a file. This is the transform the brownfield inventory calls for (`DatabaseScanConfig.schema` takes one file path; midday's real schema is spread across 39 ordered migrations). |
| `traces.jsonl` `sql` | **Hand-transcribed from real, cited TypeScript source** | Not produced by a script -- Drizzle ORM call chains can't be mechanically compiled to SQL text with stdlib+PyYAML only, and adding a TypeScript/SQL codegen dependency was out of scope (no new deps). Each trace's `sql` field is a literal-placeholder (`$1`, `$2`, ...) rendering of one real, named, cited `packages/db/src/queries/*.ts` function -- e.g. `midday_insights_get_insights` transcribes `db.select().from(insights).where(and(eq(insights.teamId, teamId))).orderBy(desc(insights.periodYear), desc(insights.periodNumber)).limit(pageSize).offset(offset)` from `insights.ts:147-153`. Column names are midday's real Drizzle-mapped snake_case names, taken from the migration DDL. Every trace's `expected_policy.note` field states the exact source function and line range, and every trace's `expected_policy.native_rls_policy` field quotes the real `CREATE POLICY` statement (with its migration file/line) that actually protects the queried table -- this is the strongest provenance-per-trace of any target in this pass. `$N` placeholder style matches what Drizzle's postgres.js dialect `.toSQL()` emits (see `docs/trace-adapters.md`'s own Drizzle recorder recipe, which calls `.toSQL()` the same way), so this is a faithful reconstruction of what a real recorder would have captured, not an invented format. |
| `traces.jsonl` `principal`, `tenant_ids` | **Synthesized** | Two synthetic principals (`midday_team_member`, `midday_authenticated_user`) with realistic-shaped (v4 UUID format) but not-real tenant/user ids -- midday's real actor identity comes from Supabase auth JWTs, which this static pass has no access to. |
| `traces.jsonl` `semantic_ir` | **Deliberately omitted on every trace** | midday has no metric/dimension semantic layer (confirmed in the inventory) -- it is a real multi-tenant SaaS backend, not a data-agent semantic product. Inventing a fake business-metric vocabulary to exercise PolicyStrata's authorization/fuzz-by-semantic-IR path would be *more* synthetic than this target warrants, so every trace omits `semantic_ir` and only the SQL-level tenant-scope check runs (see `domain/policy.yaml`'s header comment for the mechanical consequence: `PolicyOracle.authorize` is never reached, and 4 of the 7 fuzz mutation families are structurally `stillborn` for lack of an IR to mutate). |
| `domain/policy.yaml` | **Fully synthesized, documented as such in-file** | Two principals/roles exist only so `PolicyOracle.principal()` succeeds (a prerequisite for the static SQL checks to run at all); `metrics: {}` / `dimensions: {}` are intentionally empty for the reason above. See the file's own header comment. |
| `domain/surfaces.yaml` | **Boilerplate, reused verbatim** | Copied unmodified from `src/policystrata/domains/support_saas/surfaces.yaml`. |
| `tenancy.tenant_columns: [team_id]` (`policystrata.yaml`) | **Native pattern name, deliberately scoped as a bare column, not the full RLS predicate** | midday's real, dominant RLS pattern (confirmed in 5 migration files, 20 `CREATE POLICY` statements) is `team_id IN (SELECT private.get_teams_for_authenticated_user())`. That predicate is enforced *transparently by Postgres* and never appears as literal text in the application's own emitted SQL, so declaring it as a `canonical_predicates` string (checked as a literal substring) would be wrong and would flag every real trace. `docs/trace-contract.md` explicitly anticipates this ("If SQL intentionally relies on database RLS rather than literal tenant predicates, add trusted `database.rls_checks` or `database.state_assertions`") -- we did not stand up a live database in this pass (see below), so we used the weaker, correct-for-this-case `tenant_columns` check instead, which validates that the app *also* includes an explicit `team_id` filter (true defense-in-depth practice, and true of every team-scoped query we transcribed). |

## Findings, classified

### (c) Scanner limitation, non-gating -- 1x `postgres_fixture_unavailable` (WARNING)

`database.schema: schema.sql` is configured with `required: false` and no `start_docker`/seed.
This machine happens to have *something* listening on `127.0.0.1:55432` (the scan's connection
attempt got `password authentication failed`, not `connection refused`), so the finding reads as
an auth failure rather than "no server" -- either way, no live Postgres fixture matching
PolicyStrata's expected credentials was prepared, exactly as expected for this pass (we did not
start or configure one -- static analysis only, per this task's constraints). Non-gating by
design (`required: false`). This is expected, not a discovery.

### (c) Real, narrowly-scoped scanner/config limitation -- 1x `tenant_scope_missing` (HIGH/HIGH, gate-failing)

`midday_insight_user_status_get` is flagged: its SQL (`... where insight_user_status.insight_id =
$1 and insight_user_status.user_id = $2 ...`) never mentions `team_id`. This is **not** a midday
security gap -- `insight_user_status` genuinely has its own, different, real RLS policy scoped
by *user*, not *team*: `CREATE POLICY "Users can view their own insight status" ON
insight_user_status ... USING (user_id = auth.uid())` (`packages/db/migrations/0016_add_insights.sql:120-123`),
and the application code correctly filters by `user_id` to match. The finding exists because
`tenancy.tenant_columns` is a single global list applied identically to every trace in a scan
config (`src/policystrata/scanner.py::tenant_columns_for_scope_check`), with no per-trace or
per-table override -- so a config correctly scoped for midday's *dominant* tenancy dimension
(`team_id`, true for 4 of the 5 traces and 20 of the app's ~21 real RLS policies) cannot also
validate a table that legitimately uses a *different* tenancy dimension (`user_id`) without either
(a) missing real team-scope violations by widening `tenant_columns` to `[team_id, user_id]`
(either column would satisfy the check, defeating the point), or (b) flagging this one correctly-
scoped-but-differently-scoped table, which is what we chose to leave in place rather than paper
over. Recommended scanner enhancement (not applied -- `src/policystrata/**` is out of scope for
this task): allow `tenancy` to declare column sets per source-table/trace rather than one global
list, so multi-dimensional tenancy (common in real apps -- team-scoped resources alongside
user-scoped personal-preference tables) doesn't force this choice.

### Clean signal worth naming

**4 of 5 traces -- covering two different tables (`insights`, `invoice_recurring`) and two
different real query-builder functions each -- produced zero findings.** All four are real,
cited, team-scoped queries that explicitly filter by `team_id` in addition to the RLS policy that
also enforces it at the database layer (true defense-in-depth, and exactly the pattern
`tenant_columns` is designed to validate). **0 false positives on real, correctly-scoped midday
code; 1 true "different real tenancy dimension" finding that is honestly midday-correct but
scanner-config-invisible, not a midday defect.**

## Not attempted

- Live PostgreSQL comparison / `database.rls_checks` / `database.state_assertions` against a real
  midday schema+seed -- `schema.sql` is produced and wired into the config (`required: false`) so
  it is honestly attempted and reports its own unavailability rather than being silently absent,
  but no Postgres fixture (Docker or otherwise) was started for this pass. midday's schema also
  has no committed seed data to load even if a fixture were started.
- `apps/api/src/chat/prompt.ts` and `apps/api/src/mcp/tools/*.ts` (the real LLM prompt/tool
  surface called out in the inventory) -- exporting these to `prompts.json` for the
  doctor-only `prompt_manifests` accounting section was not attempted in this pass; `scan` does
  not consume that section, only `doctor` does.
- `SECURITY.md` / privacy-policy TSX extraction for `policy_docs.files` (doctor-only accounting,
  not consumed by `scan`) -- not attempted.
- A systematic search for a *real* midday query that queries a team-owned table while relying
  solely on RLS (no explicit `team_id` filter) -- the `insight_user_status` example above already
  grounds the "different tenancy dimension" finding in real code, and a broader search was out of
  scope for this pass's budget.

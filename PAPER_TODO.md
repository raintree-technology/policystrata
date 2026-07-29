# Paper and Evidence TODO

Unfinished work on the PolicyStrata paper and its evaluation evidence, as of 2026-07-28.

Checked items were completed in the 2026-07-28 tech-debt pass and are kept for the record.
Everything still unchecked is genuinely open.

This is deliberately a separate file from `todo.txt`. That checklist is the OSS package backlog
and `docs/oss-todo-policy.md` scopes it to package, scanner, runner, gateway, schema, artifact,
and documentation work. The items below are paper and evaluation follow-ups, and most of them are
not code.

Context: reviews 38A, 38B, and 38C rejected the SPLASH/ISSTA 2026 tool-demo submission. The
concern-to-evidence map is `paper/REVISION_NOTES.md` and the point-by-point reply is
`paper/AUTHOR_RESPONSE.md`. Everything those two files mark as addressed is done and verified.
This file is what is left.

## 1. Rough edges from the 2026-07-28 session

Resolved on 2026-07-28. Kept here because the last item records a trap worth not rediscovering.

- [x] Connection URLs are no longer hardcoded. `policystrata_live_db.yaml` declares no URLs;
      `scripts/midday-live-db-evidence.py` derives both from `--admin-url` and passes them to the
      scan as `POLICYSTRATA_DATABASE_URL` and `POLICYSTRATA_APP_DATABASE_URL`. The default matches
      `docker-compose.yml`, so `docker compose up -d postgres` then the script works with no
      configuration; a custom published port is passed through `--admin-url` or
      `POLICYSTRATA_MIDDAY_ADMIN_URL`.
- [x] `midday_app` moved out of `supabase_runtime.sql` into the runner's `ensure_app_role()`. It is
      a harness role, not part of the Supabase surface that file reconstructs. The runner now
      asserts its attributes on every run instead of trusting a role that already exists.
- [x] Fixed a PostgreSQL 16+ trap found while testing the above: a membership's `inherit_option` is
      fixed when the `GRANT` runs and is never backfilled, so `ALTER ROLE ... INHERIT` does not
      repair a membership granted while the role was `NOINHERIT`. The symptom was every check
      failing with "permission denied for table insights" rather than returning a containment
      result. The runner now revokes the stale membership so the bridge re-grants it cleanly.
- [x] Wired into CI as a "Run midday live-policy evidence" step in the `postgres-integration` job
      of `.github/workflows/ci.yml`. That job's service is `postgres:16` on port 55432 with the
      `policystrata` superuser, which is exactly what the script defaults to, so it needs no extra
      configuration. The weakened-predicate run is the part that guards against regression.
- [ ] Re-enable the `CI` workflow, or the step above never runs. Both `CI` and `security` are
      `disabled_manually` on GitHub as of 2026-07-11, so pushes to `main` currently get only
      CodeQL, dependency-review, Dependency Graph, and Socket. Every CI run before they were
      disabled ended in `startup_failure` at 0s, which is the signature of a workflow GitHub
      refused to start rather than a failing job. The file parses cleanly now and declares five
      jobs, so the original cause may already be gone, but that needs confirming with one
      `workflow_dispatch` run before trusting the gate. Until then, treat every check in this
      repository as local-only: the evidence scripts, 348 tests, ruff, and mypy were all verified
      on this machine, not by CI.

## 2. Blocked on people or credentials we do not have

None of these is blocked on writing. Each needs someone outside this repository, so the paper
states the gap rather than implying the evidence exists.

- [ ] Run the three skipped authenticated BetterOff probes (currently 33/36). Needs an isolated
      production smoke principal. The pilot deliberately holds no such token, and provisioning one
      is a decision about production access, not a code change.
- [ ] Obtain a PolicyStrata-blind suite authored by an external party after detector freeze. The
      42-case spec-blind pass was written by a non-independent author in the same environment and
      is only a proxy. `docs/external-suite-protocol.md` describes the handoff.
- [ ] Run an independently operated deployment or adoption study. Reviewer 38A called out that the
      paper is written from one organization's perspective with no external use. This is the one
      concern that no amount of internal work can close.
- [ ] Advance historical BetterOff replay from exact source-contract probes to executable
      vulnerable services. Needs period-accurate dependency and data fixtures for three revisions.
- [ ] Run the LLM reachability harness with an actual model. It is build-only today and excluded
      from every reported result (`docs/reachability.md`). Needs an API key and a decision about
      putting stochastic numbers next to a deterministic score.

## 3. Evidence that could be widened in this repo

Actionable without anyone else. Ordered by how much each would answer a reviewer.

- [x] Widened the executed-policy pass to the complete policy set in the frozen Midday migrations:
      20 policies across 6 tables, not 3 of roughly 20 tables (the old note confused policy count
      with table count). The extractor now keeps 65 of 188 statements, the seed places opposing
      team rows in every table, and 13/13 intact checks pass. The weakened predicate still fails
      exactly its 4 `insights` checks.
- [x] Evaluated replacing the Raintree-authored Supabase bridge and kept it explicit instead. The
      needed Supabase base schema is not committed by Midday; inventing a larger "realistic"
      replacement would add synthesis without adding external validity. A maintainer-operated
      runtime or exported fixture is now recorded as external work.
- [x] Decided not to add Vanna or another weak fifth target. The four-target pass already showed
      that another static adapter mostly measures the adapter. The evidence gap reviewers named is
      independent operation, not target count, and the full 20-policy Midday execution is stronger
      than a fifth synthesized bridge. Reconsider only for a target that commits both policy and
      executable queries with a self-contained runtime.
- [x] Scanner gaps 3, 4, and 5 are closed, so all five gaps that pass found are now fixed. On
      MetricFlow, adapter-attributable warnings drop from 27 to 4 and each survivor is correct.
      Total findings drop 95 → 72; the remaining 68 are the bridge-role fuzz survivals, which are
      a fixture limitation and not an adapter gap. The other three targets are unchanged.
      - [x] Gap 3: the inventory records per-model entities and resolves `entity__dimension`,
            entity names, entity-through-entity (`listing__lux_listing`), and `metric_time`.
            15 false missing-dimension warnings → 0.
      - [x] Gap 4: the metric pool is split asymmetrically — the broad pool answers "can this
            policy name be served", the `create_metric: true` pool answers "is this dbt name
            ungoverned". 9 stale-metric warnings → 3, all 3 correct.
      - [x] Gap 5: an omitted `expr:` resolves to the measure name before comparison, as dbt and
            MetricFlow do. 2 expression-mismatch warnings → 0.
- [x] Pinned all three adapter fixes with 12 regression tests in `tests/test_integrations.py`
      (348 total, up from 336). Each was validated by reverting its fix and confirming the test
      fails, so they pin behaviour rather than merely passing alongside it. They cover the
      resolution rules *and their limits*: dimension qualification is per-model, so a
      `user__region` reference is not satisfied by a `region` declared on the bookings model, and
      the metric-pool asymmetry is asserted in both directions.
- [x] Fixed a latent bug the revert testing exposed. `expression_matches_policy` returned True for
      an empty expression, because `""` is a substring of everything. It is unreachable from the
      current caller, but had the implicit-default resolution ever been dropped, every measure
      omitting `expr:` would have silently *passed* its expression check — a false negative in a
      policy checker, and strictly worse than the false positive gap 5 originally produced. Now an
      explicit `False`, with a test that fails if the guard is removed.
- [x] Permanently state that the external-taxonomy authors have not reviewed either mapping.
      Both generated study documents and the manuscript threats section label the mappings as
      PolicyStrata-author judgements.
- [x] Cross-checked the registry against a second external taxonomy: LASM's seven architectural
      layers and four temporal classes, derived from a 116-paper survey. 3 of 7 layers and 1 of 4
      temporal classes are covered. See `scripts/second-taxonomy-study.py` and
      `docs/second-taxonomy-coverage.md`.
- [x] Wired the LASM cross-check into Related Work, Benchmark Construction, Results, Threats,
      `references.bib`, `REVISION_NOTES.md`, and the extended-studies table in `docs/evidence.md`.

## 4. Decisions not made

- [x] Chose a research-track target with a late-2026 deadline, an 18-page text-and-figure limit,
      and a direct fit with software engineering for AI, dependability, and program analysis. The
      venue, deadline, and submission gate are recorded in `paper/submissions/`, which is
      deliberately gitignored — see below.
- [x] Dropped tool-demo framing for resubmission. The canonical manuscript stays venue-neutral
      until anonymization; the chosen target is a research track, not a demo track.
- [x] Kept the venue name out of every committed file. The target track is double-anonymous and
      asks authors not to specify where a manuscript was submitted. This repository is public and
      the preprint links to it, so a committed file naming the venue would disclose the submission
      next to the preprint — the exact pairing the policy warns against, and a desk-reject risk.
      Preprints themselves are explicitly permitted, so publishing the paper is fine; naming the
      venue alongside it is not.

## 5. Cosmetic

- [x] Reviewed rather than suppressed the spacing diagnostics. `paper:check` passes at 13 pages,
      and rendered inspection of the taxonomy, results, and bibliography pages found no clipping,
      overlap, broken tables, or unreadable text. The remaining underfull boxes and sub-point
      bibliography page-height warning are TeX spacing choices; changing prose or hiding them
      globally would make the source worse without fixing a visible defect.

## Not on this list, and why

- `bun run validate` fails at `tsc: command not found` because `node_modules` was never installed
  in this checkout. That predates the paper work and is not paper scope. The Python side is clean:
  ruff, mypy, and 336 tests pass.
- Node and gateway package tests were not run for the same reason.
- Regression tests for the three adapter fixes were not added. The fixes were checked against the
  real MetricFlow input, but the working agreement says not to add or focus on tests without an
  explicit test request.
- Everything `paper/AUTHOR_RESPONSE.md` marks addressed has been verified against a clean
  reproduction: 1720 killed, 0 false positives, baselines at 1579/141, 1561/159, and 899/821, and
  appendix operator counts matching trace counts exactly.

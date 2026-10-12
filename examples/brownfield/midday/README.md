# Review the Midday integration

This example helps maintainers inspect PolicyStrata's checks against a frozen
Midday source corpus. It uses reconstructed query traces and synthetic identities.
It does not establish Midday adoption or describe its deployed system.

## Run the static check

From the PolicyStrata repository, with uv installed, run:

```bash
uv run --locked --no-dev policystrata scan \
  --config examples/brownfield/midday/policystrata.yaml \
  --out runs/midday-review
```

The configuration checks team-scoped tables using `team_id` and
`insight_user_status` using `user_id`. A local run on 2026-10-01 exited zero
with a `warn` gate and one `postgres_fixture_unavailable` warning. That warning
means database enforcement was not tested; the static result cannot prove
containment. Earlier study results describe the configuration before this override.

## Review the database evidence

The [live-database study](../../../docs/studies/midday-live-database.md)
documents loading 20 native policy statements into a reconstructed Supabase
runtime with synthetic rows. Its recorded intact run passed. A deliberately
weakened SELECT policy produced four findings on `insights`. This is an injected
regression, not a discovered Midday defect.

The existing runner is `scripts/midday-live-db-evidence.py`. It resets a database
named `midday_live` and changes fixture roles. Run it only against a disposable
PostgreSQL instance dedicated to this example. The live study was not rerun on
2026-10-01 because the local fixture was unavailable.

## Evaluate usefulness in your own release process

1. Record the source revision, policy owner, and existing checks that protect the
   selected operation. Separate native inputs from reconstructed inputs.
2. Run an intact revision and investigate every finding before using the gate.
3. Introduce one synthetic policy regression in an isolated fixture. Run the
   existing checks and PolicyStrata separately, then record which detects it.
4. Restore the policy and verify containment and the passing gate. Repeat on a
   second revision without maintainer assistance.

Record setup time, manual translations, false findings, and unresolved checks.
No independent maintainer trial is confirmed. A useful integration must show
what PolicyStrata adds to the existing checks and where its model stops.

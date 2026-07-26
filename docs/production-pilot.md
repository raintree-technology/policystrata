# BetterOff Production Pilot

On 2026-07-26, PolicyStrata was evaluated against the exact source revision deployed to
BetterOff production. The machine-readable record is
`studies/betteroff-production-pilot.json`.

## Deployment binding

Vercel reported deployment `dpl_5MQsJfscJaALxGU8nBh2srXBWQNr` as `READY` for
`app.betteroff.finance`, built from
`3663f1e475eb2ba452dc887a10b052689455a4f4`. The BetterOff primary checkout was on the same
revision. The pilot therefore did not infer deployment status from a reachable hostname; it
bound the evidence to one Git object and one production deployment.

## Live read-only checks

BetterOff's production surface verifier attempted 36 probes across the marketing site,
authenticated app boundary, API, and admin shell:

- 33 passed;
- none failed;
- three authenticated reads were skipped because no isolated production smoke-session cookie or
  API token was configured.

The passing probes include health and readiness, sign-in metadata, unauthenticated denial for
transactions and exports, blocked cron and internal routes, and rejection of invalid webhook
signatures. Valid Stripe, Plaid, and forwarded-webhook probes were deliberately excluded because
they can enqueue work or consume idempotency keys.

These checks used empty or invalid payloads. They did not read customer financial rows or mutate
production state.

## PolicyStrata adapter on the deployed revision

The same Git revision contains BetterOff's checked-in PolicyStrata adapter. Doctor reported 33
tools, three roles, six runtime-event fixtures, and no missing or partial wiring. The scan ran six
SQL traces, two RLS checks, and two database-state assertions against a disposable PostgreSQL
fixture. It returned zero findings and gate `pass`.

This is stronger than the earlier synthetic BetterOff fixture claim because the policy, surface
map, runtime manifest, traces, and source paths come from the deployed application revision. It
is still not an authenticated live cross-tenant experiment: SQL and RLS evaluation used synthetic
rows, and the live authenticated probes were unavailable.

## Reproduction

From the BetterOff repository at the recorded revision:

```bash
bun run policystrata:check-generated
bun run policystrata:check-runtime-readiness
bun run policystrata:doctor
bun run policystrata:scan
bun tools/release/verify-production.mjs --main --skip-vercel --skip-github
```

The combined release verifier's local Vercel credential was expired during this run. Deployment
identity was therefore read through the connected Vercel account, while the command above ran the
live HTTP surface matrix without deployment API access.

## Remaining production evidence

The next safe increment is an isolated, non-customer smoke principal with an app session and API
token. It should carry synthetic accounts in its own household and be barred from all customer
households. That would enable the three skipped authenticated probes and a live same-household
versus foreign-household denial test without using customer data.

# Deployment-Linked Study

PolicyStrata was evaluated against the source revision running in a maintainer-operated production
application. The application repository and deployment control plane are private, so this public
record intentionally omits service names, domains, routes, commit identifiers, deployment IDs,
file paths, and input hashes.

## Deployment binding

The deployed source revision and the revision inspected by the adapter matched. This establishes
that the study did not infer production status from a reachable hostname or test a different local
checkout. The underlying identifiers are retained with the private operational record.

## Read-only boundary checks

The verifier attempted 36 non-mutating boundary probes:

- 33 passed;
- none failed;
- three authenticated probes were skipped because no isolated synthetic production principal was
  available.

The passing probes covered public health behavior, authentication metadata, unauthenticated
application and API denial, export denial, and invalid-signature rejection. Checks that could
enqueue work, consume idempotency keys, or alter state were excluded.

The probes used empty or invalid payloads. PolicyStrata read no customer rows and made no
production mutations.

## Adapter result

On the same source revision, the adapter described 33 tools, three roles, and six runtime-event
fixtures with no missing or partial wiring. Six SQL traces and four database checks passed against
a disposable PostgreSQL fixture using synthetic rows.

## Evidence boundary

This study establishes deployment binding, adapter applicability, and selected unauthenticated
denial behavior. It does not establish authenticated tenant-to-tenant isolation, customer-data
safety, effectiveness on unknown faults, or independent operation. Because the target source and
deployment records are private, this aggregate result is auditable by the maintainers but not
independently reproducible from the public repository.

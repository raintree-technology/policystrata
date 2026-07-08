# GitHub Action

The first GitHub integration is a composite action that wraps `policystrata scan`.
It is meant for release gates and pull-request checks: if high-confidence drift is found, the
action exits non-zero and blocks the workflow.

The action installs PolicyStrata from the action checkout by default, so it can be used from a
repository tag before the package is published to PyPI. After the PyPI package is published, callers
can optionally set `package` to a normal pip install spec such as `policystrata==1.0.5`.

For CI, run two gates:

- `policystrata scan` for the policy-drift gate.
- `policystrata doctor --strict` for the implementation-readiness gate.

The action provides the scan gate. Add a CLI doctor step when missing, partial, or invalid wiring
should block release.

## Basic Gate

```yaml
name: PolicyStrata

on:
  pull_request:
  push:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4

      - uses: raintree-technology/policystrata@v1.0.5
        with:
          config: policystrata.yaml
          out: runs/policystrata

      - name: Implementation readiness gate
        if: always()
        run: policystrata doctor --config policystrata.yaml --strict
```

## Upload Scan Artifacts

```yaml
      - uses: raintree-technology/policystrata@v1.0.5
        with:
          config: policystrata.yaml
          out: runs/policystrata

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: policystrata-scan
          path: runs/policystrata
```

## JUnit Output

When your CI test reporter expects JUnit XML, run the scanner CLI directly:

```yaml
      - name: PolicyStrata scan with JUnit
        run: |
          policystrata scan \
            --config policystrata.yaml \
            --out runs/policystrata \
            --junit test-results/policystrata.xml

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: policystrata-junit
          path: test-results/policystrata.xml
```

## Generic JSON Evidence

For CI systems that want a single redacted JSON handoff without Clearance, export the run after the
scan or deterministic suite finishes:

```yaml
      - name: Export generic PolicyStrata evidence
        if: always()
        run: |
          policystrata export runs/policystrata \
            --format policystrata-json \
            --out runs/policystrata/evidence.json

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: policystrata-evidence
          path: runs/policystrata/evidence.json
```

This stays local to the workflow. The generic JSON export is an OSS artifact format; it does not
call hosted Clearance APIs and does not require hosted auth.

## Clearance Runner Contract

For repositories that use the optional Clearance runner contract, generate local metadata-only
artifacts and upload only the runner payload. The upload step requires a runner token and returns
exit code `4` on upload/auth failure.

```yaml
      - name: PolicyStrata run
        run: |
          uv run policystrata run \
            --domain support_saas \
            --suite seeded \
            --out runs/policystrata \
            --clearance-config clearance.runner.yaml \
            --commit-sha "$GITHUB_SHA" \
            --environment ci

      - name: Validate Clearance runner config
        run: uv run policystrata clearance-runner validate --config clearance.runner.yaml

      - name: Write Clearance evidence pack
        run: |
          uv run policystrata clearance-runner evidence-pack \
            --run-dir runs/policystrata \
            --config clearance.runner.yaml \
            --out runs/policystrata/evidence-pack.json

      - name: Upload Clearance metadata
        env:
          CLEARANCE_RUNNER_TOKEN: ${{ secrets.CLEARANCE_RUNNER_TOKEN }}
        run: |
          uv run policystrata clearance-runner upload \
            --run-dir runs/policystrata \
            --config clearance.runner.yaml
```

## Config-Scoped Doctor

`doctor` audits only the selected config. In the copied `postgres_dbt` example,
`policystrata_clean.yaml` is a minimal clean scan and will not claim database readiness. Use
`policystrata_real_db_clean.yaml` for DB/RLS readiness checks, or merge the dbt and database
sections into your application config before enabling `doctor --strict` as a release gate.

## Inputs

- `config`: scanner config path. Defaults to `policystrata.yaml`.
- `out`: output directory for `scan.json`, `findings.jsonl`, `summary.json`, `report.md`,
  witnesses, and optional SARIF. Defaults to `runs/policystrata`.
- `python-version`: Python version for the action runtime. Defaults to `3.12`.
- `package`: optional pip install spec. Leave empty to install from the action checkout.
- `extra-args`: additional trusted `policystrata scan` arguments.

## Boundaries

The action is a CI wrapper around the CLI. It is not a GitHub CLI extension, hosted scanner, MCP
server, or authorization boundary.

Repository-relative paths in `policystrata.yaml` resolve in the checked-out caller repository.
For real database checks, configure disposable services or sanitized fixtures in the workflow; do
not point first-pass release gates at mutable production databases.

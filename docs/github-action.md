# GitHub Action

The first GitHub integration is a composite action that wraps `policystrata scan`.
It is meant for release gates and pull-request checks: if high-confidence drift is found, the
action exits non-zero and blocks the workflow.

The action installs PolicyStrata from the action checkout by default, so it can be used from a
repository tag before the package is published to PyPI. After the PyPI package is published, callers
can optionally set `package` to a normal pip install spec such as `policystrata==0.1.2`.

## Basic Gate

```yaml
name: PolicyStrata

on:
  pull_request:
  push:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: raintree-technology/policystrata@v0.1.2
        with:
          config: policystrata.yaml
          out: runs/policystrata
```

## Upload Scan Artifacts

```yaml
      - uses: raintree-technology/policystrata@v0.1.2
        with:
          config: policystrata.yaml
          out: runs/policystrata

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: policystrata-scan
          path: runs/policystrata
```

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

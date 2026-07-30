# Distribution

PolicyStrata publishes three supported artifacts:

- the Python CLI and scanner as `policystrata` on PyPI;
- the Node recorder and runtime as `policystrata` on npm;
- the customer-hosted gateway as `@policystrata/agent-trust-gateway` on npm.

Install the Python CLI with `uvx policystrata` or `pipx run policystrata`. Install the Node
artifacts with the package manager used by the consuming application.

The repository also provides a GitHub Action that runs `policystrata scan`. The action is a thin
wrapper around the public CLI: callers remain responsible for checkout, database services, and
artifact retention.

The Python modules are importable, but internal modules are not a stable application-facing SDK.
Only documented CLI, schema, runtime, and gateway contracts carry compatibility guarantees.

All registry releases are built and published by the release workflow with provenance. Production
applications should pin published versions rather than depend on sibling checkouts or repository
archives.

# JavaScript Distribution Decision

Status: initial npm package published; future npm releases should use trusted publishing.

Date: 2026-07-02

## Decision

PolicyStrata should use dual distribution:

- PyPI remains the distribution for the Python scanner, doctor, benchmark runner, and CLI.
- npm is the correct distribution for Node applications that import `policystrata/node` or
  `policystrata/runtime`.

Do not make Node consumers depend on the PyPI package or a sibling source checkout. Normal Node
runtime usage should protect tool/action and result-release boundaries in-process:

```bash
npm install policystrata
```

```ts
import { createPolicyStrataAuthorizer } from "policystrata/runtime";
```

The initial npm package `policystrata@0.1.0` was published on 2026-07-02. The npm package has a
GitHub Actions trusted publisher configured for this repository's `publish.yml` workflow and `npm`
environment.
The Node package version `policystrata@0.1.1` is intended to publish through the GitHub trusted
publisher workflow from the `v1.0.3` tagged release commit.

## Release Policy

Registry-side trusted publisher configuration must match this repository workflow:

- PyPI project `policystrata`: GitHub owner `raintree-technology`, repository `policystrata`,
  workflow filename `publish.yml`, environment `pypi`.
- npm package `policystrata`: GitHub owner `raintree-technology`, repository `policystrata`,
  workflow filename `publish.yml`, environment `npm`, allowed action `npm publish`.

Before publishing a future npm package version:

- confirm package ownership and maintainer access on npm;
- use npm trusted publishing from GitHub Actions rather than a long-lived token or local publish;
- keep `npm publish --provenance` in the workflow so provenance intent is explicit even though npm
  trusted publishing also generates provenance attestations automatically;
- verify the target package version is not already published;
- keep the package export map limited to documented public entry points;
- include TypeScript declarations, README, license, and the runtime manifest schema in the tarball;
- run `bun run --cwd packages/node test`;
- run `npm pack --dry-run` from `packages/node`;
- run Python parity with `uv run pytest tests/test_runtime.py`;
- verify conformance fixtures cover allow/deny, unknown action/resource, role aliases, write/export
  approvals, semantic constraints, release boundary constraints, and deny-by-default;
- publish from a clean tagged release commit after reviewing package contents.

Before publishing the PyPI package:

- bump `pyproject.toml` and `src/policystrata/__init__.py` together;
- update `CHANGELOG.md`;
- run `uv run pytest`, `uv run ruff check .`, and `uv run mypy src`;
- build and check the wheel/sdist with `uv build` and `uv run twine check --strict dist/*`;
- publish through PyPI trusted publishing from a protected release environment.

## Versioning

The Python and npm artifacts may version independently because they serve different package
ecosystems. If they are released together from one tag, the release notes should state both artifact
versions explicitly, for example:

- PyPI: `policystrata==1.0.3`
- npm: `policystrata@0.1.1`

If the Node runtime becomes a committed stable SDK at the same maturity level as the scanner, revisit
whether the npm version should align with the Python package version.

## Boundary

`policystrata scan` and `policystrata doctor` are release/readiness gates over exported evidence.
`policystrata/runtime` is an in-process application authorizer. The runtime can enforce app-local
subject/action/resource decisions and result/lineage release decisions, but it does not replace
scanner evidence, database controls, or application authorization reviews.

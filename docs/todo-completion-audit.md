# TODO Completion Audit

This audit checks the root `todo.txt` as the OSS package checklist. Items in section 15 are
completed by classification to the private Clearance app TODO, not by implementing hosted product
features inside this repository.

## Evidence Reviewed

| TODO section | Status | Primary evidence |
| --- | --- | --- |
| Product boundary | Verified | `README.md`, `docs/clearance-runner.md`, `docs/open-source-commercial-strategy.md`, deterministic `uv run pytest` suite. |
| Clearance runner contract | Verified | `src/policystrata/clearance.py`, `src/policystrata/cli.py`, `tests/test_clearance.py`, `tests/fixtures/schemas/valid/clearance-run.json`. |
| Local artifact directory | Verified | `src/policystrata/clearance.py`, `src/policystrata/scanner.py`, `tests/test_clearance.py`, `tests/test_scanner.py`. |
| Metadata-only boundary | Verified | Python scanner in `src/policystrata/clearance.py`, gateway scanner in `packages/gateway/src/index.ts`, tests in `tests/test_clearance.py` and `packages/gateway/test/gateway.test.ts`. |
| Runner upload contract | Verified | Upload payload builder, validation, size limit, idempotency key, auth header, protected branch behavior, and mock upload tests in `tests/test_clearance.py`. |
| Exit codes and CI | Verified | Clearance exit-code enum and CLI paths in `src/policystrata/clearance.py` and `src/policystrata/cli.py`; docs in `docs/clearance-runner.md` and `docs/github-action.md`; JUnit output in `src/policystrata/scanner.py`. |
| Runtime and gateway | Verified | Python runtime tests in `tests/test_runtime.py`; Node runtime tests in `packages/node/test/runtime.test.ts`; gateway tests in `packages/gateway/test/gateway.test.ts`; docs in `docs/runtime-controls.md`. |
| Scanner and evidence accuracy | Verified | Audit fixture catalog in `tests/fixtures/audit/audit-fixtures.json`; coverage tests in `tests/test_audit_fixtures.py`; witness minimization tests in `tests/test_scanner.py`. |
| Schemas and compatibility | Verified | Public schema registry in `src/policystrata/schemas.py`; valid/invalid fixtures under `tests/fixtures/schemas`; compatibility tests in `tests/test_schema_compatibility.py`; policy in `docs/schema-compatibility.md`. |
| Node SDK | Verified | Recorder versioning/redaction in `packages/node/src/node.ts`; runtime event builders in `packages/node/src/runtime.ts`; tests in `packages/node/test/node.test.ts` and `packages/node/test/runtime.test.ts`. |
| Native / external integrations | Verified | Adapter exports in `src/policystrata/exports.py`; integration boundary tests in `tests/test_integrations.py`; generic docs in `docs/generic-exports.md`. |
| OSS user docs | Verified | `README.md`, `docs/clearance-runner.md`, `docs/runtime-controls.md`, `docs/gateway-deployment-examples.md`, `docs/evidence.md`, `docs/generic-exports.md`. |
| Distribution and release | Verified | `MANIFEST.in`, `pyproject.toml`, `tests/test_database_assets.py`, `tests/test_release_metadata.py`, `docs/pilot-install-path.md`, `docs/js-distribution-decision.md`. |
| Security posture | Verified | `SECURITY.md`, `.github/workflows/dependency-review.yml`, `.github/workflows/security.yml`, `tests/test_security_posture.py`, database docs/tests avoiding host `psql`. |
| Clearance hosted product work | Verified as out-of-repo classification | `docs/oss-todo-policy.md`, the private app TODO, and section 15 wording in root `todo.txt`. |
| Immediate next steps | Verified | `docs/oss-todo-policy.md`, `docs/contract-milestones.md`, this audit note, and app-only classification in root `todo.txt`. |

## Corrections Made During Audit

- Added runner/package metadata to `.clearance/clearance-run.json` so both Clearance artifacts carry
  the PolicyStrata package version.
- Fixed JUnit XML attribute quoting for finding IDs and messages containing quotes.
- Reworded conditional Docker/signed-binary TODO items to document the current decision instead of
  implying artifacts were published.
- Reworded section 15 to make clear hosted auth/UI/billing/operations are classified to the private
  Clearance app, not implemented in the OSS repository.

## Verification Commands

Run these from the repository root before treating the checklist as release-ready:

```bash
uv run ruff check .
uv run mypy src
uv run pytest
npm test --workspace packages/node
npm test --workspace packages/gateway
```

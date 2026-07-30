# PolicyStrata

Every layer of a SQL data agent can pass its own tests while the stack fails as a whole. A
tenant-scoped request reaches a stale compiler, the compiler lowers it against
`legacy_tenant_id`, and another tenant's rows can enter the result.

PolicyStrata catches that class of drift in CI. It checks the transitions between model-visible
tools, semantic validation, SQL compilation, database containment, and result release—then writes
a small witness that identifies the first layer that broke the policy.

[PyPI](https://pypi.org/project/policystrata/) ·
[Documentation](https://github.com/raintree-technology/policystrata/tree/main/docs) ·
[Paper](https://raintree.technology/papers/PolicyStrata.pdf)

Runs are deterministic and require no LLM API key. Evidence stays local and metadata-only by
default.

> PolicyStrata's scanner is a regression tester and release gate, not an authorization boundary.
> Keep application authorization and database controls in the system being tested.

## See a Failure

```bash
uvx policystrata demo --out runs/demo
```

No manual install is needed: `uvx` creates an isolated environment and runs the package.

The demo runs 50 deterministic cases and prints a worked witness (excerpt):

```text
Worked example: stale tenant-key lowering
- Request: Show escalations by severity for my tenant, variant 1.
- Version vector: manifest=v7, grammar=v7, validator=v7, compiler=v5, database=v7, release=v7
- First violated transition: compiler (lowering_violation)
- Why: compiler violated its declared responsibility: The compiler emits a predicate against legacy_tenant_id instead of tenant_id.
- Distinguishing result before containment: canonical=4, lowered=12
- Containment: database
- Release: blocked
```

The complete run writes JSONL traces, a summary, and minimized JSON witnesses under `runs/demo`.

The 50-case demo completes in about 0.2 seconds locally after dependencies are installed.
Dependency installation and optional database startup are separate CI costs.

## Is This for You?

The strongest supported path is SQL/data-agent policy drift: text-to-SQL systems, BI copilots, dbt
semantic models, PostgreSQL RLS, and governed analytics tools.

PolicyStrata is a good fit when:

- a semantic model or tool manifest declares capabilities that are later lowered into SQL;
- tenant or role rules are repeated across validation, PostgreSQL RLS, and release filters; and
- you can export sanitized traces and want CI to fail when those layers disagree.

It is not a model-quality benchmark, penetration-testing suite, or replacement for runtime
authorization.

## What It Checks

```text
canonical policy
    → model-visible manifest
    → semantic validation
    → SQL compilation
    → database containment
    → result release
```

Each transition has a declared responsibility. PolicyStrata generates or imports policy-relevant
traces, compares the observed transition with the canonical obligation, and localizes the first
violation instead of requiring every layer to behave identically.

See the [failure taxonomy](https://github.com/raintree-technology/policystrata/blob/main/docs/failure-taxonomy.md)
for the concrete drift classes.

## What the Numbers Do and Don't Show

A conventional layered control stack caught 1,561 of 1,720 injected faults. PolicyStrata's
responsibility-scoped contracts caught all 1,720 and attributed each to its first violating
surface.

The remaining 159 were not flagged by any of the validator, SQL-snapshot, database/RLS, or
final-answer checks in that layered stack—not merely detected and misattributed. Each point
control's local view accepted them; the transition contracts detected the disagreement and
localized the first break.

The 1,720 cases come from PolicyStrata's own published operator taxonomy, so the all-caught result
is an internal consistency invariant—not production recall. The useful comparative result is the
159-case gap.

Read the [evidence snapshot](https://github.com/raintree-technology/policystrata/blob/main/docs/evidence.md)
for the underlying counts and limitations, or the
[paper](https://raintree.technology/papers/PolicyStrata.pdf) for the complete evaluation.

These results establish fault-model coverage and reproducible regression behavior. They do not
establish recall on unknown production failures or independently operated deployment
effectiveness.

## Install

| Surface | Install | Documentation |
| --- | --- | --- |
| Python CLI and scanner | `python -m pip install policystrata` | [PyPI](https://pypi.org/project/policystrata/) |
| Node recorder and runtime | `npm install policystrata` | [npm](https://www.npmjs.com/package/policystrata) |
| Self-hosted gateway | `npm install @policystrata/agent-trust-gateway` | [npm](https://www.npmjs.com/package/@policystrata/agent-trust-gateway) |
| CI scanner | Pin a released `v*` tag | [GitHub Action guide](https://github.com/raintree-technology/policystrata/blob/main/docs/github-action.md) |

For one-off Python use, run commands through `uvx` or `pipx` without managing an environment.

## Scan an Application

Create a scanner configuration, scan its example trace, and inspect readiness:

```bash
uvx policystrata init-scan --out policystrata
uvx policystrata scan \
  --config policystrata/policystrata.yaml \
  --out runs/policystrata
uvx policystrata doctor \
  --config policystrata/policystrata.yaml
```

`scan` finds policy drift in configured artifacts and exported traces. `doctor` checks whether the
expected stack surfaces and release gates are wired. Add `--strict` in CI once every reported
readiness gap should fail the build.

The generated `policystrata.yaml` names the policy domain, required traces, tenancy vocabulary, and
gate behavior:

```yaml
domain: support_saas
domain_path: domain
sql_traces: {files: [traces.example.jsonl], required: true}
tenancy: {tenant_columns: [accounts.tenant_id]}
gate: {fail_on_high_confidence: true}
```

The scanner can emit JSON, JSONL, Markdown, minimized witnesses, and SARIF. Start with the
[scanner guide](https://github.com/raintree-technology/policystrata/blob/main/docs/scanner.md),
[trace contract](https://github.com/raintree-technology/policystrata/blob/main/docs/trace-contract.md),
and [trace adapters](https://github.com/raintree-technology/policystrata/blob/main/docs/trace-adapters.md).

## Run a Benchmark

Run the deterministic benchmark when evaluating PolicyStrata itself. Application CI normally uses
`scan` instead.

```bash
policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out runs/generated
policystrata summarize runs/generated
```

For archival comparisons, `policystrata freeze-benchmark` creates a manifest that `run
--freeze-manifest` verifies before execution. Freeze manifests hash the policy, surfaces, tasks,
generator, detector, and operator taxonomy so results can be compared across revisions. See the
[benchmark reference](https://github.com/raintree-technology/policystrata/blob/main/docs/benchmark-reference.md)
and [versioning guide](https://github.com/raintree-technology/policystrata/blob/main/docs/benchmark-versioning.md).

## Optional Runtime Enforcement

The Node runtime provides a deterministic in-process authorizer for applications that want live
tool and result-release decisions. The self-hosted gateway evaluates the same contracts out of
process, centralizes sanitized decision envelopes, and can return `allow`, `deny`, `redact`,
`require_approval`, `quarantine`, or `log_only`.

These components enforce in the application's request path; the scanner does not. Adopting them is
a separate decision from using the CI gates. No general runtime-overhead claim is published, so
measure them in the target deployment.

See [runtime controls](https://github.com/raintree-technology/policystrata/blob/main/docs/runtime-controls.md)
and the [gateway deployment examples](https://github.com/raintree-technology/policystrata/blob/main/docs/gateway-deployment-examples.md).

## Data-Safety Boundary

- Keep raw prompts, documents, rows, tool payloads, credentials, and private schemas local.
- Upload only the metadata required for a finding or release decision.
- Treat generated-case coverage as fault-model coverage, not field recall.
- Treat scanner findings as regression evidence, not proof of authorization correctness.

The gateway strips event payloads and fixture-only expectations from uploads by default and rejects
common sensitive-data and secret patterns before sending metadata. The
[Clearance runner contract](https://github.com/raintree-technology/policystrata/blob/main/docs/clearance-runner.md)
documents the artifact and upload boundary.

## Documentation

| Topic | Guide |
| --- | --- |
| Scanner configuration and gates | [Scanner](https://github.com/raintree-technology/policystrata/blob/main/docs/scanner.md) |
| Benchmark domains and witnesses | [Benchmark reference](https://github.com/raintree-technology/policystrata/blob/main/docs/benchmark-reference.md) |
| Runtime decisions and rollout modes | [Runtime controls](https://github.com/raintree-technology/policystrata/blob/main/docs/runtime-controls.md) |
| Trace schema and redaction | [Trace contract](https://github.com/raintree-technology/policystrata/blob/main/docs/trace-contract.md) |
| Packages and compatibility | [Distribution](https://github.com/raintree-technology/policystrata/blob/main/docs/distribution.md) |
| First adoption workflow | [Testing an AI data assistant](https://github.com/raintree-technology/policystrata/blob/main/docs/testing-ai-data-assistant.md) |

## Development

```bash
uv sync --extra dev
bun install --frozen-lockfile
bun run validate
```

[Contributing](https://github.com/raintree-technology/policystrata/blob/main/CONTRIBUTING.md) ·
[Security](https://github.com/raintree-technology/policystrata/blob/main/SECURITY.md) ·
[Changelog](https://github.com/raintree-technology/policystrata/blob/main/CHANGELOG.md) ·
[MIT License](https://github.com/raintree-technology/policystrata/blob/main/LICENSE)

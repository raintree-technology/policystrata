# PolicyStrata Agent Instructions

PolicyStrata is a research artifact for cross-layer policy regression testing in LLM data-agent stacks.

## Build And Test

- Use `uv run pytest` for tests.
- Use `uv run ruff check .` for lint.
- Use `uv run mypy src` for type checks.
- Do not require an LLM API key for deterministic tests or benchmark runs.
- Do not require host `psql`; Postgres access must go through Python or Docker.

## Design Rules

- Keep the policy oracle independent from the SQL compiler path.
- Treat constrained generation as a reliability layer, not an authorization boundary.
- Preserve JSON/YAML trace stability. Add fields compatibly.
- Keep the built-in `support_saas` domain deterministic and seed-driven.
- If adding external eval framework support, use adapters. Do not couple core execution to Inspect or BenchFlow.

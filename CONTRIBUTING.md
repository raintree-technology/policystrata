# Contributing

PolicyStrata is a deterministic research artifact. Keep changes reproducible, scoped, and explicit
about what the evidence does and does not prove.

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run mypy src
```

Optional PostgreSQL tests:

```bash
docker compose up -d postgres
POLICYSTRATA_RUN_DB_TESTS=1 uv run pytest tests/test_postgres_integration.py
```

- Keep the policy oracle independent from the SQL compiler path.
- Treat constrained generation as a reliability layer, not an authorization boundary.
- Preserve JSON/YAML trace stability. Add fields compatibly.
- Keep the built-in `support_saas` domain deterministic and seed-driven.
- Use adapters for external frameworks. Do not couple core execution to them.
- Do not require an LLM API key, hosted service, or host `psql` for deterministic tests.

When evidence behavior changes, regenerate the tables:

```bash
scripts/reproduce-evidence.sh
```

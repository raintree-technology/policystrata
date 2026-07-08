# Snowflake Text-to-SQL Fixture

This fixture models a Snowflake-backed text-to-SQL trace without requiring Snowflake credentials or
network access. It is a static imported-trace scanner example:

```bash
uv run policystrata scan \
  --config examples/integrations/snowflake_text_to_sql/policystrata.yaml \
  --out runs/snowflake-text-to-sql
```

The trace uses `source: snowflake_text_to_sql` and Snowflake-style warehouse schema qualifiers, but
PolicyStrata treats it as deterministic SQL evidence. Real Snowflake execution should live in a
separate, explicitly configured adapter or CI job with sanitized credentials.

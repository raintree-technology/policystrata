from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import psycopg

DEFAULT_DATABASE_URL = os.environ.get(
    "POLICYSTRATA_DATABASE_URL",
    "postgresql://policystrata:policystrata@localhost:55432/support_saas",
)
DEFAULT_APP_DATABASE_URL = os.environ.get(
    "POLICYSTRATA_APP_DATABASE_URL",
    "postgresql://policystrata_app:policystrata_app@localhost:55432/support_saas",
)
FORBIDDEN_SQL_TOKENS = {
    "alter",
    "call",
    "copy",
    "create",
    "delete",
    "do",
    "drop",
    "execute",
    "grant",
    "insert",
    "merge",
    "notify",
    "reindex",
    "reset",
    "revoke",
    "set",
    "truncate",
    "update",
    "vacuum",
}


class PostgresAdapter:
    def __init__(self, database_url: str = DEFAULT_DATABASE_URL) -> None:
        self.database_url = database_url

    def execute_script(self, path: Path) -> None:
        sql = path.read_text(encoding="utf-8")
        with psycopg.connect(self.database_url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(sql)

    def query(self, sql: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        assert_read_only_sql(sql)
        with (
            psycopg.connect(self.database_url) as conn,
            conn.cursor(row_factory=psycopg.rows.dict_row) as cur,
        ):
            if tenant_id is not None:
                cur.execute("select set_config('app.tenant_id', %s, true)", (tenant_id,))
            cur.execute(sql)
            return list(cur.fetchall())

    def load_fixture(self, schema: Path | None, seed: Path | None) -> None:
        if schema is not None:
            self.execute_script(schema)
        if seed is not None:
            self.execute_script(seed)


def assert_read_only_sql(sql: str) -> None:
    normalized = normalize_sql_for_safety(sql)
    if not normalized:
        raise ValueError("SQL must not be empty")
    if ";" in normalized.rstrip(";"):
        raise ValueError("SQL must contain at most one trailing semicolon")
    statement = normalized.rstrip(";").lstrip()
    lowered = statement.lower()
    if not (lowered.startswith("select ") or lowered.startswith("select\n") or lowered.startswith("with ")):
        raise ValueError("only read-only SELECT or WITH queries are allowed")
    match = re.search(r"\b(" + "|".join(sorted(FORBIDDEN_SQL_TOKENS)) + r")\b", lowered)
    if match is not None:
        raise ValueError(f"SQL contains forbidden token: {match.group(1)}")


def normalize_sql_for_safety(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    lines = []
    for line in without_block_comments.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()

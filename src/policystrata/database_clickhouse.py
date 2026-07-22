from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from policystrata.database import assert_read_only_sql, normalize_sql_for_safety

DEFAULT_CLICKHOUSE_URL = os.environ.get("POLICYSTRATA_CLICKHOUSE_URL", "http://localhost:8123/")
DEFAULT_CLICKHOUSE_USER = os.environ.get("POLICYSTRATA_CLICKHOUSE_USER", "policystrata")
DEFAULT_CLICKHOUSE_PASSWORD = os.environ.get("POLICYSTRATA_CLICKHOUSE_PASSWORD", "policystrata")
DEFAULT_CLICKHOUSE_DATABASE = os.environ.get("POLICYSTRATA_CLICKHOUSE_DATABASE", "policystrata")


class ClickHouseAdapter:
    """Adapter over the ClickHouse HTTP interface using only the standard library.

    Row-policy scoping happens at the connection level: every request authenticates
    as ``user``, so ``currentUser()`` in a row policy resolves to that user. The
    ``row_policies.sql`` fixture names its read-only users after project ids, which
    makes one adapter instance per scoped user the ClickHouse equivalent of the
    ``app.tenant_id`` session setting used by :class:`policystrata.database.PostgresAdapter`.
    """

    def __init__(
        self,
        url: str = DEFAULT_CLICKHOUSE_URL,
        user: str = DEFAULT_CLICKHOUSE_USER,
        password: str = DEFAULT_CLICKHOUSE_PASSWORD,
        database: str = DEFAULT_CLICKHOUSE_DATABASE,
    ) -> None:
        self.url = url
        self.user = user
        self.password = password
        self.database = database

    def execute_script(self, path: Path) -> None:
        for statement in split_sql_statements(path.read_text(encoding="utf-8")):
            self.execute_statement(statement)

    def execute_statement(self, sql: str) -> str:
        return self._request(sql)

    def query(self, sql: str) -> list[dict[str, Any]]:
        assert_read_only_sql(sql)
        payload = json.loads(self._request(sql, default_format="JSON"))
        if not isinstance(payload, dict):
            raise TypeError("expected a JSON object from ClickHouse")
        rows: list[dict[str, Any]] = []
        for row in payload.get("data", []):
            if not isinstance(row, dict):
                raise TypeError("expected JSON row objects from ClickHouse")
            rows.append(row)
        return rows

    def load_fixture(self, schema: Path | None, seed: Path | None) -> None:
        if schema is not None:
            self.execute_script(schema)
        if seed is not None:
            self.execute_script(seed)

    def _request(self, sql: str, default_format: str | None = None) -> str:
        params = {"database": self.database}
        if default_format is not None:
            params["default_format"] = default_format
        request_url = self.url.rstrip("/") + "/?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            request_url,
            data=sql.encode("utf-8"),
            method="POST",
            # Credentials travel in headers, never in the URL.
            headers={"X-ClickHouse-User": self.user, "X-ClickHouse-Key": self.password},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body: bytes = response.read()
                return body.decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"ClickHouse request failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ClickHouse is not reachable at {self.url}: {exc.reason}") from exc


def fixture_reader(user: str) -> ClickHouseAdapter:
    """Adapter for a read-only fixture user; row_policies.sql sets password == user name."""
    return ClickHouseAdapter(user=user, password=user)


def split_sql_statements(sql: str) -> list[str]:
    # The ClickHouse HTTP interface accepts one statement per request. Comments are
    # stripped first; fixture SQL keeps semicolons out of string literals.
    normalized = normalize_sql_for_safety(sql)
    return [statement.strip() for statement in normalized.split(";") if statement.strip()]

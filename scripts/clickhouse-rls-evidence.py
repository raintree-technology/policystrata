#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path

from policystrata.database_clickhouse import ClickHouseAdapter, fixture_reader
from policystrata.evidence import markdown_table

DOMAIN_ROOT = Path("src/policystrata/domains/analytics_clickhouse")


def main() -> int:
    admin = ClickHouseAdapter()
    admin.execute_script(DOMAIN_ROOT / "row_policies.sql")
    admin.execute_script(DOMAIN_ROOT / "seed.sql")

    rows = [
        evidence_row("project_acme_mobile", expected_projects={"project_acme_mobile"}, expected_rows=4),
        evidence_row("project_beta_web", expected_projects={"project_beta_web"}, expected_rows=1),
        evidence_row("policystrata_unscoped", expected_projects=set(), expected_rows=0),
    ]

    print(markdown_table(["ClickHouse check", "currentUser()", "Rows", "Project ids", "Result"], rows))
    return 0 if all(row[-1] == "pass" for row in rows) else 1


def evidence_row(user: str, expected_projects: set[str], expected_rows: int) -> list[str]:
    rows = fixture_reader(user).query("select project_id, event_name from events order by event_time")
    observed_projects = {str(row["project_id"]) for row in rows}
    passed = observed_projects == expected_projects and len(rows) == expected_rows
    return [
        "events row policy",
        user,
        str(len(rows)),
        ", ".join(sorted(observed_projects)) or "-",
        "pass" if passed else "fail",
    ]


if __name__ == "__main__":
    raise SystemExit(main())

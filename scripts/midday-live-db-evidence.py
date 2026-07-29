#!/usr/bin/env python
"""Execute midday's real row-level security policies and check containment with PolicyStrata.

Every brownfield result in docs/brownfield-results.md was static: PolicyStrata read SQL that real
projects had committed and reasoned about it without running anything. That leaves the obvious
question open -- would the checks notice if a real policy stopped working? This script answers it
for one target by loading midday's own CREATE POLICY statements into PostgreSQL and asking the
database what a team-scoped principal can see.

Two runs:

  intact    midday's 20 real policies, unmodified. Expect a clean gate.
  weakened  one real policy's predicate replaced with USING (true), which is the
            db_rls_old_ownership_field drift shape applied to real policy text. Expect the
            containment assertions to fail.

The second run is the one that carries weight. A checker that passes the first and also passes
the second is not checking anything. The weakened policy is a synthesized regression, not an
observed midday defect: midday's committed predicate is correct, and this script only shows what
PolicyStrata does when such a predicate stops binding.

Requires a PostgreSQL the script may create and drop databases on. Nothing here touches a
deployed system.

Usage:
    uv run python scripts/midday-live-db-evidence.py
    POLICYSTRATA_MIDDAY_ADMIN_URL=postgresql://user@host:5432/postgres \\
        uv run python scripts/midday-live-db-evidence.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from policystrata.evidence import markdown_table

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "brownfield" / "midday"
LIVE_DB = EXAMPLE / "live_db"
CONFIG = EXAMPLE / "policystrata_live_db.yaml"
DATABASE = "midday_live"

DEFAULT_ADMIN_URL = os.environ.get(
    "POLICYSTRATA_MIDDAY_ADMIN_URL",
    "postgresql://policystrata:policystrata@127.0.0.1:55432/postgres",
)

REAL_POLICY = "Team members can view their insights"
SECOND_REAL_POLICY = "Insights can be selected by a member of the team"
WEAKEN_SQL = f"""
DROP POLICY "{REAL_POLICY}" ON insights;
DROP POLICY "{SECOND_REAL_POLICY}" ON insights;
CREATE POLICY "{REAL_POLICY}" ON insights FOR SELECT TO public USING (true);
"""


def database_url(
    admin_url: str,
    database: str,
    *,
    user: str | None = None,
    password: str | None = None,
) -> str:
    params = conninfo_to_dict(admin_url)
    params["dbname"] = database
    if user is not None:
        params["user"] = user
    if password is not None:
        params["password"] = password
    normalized = {key: str(value) for key, value in params.items() if value is not None}
    return make_conninfo("", **normalized)


LOAD_ORDER = ("supabase_runtime.sql", "schema_scoped.sql", "seed.sql")


APP_ROLE_ATTRIBUTES = "login nosuperuser nocreatedb nocreaterole inherit noreplication nobypassrls"


def ensure_app_role(admin_url: str) -> None:
    """Provision the namespaced, non-owner principal used for RLS checks."""
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("select 1 from pg_roles where rolname = 'midday_app'")
        if cur.fetchone() is None:
            cur.execute(f"create role midday_app password 'midday_app' {APP_ROLE_ATTRIBUTES}")
            return
        cur.execute(f"alter role midday_app password 'midday_app' {APP_ROLE_ATTRIBUTES}")
        cur.execute("select 1 from pg_roles where rolname = 'authenticated'")
        if cur.fetchone() is not None:
            cur.execute("revoke authenticated from midday_app")


def reset_database(admin_url: str) -> None:
    """Recreate the fixture database and load the bridge, midday's real SQL, and the seed."""
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "select pg_terminate_backend(pid) from pg_stat_activity "
            "where datname = %s and pid <> pg_backend_pid()",
            (DATABASE,),
        )
        cur.execute(f'drop database if exists "{DATABASE}"')
        cur.execute(f'create database "{DATABASE}"')

    with (
        psycopg.connect(database_url(admin_url, DATABASE), autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        for name in LOAD_ORDER:
            cur.execute((LIVE_DB / name).read_text(encoding="utf-8"))


def loaded_policy_count(admin_url: str) -> int:
    with (
        psycopg.connect(database_url(admin_url, DATABASE)) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("select count(*) from pg_policies where schemaname = 'public'")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def weaken_policy(admin_url: str) -> None:
    with (
        psycopg.connect(database_url(admin_url, DATABASE), autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.execute(WEAKEN_SQL)


def run_scan(admin_url: str, out_dir: Path) -> tuple[int, list[dict[str, Any]]]:
    env = os.environ.copy()
    env["POLICYSTRATA_DATABASE_URL"] = database_url(admin_url, DATABASE)
    env["POLICYSTRATA_APP_DATABASE_URL"] = database_url(
        admin_url,
        DATABASE,
        user="midday_app",
        password="midday_app",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "policystrata",
            "scan",
            "--config",
            str(CONFIG),
            "--out",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    findings_path = out_dir / "findings.jsonl"
    findings: list[dict[str, Any]] = []
    if findings_path.exists():
        findings = [json.loads(line) for line in findings_path.read_text().splitlines() if line.strip()]
    if completed.returncode not in (0, 1):
        raise SystemExit(
            f"scan failed to run (exit {completed.returncode}):\n{completed.stdout}\n{completed.stderr}"
        )
    return completed.returncode, findings


def summarize(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "-"
    ids = sorted({f["id"] for f in findings})
    return ", ".join(ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-url", default=DEFAULT_ADMIN_URL)
    parser.add_argument("--out-root", type=Path, default=REPO_ROOT / "runs")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=REPO_ROOT / "studies" / "midday-live-db-evidence.json",
    )
    args = parser.parse_args()

    rows: list[list[str]] = []
    results: dict[str, dict[str, Any]] = {}

    ensure_app_role(args.admin_url)

    reset_database(args.admin_url)
    policies = loaded_policy_count(args.admin_url)
    if policies != 20:
        raise SystemExit(f"expected 20 real midday policies loaded, found {policies}")
    intact_exit, intact_findings = run_scan(
        args.admin_url,
        args.out_root / "brownfield-midday-live-intact",
    )
    intact_ok = intact_exit == 0 and not intact_findings
    rows.append(
        [
            "midday policies intact",
            "pass",
            "pass" if intact_exit == 0 else "fail",
            str(len(intact_findings)),
            summarize(intact_findings),
            "pass" if intact_ok else "fail",
        ]
    )
    results["intact"] = {
        "expected_gate": "pass",
        "observed_gate": "pass" if intact_exit == 0 else "fail",
        "findings": intact_findings,
        "result": "pass" if intact_ok else "fail",
    }

    reset_database(args.admin_url)
    weaken_policy(args.admin_url)
    weakened_exit, weakened_findings = run_scan(
        args.admin_url,
        args.out_root / "brownfield-midday-live-weakened",
    )
    failed = {f["id"] for f in weakened_findings}
    insights_failures = {i for i in failed if "insights_" in i}
    collateral = failed - insights_failures
    weakened_ok = weakened_exit == 1 and bool(insights_failures) and not collateral
    rows.append(
        [
            "one predicate weakened",
            "fail",
            "pass" if weakened_exit == 0 else "fail",
            str(len(weakened_findings)),
            summarize(weakened_findings),
            "pass" if weakened_ok else "fail",
        ]
    )
    results["weakened"] = {
        "expected_gate": "fail",
        "observed_gate": "pass" if weakened_exit == 0 else "fail",
        "findings": weakened_findings,
        "result": "pass" if weakened_ok else "fail",
    }

    table = markdown_table(
        ["Fixture", "Expected gate", "Observed gate", "Findings", "Finding ids", "Result"],
        rows,
    )
    print(table)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(
            {
                "target": "midday-ai/midday",
                "native_inputs": ["live_db/schema_scoped.sql"],
                "synthesized_inputs": ["live_db/supabase_runtime.sql", "live_db/seed.sql"],
                "real_policies_loaded": 20,
                "runs": results,
                "all_passed": intact_ok and weakened_ok,
            },
            indent=2,
        )
        + "\n"
    )
    return 0 if (intact_ok and weakened_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())

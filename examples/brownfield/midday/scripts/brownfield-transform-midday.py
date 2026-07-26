#!/usr/bin/env python3
"""Deterministic brownfield transform for midday-ai/midday: RLS schema concatenation.

midday's Postgres schema is defined as 39 ordered, numbered SQL migration files under
``packages/db/migrations/*NNNN_*.sql``. `DatabaseScanConfig.schema` (see
`src/policystrata/scan_models.py`) takes a single file path, so this script performs the
mechanical concatenation the brownfield inventory calls for: read every migration in numeric
filename order and concatenate them, byte for byte, into one ``schema.sql``, with a one-line
provenance comment before each migration's content naming its source file. No SQL is rewritten,
reordered within a file, or otherwise edited.

This schema.sql is a real, deterministic transform of native midday migration SQL. It is not
wired into `policystrata scan` in this brownfield pass (that would require a live PostgreSQL
fixture, out of scope here) -- see README.md for how it could be used with `policystrata doctor`
(static schema introspection, no live DB) or a future live-DB `scan` pass.

Usage:
    python brownfield-transform-midday.py --source <midday-clone> --out <example-dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path


def concatenate_migrations(migrations_dir: Path, source_root: Path) -> str:
    parts: list[str] = []
    for migration_path in sorted(migrations_dir.glob("*.sql")):
        relative = migration_path.relative_to(source_root).as_posix()
        parts.append(f"-- source: {relative}\n")
        parts.append(migration_path.read_text(encoding="utf-8").rstrip("\n"))
        parts.append("\n\n")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="path to the midday clone")
    parser.add_argument("--out", required=True, type=Path, help="path to examples/brownfield/midday")
    args = parser.parse_args()

    source_root: Path = args.source.resolve()
    out_root: Path = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    migrations_dir = source_root / "packages/db/migrations"

    migration_files = sorted(migrations_dir.glob("*.sql"))
    schema_sql = concatenate_migrations(migrations_dir, source_root)
    (out_root / "schema.sql").write_text(schema_sql, encoding="utf-8")

    print(f"concatenated {len(migration_files)} migrations into schema.sql")
    print(f"first: {migration_files[0].name}")
    print(f"last: {migration_files[-1].name}")


if __name__ == "__main__":
    main()

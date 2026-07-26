from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from policystrata.revision_replay import (
    load_replay_cases,
    render_report,
    replay_cases,
)


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_revision_replay_observes_absent_then_present_contract(tmp_path: Path) -> None:
    repository = tmp_path / "target"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "replay@example.test")
    _git(repository, "config", "user.name", "Replay Test")

    source = repository / "policy.sql"
    source.write_text("CREATE TABLE tenant_rows(id int);\n", encoding="utf-8")
    _git(repository, "add", "policy.sql")
    _git(repository, "commit", "-m", "create unprotected table")
    before = _git(repository, "rev-parse", "HEAD")

    source.write_text(
        "CREATE TABLE tenant_rows(id int);\n"
        "ALTER TABLE tenant_rows ENABLE ROW LEVEL SECURITY;\n",
        encoding="utf-8",
    )
    _git(repository, "add", "policy.sql")
    _git(repository, "commit", "-m", "enable tenant policy")
    after = _git(repository, "rev-parse", "HEAD")

    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "id": "missing-rls",
                        "before_revision": before,
                        "after_revision": after,
                        "surface": "database",
                        "witness_class": "over_permissive",
                        "taxonomy_operator": "app_deny_missing_db_policy",
                        "taxonomy_status": "mapped",
                        "probe": {
                            "pattern": "ENABLE ROW LEVEL SECURITY",
                            "paths": ["policy.sql"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    cases = load_replay_cases(manifest)
    results = replay_cases(repository, cases)
    report = render_report(repository, manifest, results)

    assert len(results) == 1
    assert results[0].reproduced is True
    assert results[0].before.matched is False
    assert results[0].after.matched is True
    assert report["reproduced"] == 1
    assert report["mapped_reproduced"] == 1


def test_revision_replay_requires_schema_version(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("cases: []\n", encoding="utf-8")

    try:
        load_replay_cases(manifest)
    except ValueError as error:
        assert "schema_version" in str(error)
    else:
        raise AssertionError("manifest without schema_version must fail")

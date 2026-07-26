"""Replay source-contract probes against exact Git revisions.

The replay is intentionally narrower than a full historical deployment. It asks whether a
declared policy-bearing source pattern is absent in the vulnerable revision and present in the
fix revision. The report preserves both Git object IDs and the matched source locations.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RevisionProbe:
    pattern: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class ReplayCase:
    id: str
    before_revision: str
    after_revision: str
    surface: str
    witness_class: str
    taxonomy_operator: str | None
    taxonomy_status: str
    probe: RevisionProbe


@dataclass(frozen=True)
class ProbeObservation:
    revision: str
    resolved_revision: str
    matched: bool
    matches: tuple[str, ...]


@dataclass(frozen=True)
class ReplayResult:
    id: str
    surface: str
    witness_class: str
    taxonomy_operator: str | None
    taxonomy_status: str
    before: ProbeObservation
    after: ProbeObservation
    reproduced: bool


def load_replay_cases(path: Path) -> list[ReplayCase]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("revision replay manifest must use schema_version: 1")

    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("revision replay manifest must contain at least one case")

    cases: list[ReplayCase] = []
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("each revision replay case must be a mapping")
        raw_probe = raw.get("probe")
        if not isinstance(raw_probe, dict):
            raise ValueError(f"{raw.get('id', '<unknown>')}: probe must be a mapping")
        paths = raw_probe.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(item, str) for item in paths):
            raise ValueError(f"{raw.get('id', '<unknown>')}: probe.paths must be a string list")

        operator = raw.get("taxonomy_operator")
        if operator is not None and not isinstance(operator, str):
            raise ValueError(f"{raw.get('id', '<unknown>')}: taxonomy_operator must be a string or null")

        cases.append(
            ReplayCase(
                id=_required_string(raw, "id"),
                before_revision=_required_string(raw, "before_revision"),
                after_revision=_required_string(raw, "after_revision"),
                surface=_required_string(raw, "surface"),
                witness_class=_required_string(raw, "witness_class"),
                taxonomy_operator=operator,
                taxonomy_status=_required_string(raw, "taxonomy_status"),
                probe=RevisionProbe(
                    pattern=_required_string(raw_probe, "pattern"),
                    paths=tuple(paths),
                ),
            )
        )
    return cases


def replay_cases(repository: Path, cases: list[ReplayCase]) -> list[ReplayResult]:
    _ensure_git_repository(repository)
    results: list[ReplayResult] = []
    for case in cases:
        before = _observe(repository, case.before_revision, case.probe)
        after = _observe(repository, case.after_revision, case.probe)
        results.append(
            ReplayResult(
                id=case.id,
                surface=case.surface,
                witness_class=case.witness_class,
                taxonomy_operator=case.taxonomy_operator,
                taxonomy_status=case.taxonomy_status,
                before=before,
                after=after,
                reproduced=not before.matched and after.matched,
            )
        )
    return results


def render_report(repository: Path, manifest: Path, results: list[ReplayResult]) -> dict[str, Any]:
    reproduced = sum(result.reproduced for result in results)
    mapped = sum(result.taxonomy_status == "mapped" for result in results)
    mapped_reproduced = sum(
        result.reproduced and result.taxonomy_status == "mapped" for result in results
    )
    return {
        "schema_version": 1,
        "repository": _portable_path(repository),
        "manifest": _portable_path(manifest),
        "cases": len(results),
        "reproduced": reproduced,
        "mapped_cases": mapped,
        "mapped_reproduced": mapped_reproduced,
        "results": [asdict(result) for result in results],
    }


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.name


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _ensure_git_repository(repository: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--git-dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"not a Git repository: {repository}")


def _observe(repository: Path, revision: str, probe: RevisionProbe) -> ProbeObservation:
    resolved = _resolve_revision(repository, revision)
    command = [
        "git",
        "-C",
        str(repository),
        "grep",
        "-n",
        "-E",
        probe.pattern,
        resolved,
        "--",
        *probe.paths,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or f"git grep failed for {revision}")
    matches = tuple(line for line in result.stdout.splitlines() if line)
    return ProbeObservation(
        revision=revision,
        resolved_revision=resolved,
        matched=bool(matches),
        matches=matches,
    )


def _resolve_revision(repository: Path, revision: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", f"{revision}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"unknown Git revision {revision!r} in {repository}")
    return result.stdout.strip()

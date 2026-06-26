from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

try:
    from importlib.resources.abc import Traversable
except ImportError:  # Python 3.10 exposes Traversable from importlib.abc.
    from importlib.abc import Traversable

from policystrata.domain import (
    domain_root,
    load_policy,
    load_suite_metadata,
    load_surface_config,
    load_tasks,
)
from policystrata.mutations import MUTATIONS

MANIFEST_VERSION = "policystrata.benchmark-manifest.v1"
FREEZE_HASH_FIELDS = (
    "manifest_version",
    "domain",
    "suite",
    "generated_count",
    "generated_seed",
    "policy_hash",
    "surfaces_hash",
    "suite_hash",
    "task_hash",
    "mutation_operator_hash",
    "detector_hash",
    "generator_hash",
)
VERIFY_FIELDS = FREEZE_HASH_FIELDS[1:]
DETECTOR_SOURCE_FILES = ("detection.py", "policy.py", "runner.py", "models.py")
GENERATOR_SOURCE_FILES = ("generator.py",)


def build_benchmark_manifest(
    domain: str,
    suite: str,
    base_path: Path | None = None,
    generated_count: int | None = None,
    generated_seed: int | None = None,
) -> dict[str, Any]:
    policy = load_policy(domain, base_path)
    surfaces = load_surface_config(domain, base_path)
    tasks = load_tasks(domain, suite, base_path, generated_count, generated_seed)
    suite_metadata = load_suite_metadata(domain, suite, base_path)
    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": domain,
        "suite": suite,
        "generated_count": generated_count,
        "generated_seed": generated_seed,
        "policy_version": policy.version,
        "surface_versions": surfaces.version_dict(),
        "suite_metadata": suite_metadata.model_dump(),
        "policy_hash": hash_domain_file(domain, base_path, "policy.yaml"),
        "surfaces_hash": hash_domain_file(domain, base_path, "surfaces.yaml"),
        "suite_hash": suite_hash(domain, suite, base_path, generated_count, generated_seed),
        "task_hash": sha256_json([task.model_dump(mode="json") for task in tasks]),
        "mutation_operator_hash": sha256_json(
            {mutation_id: spec.model_dump(mode="json") for mutation_id, spec in sorted(MUTATIONS.items())}
        ),
        "detector_hash": source_hash(DETECTOR_SOURCE_FILES),
        "generator_hash": source_hash(GENERATOR_SOURCE_FILES),
        "package_version": package_version(),
        "git_commit": git_commit(Path(__file__).resolve()),
    }
    manifest["benchmark_manifest_id"] = freeze_id(manifest)
    return manifest


def write_benchmark_manifest(
    domain: str,
    suite: str,
    out_path: Path,
    base_path: Path | None = None,
    generated_count: int | None = None,
    generated_seed: int | None = None,
) -> dict[str, Any]:
    manifest = build_benchmark_manifest(domain, suite, base_path, generated_count, generated_seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_benchmark_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"expected benchmark manifest mapping: {path}")
    if raw.get("manifest_version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported benchmark manifest version: {raw.get('manifest_version')}")
    return raw


def verify_benchmark_manifest(
    manifest_path: Path,
    domain: str | None = None,
    suite: str | None = None,
    base_path: Path | None = None,
    generated_count: int | None = None,
    generated_seed: int | None = None,
) -> dict[str, Any]:
    expected = load_benchmark_manifest(manifest_path)
    actual = build_benchmark_manifest(
        domain or str(expected["domain"]),
        suite or str(expected["suite"]),
        base_path,
        expected.get("generated_count") if generated_count is None else generated_count,
        expected.get("generated_seed") if generated_seed is None else generated_seed,
    )
    mismatches = [
        {"field": field, "expected": expected.get(field), "actual": actual.get(field)}
        for field in VERIFY_FIELDS
        if expected.get(field) != actual.get(field)
    ]
    verified = not mismatches and expected.get("benchmark_manifest_id") == freeze_id(expected)
    return {
        "verified": verified,
        "manifest": expected,
        "actual": actual,
        "mismatches": mismatches,
    }


def freeze_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_manifest_id": manifest["benchmark_manifest_id"],
        "detector_frozen": True,
        "detector_freeze_id": manifest["benchmark_manifest_id"],
        "detector_hash": manifest["detector_hash"],
        "mutation_operator_hash": manifest["mutation_operator_hash"],
        "generator_hash": manifest["generator_hash"],
        "policy_hash": manifest["policy_hash"],
        "surfaces_hash": manifest["surfaces_hash"],
        "suite_hash": manifest["suite_hash"],
        "task_hash": manifest["task_hash"],
    }


def freeze_id(manifest: dict[str, Any]) -> str:
    payload = {field: manifest.get(field) for field in FREEZE_HASH_FIELDS}
    return "psf-" + sha256_json(payload)[:20]


def suite_hash(
    domain: str,
    suite: str,
    base_path: Path | None,
    generated_count: int | None,
    generated_seed: int | None,
) -> str:
    suite_file = domain_file(domain, base_path, f"tasks/{suite}.yaml")
    if suite_file is not None:
        return sha256_bytes(suite_file.read_bytes())
    return sha256_json(
        {
            "domain": domain,
            "suite": suite,
            "generated_count": generated_count,
            "generated_seed": generated_seed,
        }
    )


def hash_domain_file(domain: str, base_path: Path | None, relative_path: str) -> str:
    file_ref = domain_file(domain, base_path, relative_path)
    if file_ref is None:
        raise FileNotFoundError(f"missing domain file: {relative_path}")
    return sha256_bytes(file_ref.read_bytes())


def domain_file(domain: str, base_path: Path | None, relative_path: str) -> Traversable | Path | None:
    if base_path is not None:
        path = base_path / relative_path
        return path if path.exists() else None
    path = domain_root(domain).joinpath(*relative_path.split("/"))
    return path if path.is_file() else None


def source_hash(file_names: tuple[str, ...]) -> str:
    root = Path(__file__).resolve().parent
    return sha256_json({name: sha256_bytes((root / name).read_bytes()) for name in file_names})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def package_version() -> str:
    try:
        return metadata.version("policystrata")
    except metadata.PackageNotFoundError:
        from policystrata import __version__

        return __version__


def git_commit(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path.parent,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None

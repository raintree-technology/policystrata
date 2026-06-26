from __future__ import annotations

import re
import shutil
from importlib import resources

try:
    from importlib.resources.abc import Traversable
except ImportError:  # Python 3.10 exposes Traversable from importlib.abc.
    from importlib.abc import Traversable
from pathlib import Path
from typing import Any

import yaml

from policystrata.generator import (
    CLEAN_CONTROLS_SUITE,
    DEFAULT_CLEAN_CONTROL_COUNT,
    DEFAULT_CLEAN_CONTROL_SEED,
    DEFAULT_GENERATED_ALT_SEED_COUNT,
    DEFAULT_GENERATED_ALT_SEED_SEED,
    DEFAULT_GENERATED_COUNT,
    DEFAULT_GENERATED_SEED,
    DEFAULT_HELDOUT_V1_COUNT,
    DEFAULT_HELDOUT_V1_SEED,
    GENERATED_ALT_SEED_SUITE,
    GENERATED_SUITE,
    HELD_OUT_SUITE,
    HELDOUT_V1_SUITE,
    MAX_GENERATED_COUNT,
    generate_clean_control_tasks,
    generate_tasks,
)
from policystrata.models import (
    MAX_SAFE_IDENTIFIER_LENGTH,
    SAFE_IDENTIFIER_PATTERN,
    Policy,
    SemanticQuery,
    SuiteMetadata,
    SurfaceConfig,
    SurfaceVersions,
    Task,
    WitnessClass,
)
from policystrata.mutations import get_mutation

BUILTIN_DOMAIN = "support_saas"
BUILTIN_DOMAINS = ("support_saas", "finance_saas", "analytics_clickhouse")
SUITE_NAME_PATTERN = SAFE_IDENTIFIER_PATTERN
MAX_SUITE_NAME_LENGTH = MAX_SAFE_IDENTIFIER_LENGTH


def domain_root(domain: str = BUILTIN_DOMAIN) -> Traversable:
    if domain not in BUILTIN_DOMAINS:
        raise ValueError(f"unknown built-in domain: {domain}")
    return resources.files("policystrata").joinpath("domains").joinpath(domain)


def load_yaml(path: Traversable | Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_yaml_mapping(path: Traversable | Path) -> dict[str, Any]:
    raw = load_yaml(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise TypeError(f"expected YAML mapping: {path}")
    return {str(key): value for key, value in raw.items()}


def load_policy(domain: str = BUILTIN_DOMAIN, base_path: Path | None = None) -> Policy:
    path: Traversable | Path
    path = base_path / "policy.yaml" if base_path else domain_root(domain).joinpath("policy.yaml")
    return Policy.model_validate(load_yaml_mapping(path))


def load_surfaces(domain: str = BUILTIN_DOMAIN, base_path: Path | None = None) -> SurfaceVersions:
    return load_surface_config(domain, base_path).versions


def load_surface_config(domain: str = BUILTIN_DOMAIN, base_path: Path | None = None) -> SurfaceConfig:
    path: Traversable | Path
    path = base_path / "surfaces.yaml" if base_path else domain_root(domain).joinpath("surfaces.yaml")
    return SurfaceConfig.model_validate(load_yaml_mapping(path))


def load_tasks(
    domain: str = BUILTIN_DOMAIN,
    suite: str = "seeded",
    base_path: Path | None = None,
    generated_count: int | None = None,
    generated_seed: int | None = None,
) -> list[Task]:
    suite = validate_suite_name(suite)
    if suite in {GENERATED_SUITE, GENERATED_ALT_SEED_SUITE, HELD_OUT_SUITE, HELDOUT_V1_SUITE}:
        policy = load_policy(domain, base_path)
        surfaces = load_surfaces(domain, base_path)
        count = generated_count
        seed = generated_seed
        if suite == GENERATED_SUITE:
            count = DEFAULT_GENERATED_COUNT if count is None else count
            seed = DEFAULT_GENERATED_SEED if seed is None else seed
        elif suite in {GENERATED_ALT_SEED_SUITE, HELD_OUT_SUITE}:
            count = DEFAULT_GENERATED_ALT_SEED_COUNT if count is None else count
            seed = DEFAULT_GENERATED_ALT_SEED_SEED if seed is None else seed
        else:
            count = DEFAULT_HELDOUT_V1_COUNT if count is None else count
            seed = DEFAULT_HELDOUT_V1_SEED if seed is None else seed
        return generate_tasks(domain, policy, surfaces, count=count, seed=seed)
    if suite == CLEAN_CONTROLS_SUITE:
        policy = load_policy(domain, base_path)
        surfaces = load_surfaces(domain, base_path)
        count = DEFAULT_CLEAN_CONTROL_COUNT if generated_count is None else generated_count
        seed = DEFAULT_CLEAN_CONTROL_SEED if generated_seed is None else generated_seed
        return generate_clean_control_tasks(domain, policy, surfaces, count=count, seed=seed)

    raw = load_suite_yaml(domain, suite, base_path)
    defaults = {
        "domain": domain,
        "policy_version": raw.get("policy_version", "v7"),
        "surface_versions": raw.get("surface_versions", {}),
    }
    tasks = [Task.model_validate({**defaults, **item}) for item in raw.get("tasks", [])]
    for item in raw.get("matrix", []):
        tasks.extend(expand_matrix_item(defaults, item))
    return tasks


def load_suite_metadata(
    domain: str = BUILTIN_DOMAIN,
    suite: str = "seeded",
    base_path: Path | None = None,
) -> SuiteMetadata:
    suite = validate_suite_name(suite)
    if suite == GENERATED_SUITE:
        return SuiteMetadata(
            provenance="generated",
            evidence_level="property_generated",
            notes=["deterministic generated suite from the public operator taxonomy"],
        )
    if suite in {GENERATED_ALT_SEED_SUITE, HELD_OUT_SUITE}:
        return SuiteMetadata(
            provenance="secondary_generated",
            evidence_level="property_generated",
            notes=[
                "secondary deterministic generated suite; not blinded unless detector-frozen "
                "metadata is supplied"
            ],
        )
    if suite == HELDOUT_V1_SUITE:
        return SuiteMetadata(
            provenance="secondary_generated",
            evidence_level="blinded_suite",
            authored_after_detector_freeze=True,
            notes=["deterministic held-out v1 suite generated after detector freeze"],
        )
    if suite == CLEAN_CONTROLS_SUITE:
        return SuiteMetadata(
            provenance="secondary_generated",
            evidence_level="blinded_suite",
            authored_after_detector_freeze=True,
            notes=["clean-control suite for false-positive accounting"],
        )

    raw = load_suite_yaml(domain, suite, base_path)
    metadata = raw.get("suite_metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise TypeError(f"expected suite_metadata mapping for suite {suite}")
    return SuiteMetadata.model_validate(metadata)


def load_suite_yaml(domain: str, suite: str, base_path: Path | None = None) -> dict[str, Any]:
    path: Traversable | Path
    if base_path:
        path = base_path / "tasks" / f"{suite}.yaml"
    else:
        path = domain_root(domain).joinpath("tasks").joinpath(f"{suite}.yaml")
    return load_yaml_mapping(path)


def expand_matrix_item(defaults: dict[str, Any], item: dict[str, Any]) -> list[Task]:
    mutation = get_mutation(str(item["mutation"]))
    count = validate_matrix_count(item.get("count", 1))
    task_list: list[Task] = []
    surface_versions = dict(defaults["surface_versions"])
    surface_versions.update(item.get("surface_versions", {}))
    for index in range(1, count + 1):
        query = dict(item["semantic_query"])
        variant = dict(item.get("variants", {}).get(index, {}))
        query.update(variant)
        task_id = f"{mutation.id}_{index:02d}"
        request_template = str(item["request"])
        request = request_template.format(index=index)
        task_list.append(
            Task(
                id=task_id,
                domain=defaults["domain"],
                principal=str(item.get("principal", "acme_analyst")),
                request=request,
                policy_version=str(defaults["policy_version"]),
                surface_versions=SurfaceVersions.model_validate(surface_versions),
                mutation=mutation.id,
                semantic_query=SemanticQuery.model_validate(query),
                expected_witness_class=WitnessClass(
                    item.get("expected_witness_class", mutation.witness_class)
                ),
                expected_localized_surface=item.get("expected_localized_surface", mutation.affected_surface),
                expected_containment_layer=item.get("expected_containment_layer", mutation.containment_layer),
            )
        )
    return task_list


def validate_suite_name(suite: str) -> str:
    if not isinstance(suite, str):
        raise TypeError("suite name must be a string")
    if len(suite) > MAX_SUITE_NAME_LENGTH or re.fullmatch(SUITE_NAME_PATTERN, suite) is None:
        raise ValueError(f"unsafe suite name: {suite}")
    return suite


def validate_matrix_count(count: Any) -> int:
    if not isinstance(count, int) or isinstance(count, bool):
        raise TypeError("matrix count must be an integer")
    if count < 1 or count > MAX_GENERATED_COUNT:
        raise ValueError(f"matrix count must be between 1 and {MAX_GENERATED_COUNT}: {count}")
    return count


def copy_domain(domain: str, destination: Path) -> Path:
    source = domain_root(domain)
    target = destination / domain
    if target.exists():
        raise FileExistsError(f"domain already exists: {target}")
    target.mkdir(parents=True)
    for child in source.iterdir():
        if child.is_dir():
            shutil.copytree(Path(str(child)), target / child.name)
        else:
            (target / child.name).write_text(child.read_text(encoding="utf-8"), encoding="utf-8")
    return target

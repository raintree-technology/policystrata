from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from policystrata.models import Decision, SurfaceName, WitnessClass

SURFACE_ORDER: tuple[SurfaceName, ...] = (
    "manifest",
    "grammar",
    "validator",
    "compiler",
    "database",
    "release",
)


@dataclass(frozen=True)
class WitnessDetection:
    witness_class: WitnessClass
    localized_surface: SurfaceName
    containment_layer: SurfaceName | None


def detect_witness(
    canonical: Decision,
    surface_decisions: Mapping[str, Decision],
    contract_decisions: Mapping[str, Decision],
    includes_tenant_predicate: bool,
    semantic_difference: bool,
    release_decision: Decision,
    db_result: Mapping[str, Any],
) -> WitnessDetection:
    localized_surface = first_contract_violation(contract_decisions)
    if localized_surface is None:
        localized_surface = first_surface_mismatch(canonical, surface_decisions)

    if localized_surface is None:
        if release_decision.allowed and not canonical.allowed:
            return WitnessDetection(WitnessClass.UNSAFE_RELEASE, "release", None)
        return WitnessDetection(WitnessClass.CLEAN, "release", None)

    containment_layer = contained_surface(contract_decisions, db_result)
    witness_class = classify_witness(
        localized_surface=localized_surface,
        canonical=canonical,
        surface_decisions=surface_decisions,
        includes_tenant_predicate=includes_tenant_predicate,
        semantic_difference=semantic_difference,
        release_decision=release_decision,
    )
    return WitnessDetection(witness_class, localized_surface, containment_layer)


def first_contract_violation(contract_decisions: Mapping[str, Decision]) -> SurfaceName | None:
    for surface in SURFACE_ORDER:
        decision = contract_decisions.get(surface)
        if decision is not None and not decision.allowed:
            return surface
    return None


def first_surface_mismatch(
    canonical: Decision,
    surface_decisions: Mapping[str, Decision],
) -> SurfaceName | None:
    for surface in SURFACE_ORDER:
        decision = surface_decisions.get(surface)
        if decision is not None and decision.allowed != canonical.allowed:
            return surface
    return None


def contained_surface(
    contract_decisions: Mapping[str, Decision],
    db_result: Mapping[str, Any],
) -> SurfaceName | None:
    for surface in SURFACE_ORDER:
        decision = contract_decisions.get(surface)
        if decision is None or not decision.allowed:
            continue
        if any("contained a downstream obligation violation" in reason for reason in decision.reasons):
            return surface

    if db_result.get("blocked_by_database") is True:
        return "database"
    return None


def classify_witness(
    localized_surface: SurfaceName,
    canonical: Decision,
    surface_decisions: Mapping[str, Decision],
    includes_tenant_predicate: bool,
    semantic_difference: bool,
    release_decision: Decision,
) -> WitnessClass:
    localized_decision = surface_decisions.get(localized_surface)

    if canonical.allowed and localized_decision is not None and not localized_decision.allowed:
        return WitnessClass.OVER_RESTRICTIVE
    if not canonical.allowed and localized_decision is not None and localized_decision.allowed:
        return WitnessClass.OVER_PERMISSIVE
    if localized_surface == "compiler" and not includes_tenant_predicate:
        return WitnessClass.LOWERING_VIOLATION
    if localized_surface == "compiler" and semantic_difference:
        return WitnessClass.SEMANTIC_DRIFT
    if localized_surface == "database":
        return WitnessClass.OVER_PERMISSIVE
    if localized_surface == "release" and release_decision.allowed:
        return WitnessClass.UNSAFE_RELEASE
    if release_decision.allowed and not canonical.allowed:
        return WitnessClass.UNSAFE_RELEASE
    if semantic_difference:
        return WitnessClass.SEMANTIC_DRIFT
    return WitnessClass.CLEAN

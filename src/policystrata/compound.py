"""Higher-order (compound) mutation study.

Real policy drift is often compound: a stale model-visible manifest and a
stale compiler tenant key can be live at the same time. The deterministic
benchmark injects exactly one operator per case, so it never exercises how
first-transition attribution behaves when several surfaces are skewed at once.

This module composes 2+ single-surface skews into one case and measures two
things the review asked for:

* detection - is any witness still produced (the compound mutant is killed)?
* attribution - does the detector still localize the case to the *earliest*
  violating surface in ``SURFACE_ORDER`` (first-transition attribution), or does
  composition degrade it?

Composition model and its limits
--------------------------------
A compound case is modeled as the **union of independent single-surface
skews**: each constituent mutation is evaluated on its own with the existing
:func:`policystrata.runner.evaluate_task`, and the per-surface contract
violations are merged (a surface violates its contract in the compound case iff
it violates it in any constituent). This faithfully models compositions across
*distinct* surfaces - the case the review named ("stale manifest and stale
compiler key simultaneously"). It does **not** model non-linear interaction
between two skews on the *same* surface (e.g. two compiler rewrites on one
query), which would require threading multiple mutations through the compiler
and DB simulator; that is left to future work and compound cases are generated
only across distinct surfaces.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from policystrata.detection import first_contract_violation
from policystrata.models import (
    Decision,
    InputModel,
    Policy,
    SemanticQuery,
    SurfaceConfig,
    SurfaceName,
    SurfaceVersions,
    Task,
    Trace,
    WitnessClass,
)
from policystrata.mutations import (
    CompoundExpectation,
    compound_expectations,
    get_mutation,
    surface_position,
)
from policystrata.runner import SURFACES, evaluate_task

CONTAINMENT_REASON = "contained a downstream obligation violation"


class CompoundCase(InputModel):
    """A single case carrying two or more simultaneous single-surface skews."""

    id: str
    domain: str = "support_saas"
    principal: str
    request: str
    policy_version: str
    surface_versions: SurfaceVersions
    mutations: list[str] = Field(min_length=2)
    semantic_query: SemanticQuery

    def ordered_mutations(self) -> list[str]:
        specs = [get_mutation(m) for m in self.mutations]
        ordered = sorted(specs, key=lambda spec: surface_position(spec.affected_surface))
        return [spec.id for spec in ordered]


class CompoundResult(InputModel):
    case_id: str
    domain: str
    mutations: list[str]
    affected_surfaces: list[SurfaceName]
    detected: bool
    observed_first_transition: SurfaceName | None
    expected_first_transition: SurfaceName
    attribution_correct: bool
    observed_witness_class: WitnessClass | None
    expected_witness_class: WitnessClass
    class_correct: bool
    observed_containment_layer: SurfaceName | None
    expected_containment_layer: SurfaceName | None
    containment_correct: bool
    constituent_surfaces: list[SurfaceName]


class CompoundReport(InputModel):
    total: int
    detected: int
    attribution_correct: int
    class_correct: int
    detection_rate: float
    attribution_accuracy: float
    class_accuracy: float
    results: list[CompoundResult]


def _sub_task(case: CompoundCase, mutation_id: str) -> Task:
    """Build a single-mutation task for one constituent of a compound case.

    The affected surface version is bumped to reflect the skew, mirroring the
    generator's ``-gen`` marker so the constituent looks like a real drifted
    surface rather than the canonical version.
    """
    spec = get_mutation(mutation_id)
    versions = case.surface_versions.as_dict()
    surface = spec.affected_surface
    bumped = case.surface_versions.model_copy(update={surface: f"{versions[surface]}-compound"})
    return Task(
        id=f"{case.id}__{mutation_id}",
        domain=case.domain,
        principal=case.principal,
        request=case.request,
        policy_version=case.policy_version,
        surface_versions=bumped,
        mutation=mutation_id,
        semantic_query=case.semantic_query,
        expected_witness_class=WitnessClass(spec.witness_class),
        expected_localized_surface=spec.affected_surface,
        expected_containment_layer=spec.containment_layer,
    )


def merge_contract_decisions(sub_traces: Sequence[Trace]) -> dict[str, Decision]:
    """Merge per-constituent contract decisions.

    A surface violates its contract in the compound case iff it violates it in
    any constituent; containment is preserved only when no constituent violates
    that surface.
    """
    merged: dict[str, Decision] = {}
    for surface in SURFACES:
        decisions = [trace.contract_decisions.get(surface) for trace in sub_traces]
        present = [decision for decision in decisions if decision is not None]
        violated = [decision for decision in present if not decision.allowed]
        if violated:
            reasons: list[str] = []
            for decision in violated:
                reasons.extend(decision.reasons)
            merged[surface] = Decision(allowed=False, reasons=reasons)
            continue
        contained = [
            decision
            for decision in present
            if any(CONTAINMENT_REASON in reason for reason in decision.reasons)
        ]
        merged[surface] = contained[0] if contained else Decision(allowed=True, reasons=[])
    return merged


def evaluate_compound_case(
    policy: Policy,
    case: CompoundCase,
    surface_config: SurfaceConfig,
) -> CompoundResult:
    specs = [get_mutation(mutation_id) for mutation_id in case.mutations]
    expectation = compound_expectations(specs)

    sub_traces = [evaluate_task(policy, _sub_task(case, m), surface_config) for m in case.mutations]
    merged = merge_contract_decisions(sub_traces)
    observed_first = first_contract_violation(merged)

    non_clean = [trace for trace in sub_traces if trace.witness_class != WitnessClass.CLEAN]
    detected = bool(non_clean)

    observed_class: WitnessClass | None = None
    observed_containment: SurfaceName | None = None
    if non_clean:
        earliest = min(non_clean, key=lambda trace: surface_position(trace.localized_surface))
        observed_class = earliest.witness_class
        affected = {spec.affected_surface for spec in specs if spec.witness_class != WitnessClass.CLEAN}
        if earliest.containment_layer is not None and earliest.containment_layer not in affected:
            observed_containment = earliest.containment_layer

    return CompoundResult(
        case_id=case.id,
        domain=case.domain,
        mutations=list(case.mutations),
        affected_surfaces=sorted(expectation.affected_surfaces, key=surface_position),
        detected=detected,
        observed_first_transition=observed_first,
        expected_first_transition=expectation.localized_surface,
        attribution_correct=observed_first == expectation.localized_surface,
        observed_witness_class=observed_class,
        expected_witness_class=expectation.witness_class,
        class_correct=observed_class == expectation.witness_class,
        observed_containment_layer=observed_containment,
        expected_containment_layer=expectation.containment_layer,
        containment_correct=observed_containment == expectation.containment_layer,
        constituent_surfaces=[spec.affected_surface for spec in specs],
    )


def summarize_compound(results: Sequence[CompoundResult]) -> CompoundReport:
    total = len(results)
    detected = sum(1 for result in results if result.detected)
    attribution = sum(1 for result in results if result.attribution_correct)
    class_ok = sum(1 for result in results if result.class_correct)
    return CompoundReport(
        total=total,
        detected=detected,
        attribution_correct=attribution,
        class_correct=class_ok,
        detection_rate=detected / total if total else 0.0,
        attribution_accuracy=attribution / total if total else 0.0,
        class_accuracy=class_ok / total if total else 0.0,
        results=list(results),
    )


def _distinct_surface(spec_a: str, spec_b: str) -> bool:
    return get_mutation(spec_a).affected_surface != get_mutation(spec_b).affected_surface


def generate_compound_cases(
    domain: str,
    policy: Policy,
    surface_versions: SurfaceVersions,
    mutation_ids: Sequence[str],
    order: int = 2,
    count: int = 60,
    seed: int = 424242,
) -> list[CompoundCase]:
    """Generate compound cases by combining ``order`` distinct-surface skews.

    Cases are drawn deterministically. Only combinations across *distinct*
    surfaces are produced (see the module docstring for why same-surface
    composition is out of scope).
    """
    import random

    from policystrata.generator import query_for_mutation, select_restricted_principal

    if order < 2:
        raise ValueError("compound order must be at least 2")
    rng = random.Random(seed)
    principal = select_restricted_principal(policy)
    pool = [m for m in mutation_ids if get_mutation(m).witness_class != WitnessClass.CLEAN]

    cases: list[CompoundCase] = []
    seen: set[tuple[str, ...]] = set()
    attempts = 0
    max_attempts = count * 50
    while len(cases) < count and attempts < max_attempts:
        attempts += 1
        picked = rng.sample(pool, order) if len(pool) >= order else pool
        surfaces: set[SurfaceName] = {get_mutation(m).affected_surface for m in picked}
        if len(surfaces) != len(picked):
            continue
        key = tuple(sorted(picked))
        if key in seen:
            continue
        seen.add(key)
        ordered = sorted(picked, key=lambda m: surface_position(get_mutation(m).affected_surface))
        primary = ordered[0]
        query = query_for_mutation(policy, principal, primary, rng)
        versions = surface_versions
        sorted_surfaces = sorted(surfaces, key=surface_position)
        request = (
            f"Compound drift case {len(cases) + 1}: simultaneous skews on "
            f"{', '.join(sorted_surfaces)}."
        )
        cases.append(
            CompoundCase(
                id=f"compound_{len(cases) + 1:04d}",
                domain=domain,
                principal=principal.id,
                request=request,
                policy_version=policy.version,
                surface_versions=versions,
                mutations=ordered,
                semantic_query=query,
            )
        )
    return cases


def default_compound_report(
    domain: str,
    policy: Policy,
    surface_config: SurfaceConfig,
    mutation_ids: Sequence[str],
    orders: Sequence[int] = (2, 3),
    per_order: int = 60,
) -> CompoundReport:
    results: list[CompoundResult] = []
    for order in orders:
        cases = generate_compound_cases(
            domain,
            policy,
            surface_config.versions,
            mutation_ids,
            order=order,
            count=per_order,
            seed=424242 + order,
        )
        results.extend(evaluate_compound_case(policy, case, surface_config) for case in cases)
    return summarize_compound(results)


def run_compound_study(
    domain: str,
    orders: Sequence[int] = (2, 3),
    per_order: int = 60,
    base_path: object | None = None,
) -> CompoundReport:
    """Load a domain and produce a compound-mutation report."""
    from pathlib import Path

    from policystrata.domain import load_policy, load_surface_config
    from policystrata.generator import mutation_ids_for_domain

    resolved: Path | None = base_path if isinstance(base_path, Path) else None
    policy = load_policy(domain, resolved)
    surface_config = load_surface_config(domain, resolved)
    mutation_ids = mutation_ids_for_domain(domain)
    return default_compound_report(domain, policy, surface_config, mutation_ids, orders, per_order)


def _unused_expectation(expectation: CompoundExpectation) -> CompoundExpectation:  # pragma: no cover
    return expectation

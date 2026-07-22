"""Counterfactual-repair validation of first-transition attribution.

Plain localization accuracy (``localized_surface == expected_localized_surface``)
compares two labels that both come from the operator taxonomy, so a perfect
score is circular: it only says the detector reproduces the injection label.

Counterfactual repair is an *interventional* check instead. For a case whose
witness is attributed to surface A, it verifies two causal claims:

* **Sufficiency** - remove the skew on A (repair the attributed layer) and the
  A-witness must disappear (attribution moves off A, or the case goes clean).
  If it does not, A was not actually responsible for the A-witness.
* **Necessity** - remove a skew on some *other* surface B while leaving A, and
  attribution must stay on A. If removing B changes the attribution, then B -
  not A - was driving it, and the original attribution was wrong.

Both directions are only testable when more than one surface is skewed, so this
validation runs over compound cases (see :mod:`policystrata.compound`). For a
single-surface case only sufficiency is defined (repairing the one skew yields a
clean run), and it is reported separately.
"""

from __future__ import annotations

from collections.abc import Sequence

from policystrata.compound import CompoundCase, merge_contract_decisions
from policystrata.detection import first_contract_violation
from policystrata.models import (
    InputModel,
    Policy,
    SurfaceConfig,
    SurfaceName,
    Task,
    WitnessClass,
)
from policystrata.mutations import get_mutation, surface_position
from policystrata.runner import evaluate_task


class RepairOutcome(InputModel):
    removed_surface: SurfaceName
    removed_mutation: str
    role: str  # "attributed" or "non_attributed"
    first_transition_after: SurfaceName | None
    detected_after: bool
    # For an attributed repair we expect the attributed surface to no longer be
    # the first transition (sufficiency). For a non-attributed repair we expect
    # the first transition to remain the attributed surface (necessity).
    expectation_met: bool


class CounterfactualResult(InputModel):
    case_id: str
    domain: str
    mutations: list[str]
    attributed_surface: SurfaceName
    baseline_detected: bool
    sufficiency_holds: bool
    necessity_holds: bool
    counterfactual_valid: bool
    repairs: list[RepairOutcome]


class CounterfactualReport(InputModel):
    total: int
    valid: int
    sufficiency_holds: int
    necessity_holds: int
    validity_rate: float
    sufficiency_rate: float
    necessity_rate: float
    results: list[CounterfactualResult]


def _attribute(
    policy: Policy,
    case: CompoundCase,
    mutation_ids: Sequence[str],
    surface_config: SurfaceConfig,
) -> tuple[SurfaceName | None, bool]:
    """Attribute a case under an arbitrary (possibly reduced) mutation set."""
    if not mutation_ids:
        return None, False
    sub_traces = []
    for mutation_id in mutation_ids:
        spec = get_mutation(mutation_id)
        versions = case.surface_versions.as_dict()
        surface = spec.affected_surface
        bumped = case.surface_versions.model_copy(
            update={surface: f"{versions[surface]}-cf"}
        )
        task = Task(
            id=f"{case.id}__cf__{mutation_id}",
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
        sub_traces.append(evaluate_task(policy, task, surface_config))
    merged = merge_contract_decisions(sub_traces)
    first = first_contract_violation(merged)
    detected = any(trace.witness_class != WitnessClass.CLEAN for trace in sub_traces)
    return first, detected


def validate_case(
    policy: Policy,
    case: CompoundCase,
    surface_config: SurfaceConfig,
) -> CounterfactualResult:
    mutations = case.ordered_mutations()
    attributed, baseline_detected = _attribute(policy, case, mutations, surface_config)
    if attributed is None:
        # No witness at all; nothing to validate causally.
        return CounterfactualResult(
            case_id=case.id,
            domain=case.domain,
            mutations=mutations,
            attributed_surface="release",
            baseline_detected=False,
            sufficiency_holds=False,
            necessity_holds=False,
            counterfactual_valid=False,
            repairs=[],
        )

    attributed_mutation = next(
        (m for m in mutations if get_mutation(m).affected_surface == attributed), None
    )
    if attributed_mutation is None:
        # Attribution named a surface that is not even skewed in this case: the
        # attribution cannot be causally supported, so it fails validation.
        return CounterfactualResult(
            case_id=case.id,
            domain=case.domain,
            mutations=mutations,
            attributed_surface=attributed,
            baseline_detected=baseline_detected,
            sufficiency_holds=False,
            necessity_holds=False,
            counterfactual_valid=False,
            repairs=[],
        )
    repairs: list[RepairOutcome] = []

    # Sufficiency: repair the attributed layer.
    remaining = [m for m in mutations if m != attributed_mutation]
    first_after, detected_after = _attribute(policy, case, remaining, surface_config)
    sufficiency = first_after != attributed
    repairs.append(
        RepairOutcome(
            removed_surface=attributed,
            removed_mutation=attributed_mutation,
            role="attributed",
            first_transition_after=first_after,
            detected_after=detected_after,
            expectation_met=sufficiency,
        )
    )

    # Necessity: repair each non-attributed layer individually.
    necessity = True
    for mutation_id in mutations:
        if mutation_id == attributed_mutation:
            continue
        surface = get_mutation(mutation_id).affected_surface
        reduced = [m for m in mutations if m != mutation_id]
        first_after, detected_after = _attribute(policy, case, reduced, surface_config)
        met = first_after == attributed
        necessity = necessity and met
        repairs.append(
            RepairOutcome(
                removed_surface=surface,
                removed_mutation=mutation_id,
                role="non_attributed",
                first_transition_after=first_after,
                detected_after=detected_after,
                expectation_met=met,
            )
        )

    return CounterfactualResult(
        case_id=case.id,
        domain=case.domain,
        mutations=mutations,
        attributed_surface=attributed,
        baseline_detected=baseline_detected,
        sufficiency_holds=sufficiency,
        necessity_holds=necessity,
        counterfactual_valid=sufficiency and necessity,
        repairs=repairs,
    )


def summarize_counterfactual(
    results: Sequence[CounterfactualResult],
) -> CounterfactualReport:
    total = len(results)
    valid = sum(1 for result in results if result.counterfactual_valid)
    sufficiency = sum(1 for result in results if result.sufficiency_holds)
    necessity = sum(1 for result in results if result.necessity_holds)
    return CounterfactualReport(
        total=total,
        valid=valid,
        sufficiency_holds=sufficiency,
        necessity_holds=necessity,
        validity_rate=valid / total if total else 0.0,
        sufficiency_rate=sufficiency / total if total else 0.0,
        necessity_rate=necessity / total if total else 0.0,
        results=list(results),
    )


def run_counterfactual_study(
    domain: str,
    orders: Sequence[int] = (2, 3),
    per_order: int = 60,
    base_path: object | None = None,
) -> CounterfactualReport:
    from pathlib import Path

    from policystrata.compound import generate_compound_cases
    from policystrata.domain import load_policy, load_surface_config
    from policystrata.generator import mutation_ids_for_domain

    resolved: Path | None = base_path if isinstance(base_path, Path) else None
    policy = load_policy(domain, resolved)
    surface_config = load_surface_config(domain, resolved)
    mutation_ids = mutation_ids_for_domain(domain)

    results: list[CounterfactualResult] = []
    for order in orders:
        cases = generate_compound_cases(
            domain,
            policy,
            surface_config.versions,
            mutation_ids,
            order=order,
            count=per_order,
            seed=515151 + order,
        )
        results.extend(validate_case(policy, case, surface_config) for case in cases)
    return summarize_counterfactual(results)


def order_by_surface(mutation_ids: Sequence[str]) -> list[str]:
    return sorted(mutation_ids, key=lambda m: surface_position(get_mutation(m).affected_surface))

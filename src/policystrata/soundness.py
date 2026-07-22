"""Soundness invariant and per-fault-class completeness characterization.

**Soundness** (the direction the review named - "a witness implies a contract
violation"): whenever the detector emits a non-clean witness, either some
surface's declared contract was violated, or the release layer let an
unauthorized result out (an unsafe release, which is itself the release
contract's violation). Formally, for every trace:

    witness != CLEAN  =>  (exists surface with contract_decisions[surface] denied)
                          or (release allowed while canonical denied)

:func:`witness_implies_contract_violation` is that predicate; the property tests
exercise it over the operator taxonomy with Hypothesis.

**Completeness** is characterized per fault class rather than claimed globally:
each operator family declares the surface it skews and the witness class it
should produce, and :func:`completeness_by_class` groups the taxonomy that way so
the guarantee ("this class of fault is localized to this surface") and its scope
(only faults expressible as one of these operators) are explicit.
"""

from __future__ import annotations

from policystrata.models import InputModel, Trace, WitnessClass
from policystrata.mutations import MUTATIONS


def witness_implies_contract_violation(trace: Trace) -> bool:
    """The soundness invariant for a single trace."""
    if trace.witness_class == WitnessClass.CLEAN:
        return True
    has_contract_violation = any(
        not decision.allowed for decision in trace.contract_decisions.values()
    )
    unsafe_release = trace.release_decision.allowed and not trace.canonical_decision.allowed
    return has_contract_violation or unsafe_release


class FaultClassCoverage(InputModel):
    witness_class: WitnessClass
    operators: list[str]
    surfaces: list[str]


def completeness_by_class() -> list[FaultClassCoverage]:
    """Group the operator taxonomy by the witness class it is designed to raise."""
    by_class: dict[WitnessClass, list[str]] = {}
    surfaces: dict[WitnessClass, set[str]] = {}
    for operator_id, spec in sorted(MUTATIONS.items()):
        witness_class = WitnessClass(spec.witness_class)
        by_class.setdefault(witness_class, []).append(operator_id)
        surfaces.setdefault(witness_class, set()).add(spec.affected_surface)
    return [
        FaultClassCoverage(
            witness_class=witness_class,
            operators=sorted(operators),
            surfaces=sorted(surfaces[witness_class]),
        )
        for witness_class, operators in sorted(by_class.items(), key=lambda item: item[0].value)
    ]


class OperatorContract(InputModel):
    operator: str
    affected_surface: str
    witness_class: WitnessClass
    containment_layer: str | None
    description: str


def operator_contract_map() -> list[OperatorContract]:
    """Flat operator -> (surface, witness class, containment) mapping."""
    return [
        OperatorContract(
            operator=operator_id,
            affected_surface=spec.affected_surface,
            witness_class=WitnessClass(spec.witness_class),
            containment_layer=spec.containment_layer,
            description=spec.description,
        )
        for operator_id, spec in sorted(MUTATIONS.items())
    ]

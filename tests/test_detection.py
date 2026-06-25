from policystrata.detection import detect_witness
from policystrata.models import Decision, WitnessClass


def test_detects_over_permissive_surface_acceptance() -> None:
    detection = detect_witness(
        canonical=Decision(allowed=False, reasons=["metric not allowed"]),
        surface_decisions={"manifest": Decision(allowed=True)},
        contract_decisions={"manifest": Decision(allowed=False, reasons=["manifest violated"])},
        includes_tenant_predicate=True,
        semantic_difference=False,
        release_decision=Decision(allowed=True),
        db_result={"blocked_by_database": False},
    )

    assert detection.witness_class == WitnessClass.OVER_PERMISSIVE
    assert detection.localized_surface == "manifest"
    assert detection.containment_layer is None


def test_detects_lowering_violation_before_semantic_drift() -> None:
    detection = detect_witness(
        canonical=Decision(allowed=True),
        surface_decisions={"compiler": Decision(allowed=True)},
        contract_decisions={
            "compiler": Decision(allowed=False, reasons=["tenant-scope obligation was not preserved"]),
            "database": Decision(
                allowed=True,
                reasons=["database contained a downstream obligation violation"],
            ),
        },
        includes_tenant_predicate=False,
        semantic_difference=True,
        release_decision=Decision(allowed=False, reasons=["contained by database"]),
        db_result={"blocked_by_database": True},
    )

    assert detection.witness_class == WitnessClass.LOWERING_VIOLATION
    assert detection.localized_surface == "compiler"
    assert detection.containment_layer == "database"


def test_authorization_drift_wins_over_simulated_value_difference() -> None:
    detection = detect_witness(
        canonical=Decision(allowed=False, reasons=["limit exceeds max rows"]),
        surface_decisions={"compiler": Decision(allowed=True)},
        contract_decisions={"compiler": Decision(allowed=False, reasons=["compiler violated"])},
        includes_tenant_predicate=True,
        semantic_difference=True,
        release_decision=Decision(allowed=True),
        db_result={"blocked_by_database": False},
    )

    assert detection.witness_class == WitnessClass.OVER_PERMISSIVE
    assert detection.localized_surface == "compiler"


def test_clean_when_no_surface_or_contract_disagrees() -> None:
    detection = detect_witness(
        canonical=Decision(allowed=True),
        surface_decisions={"validator": Decision(allowed=True)},
        contract_decisions={"validator": Decision(allowed=True)},
        includes_tenant_predicate=True,
        semantic_difference=False,
        release_decision=Decision(allowed=True),
        db_result={"blocked_by_database": False},
    )

    assert detection.witness_class == WitnessClass.CLEAN

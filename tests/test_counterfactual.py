from __future__ import annotations

from collections.abc import Mapping

import pytest

import policystrata.counterfactual as cf
from policystrata.compound import CompoundCase
from policystrata.counterfactual import (
    run_counterfactual_study,
    summarize_counterfactual,
    validate_case,
)
from policystrata.domain import load_policy, load_surface_config
from policystrata.models import Decision, Policy, SemanticQuery, SurfaceConfig, SurfaceName


def support() -> tuple[Policy, SurfaceConfig]:
    return load_policy("support_saas"), load_surface_config("support_saas")


def a_case(mutations: list[str]) -> CompoundCase:
    policy, surfaces = support()
    principal = next(p.id for p in policy.principals.values() if "admin" not in p.role)
    return CompoundCase(
        id="cf_case",
        domain="support_saas",
        principal=principal,
        request="counterfactual test",
        policy_version=policy.version,
        surface_versions=surfaces.versions,
        mutations=mutations,
        semantic_query=SemanticQuery(metric="ticket_count"),
    )


def test_sufficiency_and_necessity_hold_for_valid_attribution() -> None:
    policy, surfaces = support()
    case = a_case(["stale_metric_alias_manifest", "grammar_permits_forbidden_dimension"])
    result = validate_case(policy, case, surfaces)
    assert result.attributed_surface == "manifest"
    assert result.sufficiency_holds is True
    assert result.necessity_holds is True
    assert result.counterfactual_valid is True
    attributed_repair = next(r for r in result.repairs if r.role == "attributed")
    assert attributed_repair.first_transition_after == "grammar"
    other_repair = next(r for r in result.repairs if r.role == "non_attributed")
    assert other_repair.first_transition_after == "manifest"


def test_full_study_reports_validity() -> None:
    report = run_counterfactual_study("support_saas", orders=(2, 3), per_order=20)
    assert report.total == 40
    assert report.validity_rate == 1.0
    assert report.sufficiency_rate == 1.0
    assert report.necessity_rate == 1.0


def test_check_has_teeth_broken_attribution_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    policy, surfaces = support()
    case = a_case(["stale_metric_alias_manifest", "grammar_permits_forbidden_dimension"])

    def constant_attribution(_decisions: Mapping[str, Decision]) -> SurfaceName:
        return "database"

    monkeypatch.setattr(cf, "first_contract_violation", constant_attribution)
    result = validate_case(policy, case, surfaces)
    assert result.attributed_surface == "database"
    assert result.counterfactual_valid is False


def test_summarize_empty() -> None:
    report = summarize_counterfactual([])
    assert report.total == 0
    assert report.validity_rate == 0.0

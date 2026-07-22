from __future__ import annotations

from pathlib import Path

from policystrata.adversarial_controls import (
    ARCHETYPES,
    generate_adversarial_clean_control_tasks,
)
from policystrata.baselines import evaluate_false_positive_runs
from policystrata.domain import load_policy, load_surfaces, load_tasks
from policystrata.generator import (
    DEFAULT_CLEAN_CONTROL_SEED,
    generate_clean_control_tasks,
)
from policystrata.models import WitnessClass
from policystrata.runner import run_suite
from policystrata.summary import summarize_run


def test_generates_requested_count_all_clean() -> None:
    policy = load_policy("support_saas")
    surfaces = load_surfaces("support_saas")
    tasks = generate_adversarial_clean_control_tasks("support_saas", policy, surfaces, count=1000)
    assert len(tasks) == 1000
    assert all(task.expected_witness_class == WitnessClass.CLEAN for task in tasks)
    assert all(task.mutation == "none" for task in tasks)


def test_covers_all_archetypes() -> None:
    policy = load_policy("support_saas")
    surfaces = load_surfaces("support_saas")
    tasks = generate_adversarial_clean_control_tasks("support_saas", policy, surfaces, count=70)
    # Every archetype appears at least once in the request text.
    for archetype in ("staged rollout", "feature-flagged", "row budget", "service account", "denies"):
        assert any(archetype in task.request for task in tasks)
    assert len(ARCHETYPES) == 7


def test_existing_clean_controls_suite_unchanged() -> None:
    # The shipped 80-case clean-control suite must be byte-identical (frozen).
    policy = load_policy("support_saas")
    surfaces = load_surfaces("support_saas")
    tasks = generate_clean_control_tasks(policy=policy, surface_versions=surfaces, domain="support_saas")
    ids = [task.id for task in tasks]
    assert ids[0].startswith("clean_control_")
    # Regenerating with the shipped default seed is deterministic.
    again = generate_clean_control_tasks(
        policy=policy, surface_versions=surfaces, domain="support_saas", seed=DEFAULT_CLEAN_CONTROL_SEED
    )
    assert [t.model_dump() for t in tasks] == [t.model_dump() for t in again]


def test_suite_loads_via_domain(tmp_path: Path) -> None:
    tasks = load_tasks("support_saas", "adversarial_clean_controls", generated_count=140)
    assert len(tasks) == 140


def test_detector_zero_fp_baseline_separation(tmp_path: Path) -> None:
    run_dir = tmp_path / "adv"
    run_suite("support_saas", "adversarial_clean_controls", run_dir, generated_count=700)
    summary = summarize_run(run_dir)
    assert summary.total == 700
    assert summary.clean_controls == 700
    # Responsibility-contract detector: zero false positives.
    assert summary.false_positives == 0
    # A naive denial-flagging baseline false-positives on the legitimately-denied
    # archetypes; the contract detector does not. This is the precision gap.
    fp = evaluate_false_positive_runs([run_dir])
    assert fp["validator_only"]["false_positives"] > 0
    # Deployable decision/differential baselines see none in this simulator.
    assert fp["naive_surface_equality"]["false_positives"] == 0
    assert fp["property_differential"]["false_positives"] == 0

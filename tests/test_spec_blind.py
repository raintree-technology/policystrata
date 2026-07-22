import json
from pathlib import Path

import pytest

from policystrata.cli import main

SPEC_BLIND_DOMAIN_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "spec_blind"

# These counts are pinned against docs/spec-blind-results.md. If this suite's
# tasks or labels ever change, that doc's headline numbers and per-miss table
# need to be regenerated and re-reviewed, not just this test's expectations.
EXPECTED_TOTAL = 42
EXPECTED_KILLED = 39
EXPECTED_SURVIVED = 3
EXPECTED_KILL_RATE = EXPECTED_KILLED / EXPECTED_TOTAL
EXPECTED_LOCALIZATION_ACCURACY = 1.0
EXPECTED_CLASS_ACCURACY = EXPECTED_KILLED / EXPECTED_TOTAL

# Every operator in the suite ran 3 tasks; only cost_estimate_ignores_expansion
# survived (all 3), matching the "genuinely ambiguous / contract underspecified"
# per-miss entry in docs/spec-blind-results.md.
SURVIVED_MUTATION = "cost_estimate_ignores_expansion"
EXPECTED_OPERATORS = {
    "stale_metric_alias_manifest",
    "grammar_permits_forbidden_dimension",
    "validator_omits_sensitive_column",
    "compiler_drops_tenant_predicate",
    "compiler_uses_old_tenant_key",
    "compiler_swaps_tenant_account_id",
    "db_rls_old_ownership_field",
    "gross_net_metric_drift",
    "fanout_join_drift",
    "compiler_removes_distinct",
    "compiler_inner_join_drops_rows",
    "fiscal_calendar_mismatch",
    SURVIVED_MUTATION,
    "app_deny_missing_db_policy",
}


def _run_spec_blind_suite(out_dir: Path) -> None:
    exit_code = main(
        [
            "run",
            "--domain",
            "support_saas",
            "--domain-path",
            str(SPEC_BLIND_DOMAIN_PATH),
            "--suite",
            "spec_blind",
            "--out",
            str(out_dir),
        ]
    )
    assert exit_code == 0


def test_spec_blind_suite_loads_via_base_path_and_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "run"

    _run_spec_blind_suite(out_dir)
    run_output = json.loads(capsys.readouterr().out)

    assert run_output["out"] == str(out_dir)
    assert run_output["traces"] == EXPECTED_TOTAL
    assert (out_dir / "traces.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "metadata.json").exists()


def test_spec_blind_headline_numbers_match_reported_results(tmp_path: Path) -> None:
    out_dir = tmp_path / "run"
    _run_spec_blind_suite(out_dir)

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["total"] == EXPECTED_TOTAL
    assert summary["killed"] == EXPECTED_KILLED
    assert summary["survived"] == EXPECTED_SURVIVED
    assert summary["equivalent"] == 0
    assert summary["invalid"] == 0
    assert summary["clean_controls"] == 0
    assert summary["false_positives"] == 0
    assert summary["mutant_kill_rate"] == pytest.approx(EXPECTED_KILL_RATE)
    assert summary["localization_accuracy"] == pytest.approx(EXPECTED_LOCALIZATION_ACCURACY)
    assert summary["expected_class_accuracy"] == pytest.approx(EXPECTED_CLASS_ACCURACY)
    assert summary["minimized_witness_count"] == EXPECTED_KILLED


def test_spec_blind_suite_metadata_declares_spec_blind_provenance(tmp_path: Path) -> None:
    out_dir = tmp_path / "run"
    _run_spec_blind_suite(out_dir)

    metadata = json.loads((out_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["domain"] == "support_saas"
    assert metadata["suite"] == "spec_blind"
    assert metadata["suite_provenance"] == "hand_authored"
    assert metadata["evidence_level"] == "blinded_suite"
    assert metadata["suite_metadata"]["notes"] == [
        "spec-blind authored; labels derived from contract docs without detector access",
        "not a fully independent/external author: same repo worktree, same agent session, "
        "self-restricted to a documented allowlist of contract files "
        "(see header comment and docs/spec-blind-results.md)",
        "provenance is 'hand_authored' rather than 'generated' because every task was written "
        "by hand from the contract, not synthesized by policystrata's generator.py seed/count "
        "mechanism; 'generated' would overclaim the method used here",
    ]


def test_spec_blind_only_cost_estimate_operator_survived(tmp_path: Path) -> None:
    out_dir = tmp_path / "run"
    _run_spec_blind_suite(out_dir)

    lines = (out_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
    traces = [json.loads(line) for line in lines]

    assert len(traces) == EXPECTED_TOTAL
    assert all(trace["domain"] == "support_saas" for trace in traces)
    assert {trace["mutation"] for trace in traces} == EXPECTED_OPERATORS

    by_mutation: dict[str, list[str]] = {}
    for trace in traces:
        by_mutation.setdefault(trace["mutation"], []).append(trace["accounting_status"])

    assert set(by_mutation) == EXPECTED_OPERATORS
    for mutation, statuses in by_mutation.items():
        assert len(statuses) == 3
        if mutation == SURVIVED_MUTATION:
            assert statuses == ["survived", "survived", "survived"]
        else:
            assert statuses == ["killed", "killed", "killed"]

    survived_ids = {trace["task_id"] for trace in traces if trace["accounting_status"] == "survived"}
    assert survived_ids == {
        "sb-compiler-costexpand-01",
        "sb-compiler-costexpand-02",
        "sb-compiler-costexpand-03",
    }

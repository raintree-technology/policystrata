"""Pins the current adapter-TCB mutation classification.

Every entry in policystrata.tcb_catalog.CATALOG is applied against a fixed
detection scenario and the observed outcome is compared to the recorded
classification below. Hardening an adapter (checksums, count invariants,
schema validation) should flip entries from HIDDEN/INVENTED to LOUD and show
up here as a diff.
"""

from pathlib import Path

from policystrata import database, scanner, trace_import
from policystrata.tcb_catalog import (
    CATALOG,
    Outcome,
    outcome_tally,
    run_catalog,
    run_scenario,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "tcb"

EXPECTED_OUTCOMES = {
    "import_drops_tenant_ids": Outcome.INVENTED,
    "import_forces_release_denied": Outcome.HIDDEN,
    "import_drops_semantic_ir": Outcome.HIDDEN,
    "import_swaps_denied_metric": Outcome.HIDDEN,
    "import_stamps_default_principal": Outcome.HIDDEN,
    "import_drops_all_traces": Outcome.HIDDEN,
    "import_returns_none": Outcome.LOUD,
    "import_drops_source_field": Outcome.NEUTRAL,
    "import_skips_malformed_lines": Outcome.HIDDEN,
    "sql_guard_accepts_multi_statement": Outcome.HIDDEN,
    "sql_guard_rejects_cte": Outcome.INVENTED,
    "db_truncates_result_rows": Outcome.HIDDEN,
    "db_renames_result_columns": Outcome.HIDDEN,
    "state_eval_ignores_forbidden_values": Outcome.HIDDEN,
    "emit_drops_release_findings": Outcome.HIDDEN,
    "emit_duplicates_static_findings": Outcome.INVENTED,
    "emit_downgrades_severity": Outcome.HIDDEN,
    "gate_always_passes": Outcome.HIDDEN,
}


def test_catalog_covers_every_tcb_adapter() -> None:
    adapters = {mutation.adapter for mutation in CATALOG}
    mutation_ids = [mutation.id for mutation in CATALOG]

    assert adapters == {"trace_import", "sql_guard", "db_results", "finding_emission"}
    assert len(mutation_ids) == len(set(mutation_ids))
    assert set(mutation_ids) == set(EXPECTED_OUTCOMES)


def test_main_scenario_baseline_detects_true_findings(tmp_path: Path) -> None:
    signature = run_scenario("main", FIXTURE_DIR, tmp_path / "baseline")

    assert signature.gate == "fail"
    assert {finding_id for finding_id, _ in signature.findings} == {
        "unsafe_release_denied_metric_release",
        "unauthorized_trace_reached_sql_denied_metric_release",
        "trace_unknown_principal_ghost_principal",
        "tenant_scope_missing_stale_scope_trace",
    }


def test_adapter_mutations_match_recorded_classification(tmp_path: Path) -> None:
    results = run_catalog(FIXTURE_DIR, tmp_path)
    outcomes = {result.mutation_id: result.outcome for result in results}

    assert outcomes == EXPECTED_OUTCOMES
    assert outcome_tally(results) == {"HIDDEN": 13, "INVENTED": 3, "NEUTRAL": 1, "LOUD": 1}


def test_run_catalog_restores_patched_adapters(tmp_path: Path) -> None:
    originals = (
        scanner.load_imported_traces,
        scanner.finding,
        scanner.decide_gate,
        scanner.scan_trace_authorization,
        scanner.scan_trace_static_sql,
        scanner.evaluate_state_assertion,
        scanner.assert_read_only_sql,
        trace_import.assert_read_only_sql,
        database.assert_read_only_sql,
    )

    run_catalog(FIXTURE_DIR, tmp_path)

    assert (
        scanner.load_imported_traces,
        scanner.finding,
        scanner.decide_gate,
        scanner.scan_trace_authorization,
        scanner.scan_trace_static_sql,
        scanner.evaluate_state_assertion,
        scanner.assert_read_only_sql,
        trace_import.assert_read_only_sql,
        database.assert_read_only_sql,
    ) == originals

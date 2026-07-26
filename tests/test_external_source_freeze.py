from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "benchmarks" / "external_source" / "metricflow-freeze.json"


def test_metricflow_external_source_freeze_matches_checked_in_inputs() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    expected_hashes = freeze["frozen_inputs_sha256"]

    for relative_path, expected_hash in expected_hashes.items():
        content = (ROOT / relative_path).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected_hash, relative_path


def test_metricflow_external_source_freeze_has_exact_selection_accounting() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    selection = freeze["selection"]
    trace_path = ROOT / "examples" / "brownfield" / "metricflow" / "traces.jsonl"
    traces = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

    assert len(traces) == selection["cases_selected"] == 68
    assert len({trace["id"] for trace in traces}) == 68
    assert all(trace["source"].startswith("metricflow:tests_metricflow/") for trace in traces)
    assert (
        selection["cases_selected"]
        + selection["skipped_multi_metric"]
        + selection["skipped_other_manifest"]
        + selection["skipped_macro_dependent"]
        + selection["skipped_unusable_sql"]
        == selection["documents_seen"]
    )


def test_metricflow_external_source_claim_does_not_imply_external_operation() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))

    assert freeze["authorship"]["operated_by_external_party"] is False
    assert "Raintree-authored adapter" in freeze["authorship"]["claim"]

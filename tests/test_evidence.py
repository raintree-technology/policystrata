import json

import pytest

from policystrata.evidence import render_evidence_tables, run_artifact_path
from policystrata.runner import run_suite


@pytest.mark.parametrize("witness_path", ["../secret.json", "/tmp/secret.json"])
def test_evidence_rejects_witness_paths_outside_run_dir(tmp_path, witness_path: str) -> None:
    run_dir = tmp_path / "run"
    run_suite("support_saas", "seeded", run_dir)
    traces_path = run_dir / "traces.jsonl"
    lines = traces_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["witness_path"] = witness_path
    lines[0] = json.dumps(first)
    traces_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError):
        render_evidence_tables({"malicious": run_dir})


def test_evidence_rejects_symlink_witness_escape(tmp_path) -> None:
    run_dir = tmp_path / "run"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text("secret", encoding="utf-8")
    run_suite("support_saas", "seeded", run_dir)
    (run_dir / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes run directory"):
        run_artifact_path(run_dir, "linked/secret.json")


def test_evidence_accepts_in_run_witness_path(tmp_path) -> None:
    run_dir = tmp_path / "run"
    traces = run_suite("support_saas", "seeded", run_dir)

    path = run_artifact_path(run_dir, traces[0].witness_path or "")

    assert path.is_file()


def test_evidence_renders_suite_provenance(tmp_path) -> None:
    run_dir = tmp_path / "run"
    run_suite("support_saas", "seeded", run_dir)

    evidence = render_evidence_tables({"seeded": run_dir})

    assert "## Evidence Provenance" in evidence
    assert "Evidence level" in evidence
    assert "| seeded | 50 | 50 | 0 | 0 |" in evidence
    assert "deterministic_fixture" in evidence
    assert "hand_authored" in evidence

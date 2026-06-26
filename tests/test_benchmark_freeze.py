import json

from policystrata.cli import main
from policystrata.freeze import verify_benchmark_manifest, write_benchmark_manifest
from policystrata.runner import run_suite


def test_freeze_manifest_verifies_and_marks_run_metadata(tmp_path) -> None:
    manifest_path = tmp_path / "freeze" / "support-generated.json"
    manifest = write_benchmark_manifest(
        "support_saas",
        "generated",
        manifest_path,
        generated_count=12,
        generated_seed=1729,
    )

    verification = verify_benchmark_manifest(
        manifest_path,
        domain="support_saas",
        suite="generated",
        generated_count=12,
        generated_seed=1729,
    )
    assert verification["verified"] is True
    assert verification["mismatches"] == []

    run_dir = tmp_path / "run"
    traces = run_suite(
        "support_saas",
        "generated",
        run_dir,
        generated_count=12,
        generated_seed=1729,
        freeze_manifest=manifest_path,
    )

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    copied_manifest = json.loads((run_dir / "benchmark_manifest.json").read_text(encoding="utf-8"))
    assert len(traces) == 12
    assert metadata["detector_frozen"] is True
    assert metadata["benchmark_manifest_id"] == manifest["benchmark_manifest_id"]
    assert metadata["detector_freeze_id"] == manifest["benchmark_manifest_id"]
    assert copied_manifest["benchmark_manifest_id"] == manifest["benchmark_manifest_id"]


def test_freeze_verification_detects_suite_tampering(tmp_path) -> None:
    manifest_path = tmp_path / "freeze.json"
    write_benchmark_manifest(
        "support_saas",
        "generated",
        manifest_path,
        generated_count=12,
        generated_seed=1729,
    )

    verification = verify_benchmark_manifest(
        manifest_path,
        domain="support_saas",
        suite="generated",
        generated_count=13,
        generated_seed=1729,
    )

    assert verification["verified"] is False
    assert {item["field"] for item in verification["mismatches"]} >= {"generated_count", "task_hash"}


def test_freeze_cli_round_trip_and_tamper_exit_code(tmp_path, capsys) -> None:
    manifest_path = tmp_path / "freeze.json"

    assert (
        main(
            [
                "freeze-benchmark",
                "--domain",
                "support_saas",
                "--suite",
                "generated",
                "--count",
                "8",
                "--seed",
                "99",
                "--out",
                str(manifest_path),
            ]
        )
        == 0
    )
    created = json.loads(capsys.readouterr().out)
    assert created["benchmark_manifest_id"].startswith("psf-")

    assert (
        main(
            [
                "verify-freeze",
                str(manifest_path),
                "--domain",
                "support_saas",
                "--suite",
                "generated",
                "--count",
                "8",
                "--seed",
                "99",
            ]
        )
        == 0
    )
    verified = json.loads(capsys.readouterr().out)
    assert verified["verified"] is True

    assert (
        main(
            [
                "verify-freeze",
                str(manifest_path),
                "--domain",
                "support_saas",
                "--suite",
                "generated",
                "--count",
                "9",
                "--seed",
                "99",
            ]
        )
        == 1
    )
    failed = json.loads(capsys.readouterr().out)
    assert failed["verified"] is False
